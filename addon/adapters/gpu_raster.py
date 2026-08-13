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

    `reasons` holds the unsupported reason for any polygon the CPU path rejected,
    keyed by index and usually empty. Those polygons keep zeros in the arrays,
    exactly as `rasterize_batch` leaves them.
    """

    covered: numpy.ndarray
    affected: numpy.ndarray
    reasons: dict[int, str]


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
    int index = 0;
    while (index < found) {
      int start = lo[index], stop = hi[index];
      ++index;
      while (index < found && lo[index] <= stop) {
        stop = max(stop, hi[index]);
        ++index;
      }
      total_covered += uint(stop - start);
      total_affected += counted(resolved, outside, start, stop);
    }
  }
  imageStore(covered, at(p), uvec4(total_covered, 0u, 0u, 0u));
  imageStore(affected, at(p), uvec4(total_affected, 0u, 0u, 0u));
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
    for name in (
        "row_width", "polygon_count", "width", "height", "words_per_row",
        "mode", "period",
    ):
        info.push_constant("INT", name)
    info.local_group_size(64, 1, 1)
    info.compute_source(_SOURCE % {"bits": _BITS, "cap": SPAN_CAP})
    return gpu.shader.create_from_info(info)


def _dispatch(shader, triangles, counts, grid, mode):
    """Run the kernel and read back per-polygon covered and affected counts."""
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
    covered = _result_texture(polygons)
    affected = _result_texture(polygons)

    shader.bind()
    shader.image("tris", tris)
    shader.image("mask", mask)
    shader.image("rowsum", rowsum)
    shader.image("layout_", layout_texture)
    shader.image("covered", covered)
    shader.image("affected", affected)
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
    return (
        numpy.asarray(covered.read()).reshape(-1)[:polygons].astype(numpy.int64),
        numpy.asarray(affected.read()).reshape(-1)[:polygons].astype(numpy.int64),
    )


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
    expected_covered = numpy.array([one.stats.covered_texels for one in oracle])

    try:
        for mode in _MODE_CODE:
            produced = _dispatch(shader, quads, counts, grid, mode)
            if produced is None:
                return False
            covered, affected = produced
            if not numpy.array_equal(covered, expected_covered):
                return False
            if not numpy.array_equal(
                affected, numpy.array(grid.count_batch(oracle, mode))
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
        if gpu.platform.backend_type_get() == "METAL":
            _reason = "NO_FP64: Metal has no double precision"
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
    """
    if mode not in _MODE_CODE or settings.margin_texels or not available():
        return None
    polygons = int(counts.shape[0])
    if polygons == 0:
        empty = numpy.zeros(0, dtype=numpy.int64)
        return GpuCounts(empty, empty, {})

    live_counts, scanlines, invalid = _survey(triangles, counts)
    # `_within_segment` makes the CPU's budget a running total within a polygon,
    # so a polygon whose total stays inside the budget never trips and one whose
    # total exceeds it always does. Runs are at most one per triangle per row, so
    # the scanline total bounds the emission total too and one comparison covers
    # both budgets. Conservative in the safe direction: a polygon routed to the
    # CPU that would not have tripped still gets the right answer.
    budget = min(settings.max_scanlines, settings.max_run_emissions)
    slow = invalid | (live_counts > SPAN_CAP) | (scanlines > budget)
    if not slow.any():
        produced = _dispatch(_shader, triangles, counts, grid, mode)
        if produced is None:
            return None
        return GpuCounts(produced[0], produced[1], {})

    # One awkward polygon must not disable the GPU for the whole mesh, so the
    # awkward ones go to the CPU and the results merge back by index.
    by_triangle = numpy.repeat(slow, counts)
    covered = numpy.zeros(polygons, dtype=numpy.int64)
    affected = numpy.zeros(polygons, dtype=numpy.int64)
    fast = ~slow
    if fast.any():
        produced = _dispatch(
            _shader, triangles[~by_triangle], counts[fast], grid, mode
        )
        if produced is None:
            return None
        covered[fast], affected[fast] = produced

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
    reasons: dict[int, str] = {}
    for coverage, index in zip(coverages, numpy.flatnonzero(slow)):
        if isinstance(coverage, str):
            reasons[int(index)] = coverage
            continue
        covered[index] = coverage.stats.covered_texels
        affected[index] = next(resolved)
    return GpuCounts(covered, affected, reasons)
