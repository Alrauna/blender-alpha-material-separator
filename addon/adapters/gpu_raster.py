# SPDX-License-Identifier: GPL-3.0-or-later
"""Fused UV rasterization and alpha counting on the GPU, when it is exact.

`addon.core.raster` remains the authority. This reproduces it for the cases it
covers and returns `None` for everything else, so the caller always has a
correct path. `docs/gpu-rasterization.md` holds the design and the measurements
behind it.

Not in `addon/core/` because that package forbids Blender imports and the unit
suite runs without Blender, while `gpu` is a Blender module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy

from ..core import AddressMode, rasterize_batch

#: Triangles per polygon the kernel can union in one thread. A polygon past this
#: goes to the CPU rather than failing its batch.
SPAN_CAP = 32

#: Alpha mask texels per float32. `R32F` is exact below 2^24, which is what a
#: 24-bit word needs, and packing this way carries an 87 MB mask in 3.6 MB.
_BITS = 24

#: Textures are laid out as rows of this width; anything longer wraps.
_ROW_WIDTH = 8192

@dataclass(frozen=True, slots=True)
class GpuCounts:
    """Per-polygon results, aligned with the input order.

    Every field but `reasons` is an int64 array with one entry per polygon. The
    six counters are the fields of `RasterStats`, kept as arrays rather than as
    objects because building one object per polygon is the cost the batch path
    exists to avoid; the caller constructs them only for the faces it reports.

    `reasons` holds the unsupported reason for any polygon the CPU path rejected,
    keyed by index and usually empty. Those polygons keep zeros in the arrays,
    exactly as `rasterize_batch` leaves them.
    """

    affected: numpy.ndarray
    triangles: numpy.ndarray
    degenerate_triangles: numpy.ndarray
    scanlines: numpy.ndarray
    emitted_runs: numpy.ndarray
    union_runs: numpy.ndarray
    covered_texels: numpy.ndarray
    reasons: dict[int, str]


#: The array fields of `GpuCounts`, in order. Everything after the first is a
#: field of `RasterStats` under the same name.
_COUNTERS = tuple(
    field for field in GpuCounts.__slots__ if field != "reasons"
)


#: Address modes as the kernel numbers them. GLSL has no enums worth the ceremony.
_MODE_CODE = {
    AddressMode.REPEAT: 0,
    AddressMode.EXTEND: 1,
    AddressMode.CLIP: 2,
    AddressMode.MIRROR: 3,
}

_SOURCE = """
ivec2 at(int linear) { return ivec2(linear %% row_width, linear / row_width); }

int whole(int slot) { return int(imageLoad(layout_, at(slot)).r); }

/* Three 22-bit chunks reassembled into one IEEE double. */
double chunked(int slot) {
  uint c0 = uint(imageLoad(tris, at(slot * 3 + 0)).r);
  uint c1 = uint(imageLoad(tris, at(slot * 3 + 1)).r);
  uint c2 = uint(imageLoad(tris, at(slot * 3 + 2)).r);
  return packDouble2x32(uvec2(c0 | ((c1 & 0x3FFu) << 22), (c1 >> 10) | (c2 << 12)));
}

/* GLSL leaves `%%` undefined when either operand is negative, so fold the value
   positive first and never hand the operator a negative. Observed, not
   theoretical: the truncate-then-correct form disagreed with the CPU on every
   negative row and start once the image dimensions were not powers of two. */
int floor_mod(int value, int period) {
  if (value >= 0) { return value %% period; }
  int folded = (-value) %% period;
  return folded == 0 ? 0 : period - folded;
}

/* Set mask bits in [from, to) of one padded row. */
uint bits_in(int row, int from, int to) {
  if (to <= from) { return 0u; }
  int base = row * words_per_row;
  int first = from / %(bits)d, last = (to - 1) / %(bits)d;
  int lead = from - first * %(bits)d, tail = (to - 1) - last * %(bits)d;
  uint high = (1u << (tail + 1)) - 1u;
  if (first == last) {
    uint word = uint(imageLoad(mask, at(base + first)).r);
    return uint(bitCount(word & high & ~((1u << lead) - 1u)));
  }
  uint total = uint(bitCount(uint(imageLoad(mask, at(base + first)).r)
                             & ~((1u << lead) - 1u)));
  for (int word = first + 1; word < last; ++word) {
    total += uint(bitCount(uint(imageLoad(mask, at(base + word)).r)));
  }
  return total + uint(bitCount(uint(imageLoad(mask, at(base + last)).r) & high));
}

/* `AlphaGrid._periodic_counts`, with popcount in place of the row prefixes.
   `period` is the width for REPEAT and twice it for MIRROR, whose mask rows are
   uploaded already folded, so both modes share this one form. */
uint periodic(int row, int start, int stop) {
  int remaining = stop - start;
  if (remaining <= 0) { return 0u; }
  int position = floor_mod(start, period);
  int first = min(remaining, period - position);
  uint total = bits_in(row, position, position + first);
  remaining -= first;
  if (remaining > 0) {
    total += uint(remaining / period) * uint(imageLoad(rowsum, at(row)).r);
    total += bits_in(row, 0, remaining %% period);
  }
  return total;
}

bool edge_set(int row, int column) {
  uint word = uint(imageLoad(mask, at(row * words_per_row + column / %(bits)d)).r);
  return (word & (1u << (column %% %(bits)d))) != 0u;
}

/* One run, in whichever mode this batch is using. Mirrors the branches of
   `AlphaGrid.count_batch`; `outside` is its CLIP row mask. */
uint counted(int row, bool outside, int start, int stop) {
  if (stop <= start) { return 0u; }
  if (mode == 0 || mode == 3) { return periodic(row, start, stop); }
  if (outside) { return uint(stop - start); }

  int inside_start = clamp(start, 0, width);
  int inside_stop = clamp(stop, 0, width);
  int inside = max(inside_stop - inside_start, 0);
  uint total = (inside > 0) ? bits_in(row, inside_start, inside_stop) : 0u;
  if (mode == 2) {
    /* Outside a clipped image every cell is transparent. */
    return total + uint((stop - start) - inside);
  }
  /* EXTEND repeats the edge texel, so an overhang counts only when that texel
     is itself affected. */
  if (edge_set(row, 0)) { total += uint(min(stop, 0) - min(start, 0)); }
  if (edge_set(row, width - 1)) {
    total += uint(max(stop, width) - max(start, width));
  }
  return total;
}

/* `AlphaGrid._resolve_rows`. Returns the mask row; sets `outside` for a CLIP
   row that falls off the image, where the whole run counts as transparent. */
int resolve_row(int row, out bool outside) {
  outside = false;
  if (mode == 0) { return floor_mod(row, height); }
  if (mode == 3) {
    int position = floor_mod(row, 2 * height);
    return (position < height) ? position : 2 * height - 1 - position;
  }
  outside = (mode == 2) && (row < 0 || row >= height);
  return clamp(row, 0, height - 1);
}

void main() {
  int p = int(gl_GlobalInvocationID.x);
  if (p >= polygon_count) { return; }
  int base = whole(p * 2), span = whole(p * 2 + 1);
  if (span == 0) {
    imageStore(covered, at(p), uvec4(0u));
    imageStore(affected, at(p), uvec4(0u));
    imageStore(emitted, at(p), uvec4(0u));
    imageStore(unions, at(p), uvec4(0u));
    return;
  }

  /* The polygon's scanline range is the union of its triangles' ranges. */
  double first_row = 0.0lf, stop_row = 0.0lf;
  for (int t = 0; t < span; ++t) {
    double low_y = chunked((base + t) * 6 + 1);
    double high_y = chunked((base + t) * 6 + 5);
    double lo_row = floor(low_y);
    double hi_row = lo_row + max(0.0lf, ceil(high_y) - lo_row);
    first_row = (t == 0) ? lo_row : min(first_row, lo_row);
    stop_row = (t == 0) ? hi_row : max(stop_row, hi_row);
  }

  uint total_covered = 0u, total_affected = 0u;
  uint total_emitted = 0u, total_unions = 0u;
  int lo[%(cap)d], hi[%(cap)d];
  for (double row = first_row; row < stop_row; row += 1.0lf) {
    int found = 0;
    for (int t = 0; t < span; ++t) {
      int slot = (base + t) * 6;
      double low_x = chunked(slot + 0), low_y = chunked(slot + 1);
      double mid_x = chunked(slot + 2), mid_y = chunked(slot + 3);
      double high_x = chunked(slot + 4), high_y = chunked(slot + 5);
      double tri_first = floor(low_y);
      if (row < tri_first || row >= tri_first + max(0.0lf, ceil(high_y) - tri_first)) {
        continue;
      }

      /* `precise` holds bit-equality with the CPU; see the design document. */
      precise double long_slope = (high_x - low_x) / (high_y - low_y);
      precise double lower_slope =
          (mid_y > low_y) ? (mid_x - low_x) / (mid_y - low_y) : 0.0lf;
      precise double upper_slope =
          (high_y > mid_y) ? (high_x - mid_x) / (high_y - mid_y) : 0.0lf;

      /* The scalar loop carries the previous row's cross-sections forward.
         That is the value at the band's lower boundary: the bottom vertex on
         the triangle's first row, and the scanline everywhere else. */
      bool is_first = row == tri_first;
      double lower_y = is_first ? low_y : row;
      precise double previous_long =
          is_first ? low_x : low_x + (lower_y - low_y) * long_slope;
      precise double previous_short;
      if (is_first) {
        previous_short = (mid_y == low_y) ? mid_x : low_x;
      } else if (lower_y < mid_y) {
        previous_short = low_x + (lower_y - low_y) * lower_slope;
      } else if (lower_y > mid_y) {
        previous_short = mid_x + (lower_y - mid_y) * upper_slope;
      } else {
        previous_short = mid_x;
      }

      /* The last band ends on the top vertex. Use its coordinate directly;
         recomputing it from a slope can land a rounding step past a texel
         boundary and widen the run. */
      double upper = row + 1.0lf;
      bool at_top = upper >= high_y;
      double upper_y = at_top ? high_y : upper;
      precise double current_long =
          at_top ? high_x : low_x + (upper_y - low_y) * long_slope;
      precise double current_short;
      if (at_top) {
        current_short = (mid_y == high_y) ? mid_x : high_x;
      } else if (upper_y < mid_y) {
        current_short = low_x + (upper_y - low_y) * lower_slope;
      } else if (upper_y > mid_y) {
        current_short = mid_x + (upper_y - mid_y) * upper_slope;
      } else {
        current_short = mid_x;
      }

      double minimum = min(min(previous_long, previous_short),
                           min(current_long, current_short));
      double maximum = max(max(previous_long, previous_short),
                           max(current_long, current_short));
      /* The middle vertex is the only extremum off a band edge. */
      if (row < mid_y && mid_y < upper_y) {
        minimum = min(minimum, mid_x);
        maximum = max(maximum, mid_x);
      }
      if (!(minimum < maximum)) { continue; }
      int start = int(floor(minimum)), stop = int(ceil(maximum));
      if (start >= stop) { continue; }

      int place = found++;
      while (place > 0 && lo[place - 1] > start) {
        lo[place] = lo[place - 1]; hi[place] = hi[place - 1]; --place;
      }
      lo[place] = start; hi[place] = stop;
    }

    /* `_merge_spans` over one row: sorted by start, absorb while they touch. */
    bool outside;
    int resolved = resolve_row(int(row), outside);
    total_emitted += uint(found);
    int index = 0;
    while (index < found) {
      int start = lo[index], stop = hi[index];
      ++index;
      while (index < found && lo[index] <= stop) {
        stop = max(stop, hi[index]);
        ++index;
      }
      ++total_unions;
      total_covered += uint(stop - start);
      total_affected += counted(resolved, outside, start, stop);
    }
  }
  imageStore(covered, at(p), uvec4(total_covered, 0u, 0u, 0u));
  imageStore(affected, at(p), uvec4(total_affected, 0u, 0u, 0u));
  imageStore(emitted, at(p), uvec4(total_emitted, 0u, 0u, 0u));
  imageStore(unions, at(p), uvec4(total_unions, 0u, 0u, 0u));
}
"""

#: `False` once the probe has run and failed, the shader once it has succeeded,
#: `None` before it has run. The probe never runs twice.
_shader: object | None | bool = None

#: Why the probe decided what it decided. `MISMATCH` is the one that means the
#: machine has a working GPU that computes the wrong answer, which is a defect
#: rather than an absent capability, so the tests fail on it instead of skipping.
_reason = "not probed"

#: `id(grid)` to `(grid, mask texture, row-sum texture, words per row)`. The grid
#: is held so its id cannot be reused by another object while the entry lives.
_masks: dict[int, tuple] = {}


def _texture(values: numpy.ndarray, fmt: str = "R32F"):
    import gpu

    flat = numpy.ascontiguousarray(values, dtype=numpy.float32).reshape(-1)
    rows = max(1, -(-flat.size // _ROW_WIDTH))
    padded = numpy.zeros(_ROW_WIDTH * rows, dtype=numpy.float32)
    padded[: flat.size] = flat
    return gpu.types.GPUTexture(
        (_ROW_WIDTH, rows),
        format=fmt,
        data=gpu.types.Buffer("FLOAT", padded.size, padded),
    )


def _result_texture(length: int):
    import gpu

    rows = max(1, -(-length // _ROW_WIDTH))
    return gpu.types.GPUTexture((_ROW_WIDTH, rows), format="R32UI")


def _chunked(values: numpy.ndarray) -> numpy.ndarray:
    """Doubles as three 22-bit pieces, each exact through an `R32F` upload."""
    bits = numpy.ascontiguousarray(values, dtype=numpy.float64).view(numpy.uint64)
    return numpy.stack(
        (
            (bits & 0x3FFFFF).astype(numpy.float32),
            ((bits >> 22) & 0x3FFFFF).astype(numpy.float32),
            (bits >> 44).astype(numpy.float32),
        ),
        axis=-1,
    ).reshape(-1)


def _packed_mask(plane: numpy.ndarray) -> tuple[numpy.ndarray, int]:
    """Row-padded mask, 24 texels per float32, and the words each row occupies.

    Rows are padded to whole words so a run never reads across a row boundary,
    which is what lets the shader address by `row * words_per_row`.
    """
    height, width = plane.shape
    words = -(-width // _BITS)
    padded = numpy.zeros((height, words * _BITS), dtype=numpy.uint8)
    padded[:, :width] = plane
    triples = (
        numpy.packbits(padded, axis=1, bitorder="little")
        .reshape(height, words, 3)
        .astype(numpy.uint32)
    )
    return triples[:, :, 0] | (triples[:, :, 1] << 8) | (triples[:, :, 2] << 16), words


def _mask_textures(grid, mirrored: bool):
    """The packed mask and per-row sums, built once per grid and folding.

    MIRROR gets its rows uploaded already folded, each row followed by its own
    reverse, which is what `AlphaGrid._ensure_mirrors` builds on the CPU. That
    turns MIRROR into REPEAT over a period of twice the width and keeps one
    counting form in the kernel instead of two.
    """
    key = (id(grid), mirrored)
    entry = _masks.get(key)
    if entry is None or entry[0] is not grid:
        plane = grid._plane
        if mirrored:
            plane = numpy.concatenate((plane, plane[:, ::-1]), axis=1)
        packed, words = _packed_mask(plane)
        entry = (grid, _texture(packed), _texture(plane.sum(axis=1)), words)
        _masks[key] = entry
    return entry[1], entry[2], entry[3]


def clear_cache() -> None:
    """Drop the retained mask textures. Safe to call when the GPU is absent."""
    _masks.clear()


def _survey(triangles: numpy.ndarray, counts: numpy.ndarray):
    """Per-polygon live triangle count and scanline total, without rasterizing.

    Both come from the sorted heights alone, which is why partitioning can be
    decided before a dispatch rather than after one.
    """
    xs, ys = triangles[:, :, 0], triangles[:, :, 1]
    polygons = int(counts.shape[0])
    of_triangle = numpy.repeat(numpy.arange(polygons), counts)
    finite = numpy.isfinite(triangles).all(axis=(1, 2))
    # Excluded from `live` before the arithmetic, or a NaN would read as a
    # positive area and then poison the scanline sum.
    live = finite & (
        (
            (xs[:, 1] - xs[:, 0]) * (ys[:, 2] - ys[:, 0])
            - (ys[:, 1] - ys[:, 0]) * (xs[:, 2] - xs[:, 0])
        )
        != 0.0
    )
    heights = ys[live]
    rows = numpy.maximum(
        0.0, numpy.ceil(heights.max(axis=1)) - numpy.floor(heights.min(axis=1))
    )
    return (
        numpy.bincount(of_triangle[live], minlength=polygons).astype(numpy.int64),
        numpy.bincount(of_triangle[live], weights=rows, minlength=polygons).astype(
            numpy.int64
        ),
        numpy.bincount(of_triangle[~finite], minlength=polygons).astype(bool),
    )


def _prepare(triangles: numpy.ndarray, counts: numpy.ndarray):
    """Drop degenerate triangles and height-sort, as `rasterize_batch` does."""
    xs, ys = triangles[:, :, 0], triangles[:, :, 1]
    live = (
        (xs[:, 1] - xs[:, 0]) * (ys[:, 2] - ys[:, 0])
        - (ys[:, 1] - ys[:, 0]) * (xs[:, 2] - xs[:, 0])
    ) != 0.0
    polygon = numpy.repeat(numpy.arange(counts.shape[0]), counts)[live]
    xs, ys = xs[live], ys[live]

    order = numpy.argsort(ys, axis=1, kind="stable")
    index = numpy.arange(ys.shape[0])[:, None]
    ys, xs = ys[index, order], xs[index, order]

    packed = numpy.empty((xs.shape[0], 6), dtype=numpy.float64)
    packed[:, 0::2], packed[:, 1::2] = xs, ys
    live_counts = numpy.bincount(polygon, minlength=counts.shape[0])
    starts = numpy.concatenate(
        (numpy.zeros(1, dtype=numpy.int64), numpy.cumsum(live_counts))
    )[:-1]
    return (
        _chunked(packed.reshape(-1)),
        numpy.stack((starts, live_counts), axis=1),
        int(live_counts.max(initial=0)),
    )


def _build():
    import gpu

    info = gpu.types.GPUShaderCreateInfo()
    info.image(0, "R32F", "FLOAT_2D", "tris", qualifiers={"READ"})
    info.image(1, "R32F", "FLOAT_2D", "mask", qualifiers={"READ"})
    info.image(2, "R32F", "FLOAT_2D", "rowsum", qualifiers={"READ"})
    info.image(3, "R32F", "FLOAT_2D", "layout_", qualifiers={"READ"})
    info.image(4, "R32UI", "UINT_2D", "covered", qualifiers={"WRITE"})
    info.image(5, "R32UI", "UINT_2D", "affected", qualifiers={"WRITE"})
    info.image(6, "R32UI", "UINT_2D", "emitted", qualifiers={"WRITE"})
    info.image(7, "R32UI", "UINT_2D", "unions", qualifiers={"WRITE"})
    for name in (
        "row_width", "polygon_count", "width", "height", "words_per_row",
        "mode", "period",
    ):
        info.push_constant("INT", name)
    info.local_group_size(64, 1, 1)
    info.compute_source(_SOURCE % {"bits": _BITS, "cap": SPAN_CAP})
    return gpu.shader.create_from_info(info)


#: `1.0 + 2**-52` as its two halves, and the halves of the `2**-52` that
#: subtracting one from it must leave. Single precision cannot hold either: it
#: rounds the input to `1.0` and the difference to `0.0`.
_FP64_INPUT = (0x00000001, 0x3FF00000)
_FP64_EXPECTED = (0x00000000, 0x3CB00000)

_FP64_SOURCE = """
void main() {
  double value = packDouble2x32(uvec2(uint(low), uint(high))) - 1.0lf;
  uvec2 halves = unpackDouble2x32(value);
  imageStore(probe, ivec2(0, 0), uvec4(halves.x, 0u, 0u, 0u));
  imageStore(probe, ivec2(1, 0), uvec4(halves.y, 0u, 0u, 0u));
}
"""


def _has_fp64() -> bool:
    """Whether this backend really computes in double precision.

    The kernel's exactness rests entirely on fp64, and a backend can lack it in
    two ways that look nothing alike. One refuses to compile `double`, which
    raises here. The other compiles it as `float` and quietly returns wrong
    counts, which would otherwise surface as a self-test mismatch — reported as a
    defect rather than as the missing capability it is.

    The bits arrive through push constants so the compiler cannot fold the
    answer at compile time on the host, which would hide the second case.
    """
    import gpu

    info = gpu.types.GPUShaderCreateInfo()
    info.image(0, "R32UI", "UINT_2D", "probe", qualifiers={"WRITE"})
    info.push_constant("INT", "low")
    info.push_constant("INT", "high")
    info.local_group_size(1, 1, 1)
    info.compute_source(_FP64_SOURCE)
    try:
        shader = gpu.shader.create_from_info(info)
    except Exception:
        # A backend without double precision rejects the source. That is the
        # capability answer, not an unexpected failure.
        return False

    texture = _result_texture(2)
    shader.bind()
    shader.image("probe", texture)
    shader.uniform_int("low", _FP64_INPUT[0])
    shader.uniform_int("high", _FP64_INPUT[1])
    gpu.compute.dispatch(shader, 1, 1, 1)
    # Releasing a still-bound shader hard-crashes Blender on the next bind.
    gpu.shader.unbind()
    produced = numpy.asarray(texture.read()).reshape(-1)[:2]
    expected = numpy.array(_FP64_EXPECTED, dtype=produced.dtype)
    return numpy.array_equal(produced, expected)


def _submit(shader, triangles, counts, grid, mode):
    """Queue the kernel and return a handle to read later, or `None` to fall back.

    Split from the readback because reading a result texture waits for the
    dispatch that fills it. Anything the caller does between the two is free.
    """
    import gpu

    chunks, layout, widest = _prepare(triangles, counts)
    if widest > SPAN_CAP:
        return None
    mirrored = mode is AddressMode.MIRROR
    mask, rowsum, words = _mask_textures(grid, mirrored)
    polygons = int(counts.shape[0])
    # Held in locals, not passed inline: a texture collected between bind and
    # dispatch takes its storage with it.
    tris = _texture(chunks)
    layout_texture = _texture(layout)
    outputs = {
        name: _result_texture(polygons)
        for name in ("covered", "affected", "emitted", "unions")
    }

    shader.bind()
    shader.image("tris", tris)
    shader.image("mask", mask)
    shader.image("rowsum", rowsum)
    shader.image("layout_", layout_texture)
    for name, texture in outputs.items():
        shader.image(name, texture)
    shader.uniform_int("row_width", _ROW_WIDTH)
    shader.uniform_int("polygon_count", polygons)
    shader.uniform_int("width", grid.width)
    shader.uniform_int("height", grid.height)
    shader.uniform_int("words_per_row", words)
    shader.uniform_int("mode", _MODE_CODE[mode])
    shader.uniform_int("period", grid.width * 2 if mirrored else grid.width)
    gpu.compute.dispatch(shader, -(-polygons // 64), 1, 1)
    # Releasing a still-bound shader hard-crashes Blender on the next bind.
    gpu.shader.unbind()
    # The input textures ride along in the handle. They are read by a dispatch
    # that has not finished, so they must not be collected before it has.
    return (outputs, polygons, (tris, layout_texture))


def _collect(handle):
    """Read a submitted dispatch. This is where the wait actually happens."""
    outputs, polygons, _inputs = handle
    return {
        name: numpy.asarray(texture.read())
        .reshape(-1)[:polygons]
        .astype(numpy.int64)
        for name, texture in outputs.items()
    }


def _self_test(shader) -> bool:
    """Run a fixed fixture and require the CPU path's exact counts.

    This verifies results rather than compilation, which is the point: a driver
    that rounds division differently, folds `bitCount` unexpectedly, mishandles
    the 24-bit packing or miscompiles the kernel has to fail here rather than in
    a user's report. It does not detect multiply-add contraction, because
    contraction does not change counts; `precise` in the source covers that.
    """
    from ..core import AlphaGrid, rasterize_batch

    # Neither dimension is a power of two, deliberately. A driver that folds a
    # modulo into a bit mask gives the right answer for negative operands only
    # when the period is a power of two, so a 64x16 fixture cannot see it.
    width, height = 53, 17
    columns = numpy.arange(width)
    rows = numpy.arange(height)[:, None]
    plane = (((columns * 7 + rows * 5) % 11) < 4).astype(numpy.uint8)
    grid = AlphaGrid(width, height, plane.reshape(-1).tobytes())

    # UVs deliberately outside the unit square, on both sides and in both axes,
    # with a degenerate triangle and a three-triangle polygon among the quads.
    # The last two are not axis-aligned: their middle vertex is the row's
    # extremum, strictly inside a band, which is the only case where the
    # straddle correction changes a run. Rectangles split into right triangles
    # never reach it, so a fixture of those alone would let that defect pass.
    quads = numpy.array(
        [
            [[-121.5, -40.25], [-60.0, -40.25], [-60.0, -34.5]],
            [[-121.5, -40.25], [-60.0, -34.5], [-121.5, -34.5]],
            [[-30.0, 2.25], [12.75, 2.25], [12.75, 9.5]],
            [[-30.0, 2.25], [12.75, 9.5], [-30.0, 9.5]],
            [[3.0, 9.0], [3.0, 9.0], [40.0, 12.0]],
            [[-70.0, -3.0], [190.5, -3.0], [190.5, 5.25]],
            [[-70.0, -3.0], [190.5, 5.25], [60.0, 5.25]],
            [[-70.0, -3.0], [60.0, 5.25], [-70.0, 1.5]],
            [[10.0, 1.3], [48.7, 5.5], [12.0, 9.1]],
            [[-14.25, 12.4], [-52.6, 15.5], [-11.0, 16.8]],
        ],
        dtype=numpy.float64,
    )
    counts = numpy.array([2, 2, 1, 3, 1, 1], dtype=numpy.int64)

    oracle = rasterize_batch(quads, counts)
    if any(isinstance(one, str) for one in oracle):
        return False
    expected = {
        "covered": numpy.array([one.stats.covered_texels for one in oracle]),
        "emitted": numpy.array([one.stats.emitted_runs for one in oracle]),
        "unions": numpy.array([one.stats.union_runs for one in oracle]),
    }

    try:
        for mode in _MODE_CODE:
            handle = _submit(shader, quads, counts, grid, mode)
            if handle is None:
                return False
            produced = _collect(handle)
            if any(
                not numpy.array_equal(produced[name], want)
                for name, want in expected.items()
            ):
                return False
            if not numpy.array_equal(
                produced["affected"], numpy.array(grid.count_batch(oracle, mode))
            ):
                return False
    finally:
        clear_cache()
    return True


def available() -> bool:
    """Whether this machine can run the kernel exactly. Probed once, cached."""
    global _shader, _reason
    if _shader is not None:
        return _shader is not False
    _shader = False
    try:
        import bpy
        import gpu

        if bpy.app.background:
            # A background Blender has no window to borrow a context from.
            gpu.init()
        if not _has_fp64():
            _reason = "NO_FP64: this GPU does not compute in double precision"
            return False
        shader = _build()
        if _self_test(shader):
            _shader = shader
            _reason = "OK"
        else:
            _reason = "MISMATCH: the self-test did not reproduce the CPU counts"
    except Exception as error:
        # A probe that raises is a probe that failed. The CPU path is correct
        # and always available, so no failure here is worth propagating.
        _reason = f"UNAVAILABLE: {type(error).__name__}: {error}"
        _shader = False
    return _shader is not False


def reason() -> str:
    """Why `available()` answered as it did. Call it after `available()`."""
    return _reason


def counted_batch(
    triangles: numpy.ndarray, counts: numpy.ndarray, grid, mode, *, settings
):
    """Covered and affected texels per polygon, or `None` to use the CPU.

    `triangles` is `(T, 3, 2)` float64 in texel-edge space and `counts` gives the
    consecutive triangles of each polygon, exactly as `rasterize_batch` takes
    them. `None` means this batch is not one the kernel handles and the caller
    must fall back; it is never a partial or approximate answer.

    A non-zero raster margin always falls back. The kernel counts spans as it
    unions them and never materializes them, so it has nothing to dilate, and
    reproducing `rasterize_batch`'s margin pass would mean giving that up.

    This waits for the dispatch. A caller with other work to do should use
    `submit_batch` and `collect_batch` and do that work in between.
    """
    result, pending = submit_batch(triangles, counts, grid, mode, settings=settings)
    return None if result is None else collect_batch(result, pending)


def submit_batch(
    triangles: numpy.ndarray, counts: numpy.ndarray, grid, mode, *, settings
):
    """Queue this batch and return `(partial counts, pending)` for `collect_batch`.

    The counters that need no rasterization are already filled in on the returned
    `GpuCounts`; the rest arrive when it is collected. `(None, None)` means the
    same thing `counted_batch` returning `None` does.
    """
    if mode not in _MODE_CODE or settings.margin_texels or not available():
        return None, None
    polygons = int(counts.shape[0])
    counts = counts.astype(numpy.int64, copy=False)
    if polygons == 0:
        empty = numpy.zeros(0, dtype=numpy.int64)
        return GpuCounts(*([empty] * 7), {}), None

    live_counts, scanlines, invalid = _survey(triangles, counts)
    # `_within_segment` makes the CPU's budget a running total within a polygon,
    # so a polygon whose total stays inside the budget never trips and one whose
    # total exceeds it always does. Runs are at most one per triangle per row, so
    # the scanline total bounds the emission total too and one comparison covers
    # both budgets. Conservative in the safe direction: a polygon routed to the
    # CPU that would not have tripped still gets the right answer.
    budget = min(settings.max_scanlines, settings.max_run_emissions)
    slow = invalid | (live_counts > SPAN_CAP) | (scanlines > budget)

    # `triangles` and `scanlines` need no rasterization, and a degenerate is
    # simply one the survey did not keep.
    result = GpuCounts(
        affected=numpy.zeros(polygons, dtype=numpy.int64),
        # A copy, because a rejected polygon has its counters cleared below and
        # the caller's array must not be written through.
        triangles=numpy.array(counts, dtype=numpy.int64),
        degenerate_triangles=counts - live_counts,
        scanlines=scanlines,
        emitted_runs=numpy.zeros(polygons, dtype=numpy.int64),
        union_runs=numpy.zeros(polygons, dtype=numpy.int64),
        covered_texels=numpy.zeros(polygons, dtype=numpy.int64),
        reasons={},
    )

    fast = ~slow
    by_triangle = numpy.repeat(slow, counts)
    handle = None
    if fast.any():
        handle = _submit(
            _shader,
            triangles if not slow.any() else triangles[~by_triangle],
            counts[fast],
            grid,
            mode,
        )
        if handle is None:
            return None, None
    pending = (handle, fast, slow, by_triangle, triangles, counts, grid, mode, settings)
    return result, pending


def collect_batch(result: GpuCounts, pending) -> GpuCounts:
    """Finish a `submit_batch`: the CPU partition first, then read the dispatch.

    That order is deliberate. Reading the result texture waits for the kernel, so
    the awkward polygons the CPU has to handle anyway are rasterized while it is
    still running rather than after it has stopped.
    """
    if pending is None:
        return result
    handle, fast, slow, by_triangle, triangles, counts, grid, mode, settings = pending
    if slow.any():
        _merge_slow(result, pending)
    if handle is not None:
        produced = _collect(handle)
        result.affected[fast] = produced["affected"]
        result.covered_texels[fast] = produced["covered"]
        result.emitted_runs[fast] = produced["emitted"]
        result.union_runs[fast] = produced["unions"]
    return result


def _merge_slow(result: GpuCounts, pending) -> None:
    """One awkward polygon must not disable the GPU for the whole mesh.

    The over-cap, budget-tripped and non-finite polygons go to the CPU and the
    results merge back by index.
    """
    _handle, _fast, slow, by_triangle, triangles, counts, grid, mode, settings = pending
    coverages = rasterize_batch(
        triangles[by_triangle],
        counts[slow],
        max_scanlines=settings.max_scanlines,
        max_run_emissions=settings.max_run_emissions,
    )
    # `count_batch` takes coverages, not reasons, so the rejected ones are held
    # out of the gather and their counts stay zero.
    resolved = iter(
        grid.count_batch(
            [one for one in coverages if not isinstance(one, str)], mode
        )
    )
    for coverage, index in zip(coverages, numpy.flatnonzero(slow)):
        if isinstance(coverage, str):
            result.reasons[int(index)] = coverage
            continue
        result.affected[index] = next(resolved)
        for name in _COUNTERS[1:]:
            getattr(result, name)[index] = getattr(coverage.stats, name)
    if result.reasons:
        # `rasterize_batch` gives a rejected polygon a reason and no
        # `RasterStats` at all, so no counter may carry a partial figure.
        rejected = numpy.fromiter(
            result.reasons, dtype=numpy.int64, count=len(result.reasons)
        )
        for name in _COUNTERS:
            getattr(result, name)[rejected] = 0
