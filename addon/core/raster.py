# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic positive-area UV triangle rasterization."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from operator import itemgetter

import numpy

from .model import Coverage, InvalidRasterInput, RasterBudgetExceeded, RasterStats

Point = tuple[float, float]
Triangle = tuple[Point, Point, Point]

_height = itemgetter(1)


def _validate_triangle(triangle: Sequence[Point]) -> Triangle:
    if len(triangle) != 3:
        raise InvalidRasterInput("each loop triangle must contain three UV points")
    result = tuple((float(point[0]), float(point[1])) for point in triangle)
    if any(not math.isfinite(value) for point in result for value in point):
        raise InvalidRasterInput("UV coordinates must be finite")
    return result  # type: ignore[return-value]


def _twice_area(triangle: Triangle) -> float:
    (ax, ay), (bx, by), (cx, cy) = triangle
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _merge_spans(
    emitted: list[tuple[int, int, int]]
) -> tuple[list[int], list[int], list[int]]:
    """Union overlapping runs, in one pass over all rows at once.

    Sorting `(row, start, stop)` orders rows and orders runs within each row
    exactly as a per-row sort would, so a single merge that breaks on a row
    change replaces the per-row dict the earlier version accumulated.
    """
    emitted.sort()
    rows: list[int] = []
    starts: list[int] = []
    stops: list[int] = []
    if not emitted:
        return rows, starts, stops
    row, start, stop = emitted[0]
    for next_row, next_start, next_stop in emitted[1:]:
        if next_row == row and next_start <= stop:
            if next_stop > stop:
                stop = next_stop
            continue
        rows.append(row)
        starts.append(start)
        stops.append(stop)
        row, start, stop = next_row, next_start, next_stop
    rows.append(row)
    starts.append(start)
    stops.append(stop)
    return rows, starts, stops


def rasterize_polygon(
    triangles: Iterable[Sequence[Point]],
    *,
    margin_texels: int = 0,
    max_scanlines: int = 1_000_000,
    max_run_emissions: int = 2_000_000,
) -> Coverage:
    """Union triangle coverage for one original polygon.

    Coordinates are already in texel-edge space. A cell is included only when
    its intersection with a triangle has positive area. Budget exhaustion raises
    instead of returning an approximation.
    """
    if margin_texels < 0:
        raise ValueError("margin_texels cannot be negative")
    if max_scanlines <= 0 or max_run_emissions <= 0:
        raise ValueError("raster budgets must be positive")

    emitted: list[tuple[int, int, int]] = []
    triangle_count = 0
    degenerate_triangles = 0
    scanlines = 0
    emitted_runs = 0

    floor = math.floor
    ceil = math.ceil

    for raw_triangle in triangles:
        triangle = _validate_triangle(raw_triangle)
        triangle_count += 1
        if _twice_area(triangle) == 0.0:
            degenerate_triangles += 1
            continue

        # Sorting by height turns scanline clipping into two horizontal
        # cross-sections per row, which is the same convex intersection the
        # previous Sutherland-Hodgman clip computed, without its per-row lists.
        (low_x, low_y), (mid_x, mid_y), (high_x, high_y) = sorted(triangle, key=_height)
        first_row = floor(low_y)
        stop_row = ceil(high_y)
        row_count = max(0, stop_row - first_row)
        if scanlines + row_count > max_scanlines:
            raise RasterBudgetExceeded("scanlines", max_scanlines)
        scanlines += row_count

        # Positive area guarantees high_y > low_y. The short edges are only
        # evaluated on the side of the middle vertex that actually has height.
        long_slope = (high_x - low_x) / (high_y - low_y)
        lower_slope = (mid_x - low_x) / (mid_y - low_y) if mid_y > low_y else 0.0
        upper_slope = (high_x - mid_x) / (high_y - mid_y) if high_y > mid_y else 0.0

        # Cross-section at the bottom vertex; every later row reuses the
        # cross-section the previous row already computed at their shared edge.
        previous_long = low_x
        previous_short = mid_x if mid_y == low_y else low_x

        for row in range(first_row, stop_row):
            upper = row + 1.0
            if upper >= high_y:
                # The last band ends on the top vertex. Use its coordinate
                # directly; recomputing it from a slope can land a rounding
                # step past a texel boundary and widen the run.
                upper = high_y
                current_long = high_x
                current_short = mid_x if mid_y == high_y else high_x
            else:
                current_long = low_x + (upper - low_y) * long_slope
                if upper < mid_y:
                    current_short = low_x + (upper - low_y) * lower_slope
                elif upper > mid_y:
                    current_short = mid_x + (upper - mid_y) * upper_slope
                else:
                    current_short = mid_x

            minimum = maximum = previous_long
            if previous_short < minimum:
                minimum = previous_short
            elif previous_short > maximum:
                maximum = previous_short
            if current_long < minimum:
                minimum = current_long
            elif current_long > maximum:
                maximum = current_long
            if current_short < minimum:
                minimum = current_short
            elif current_short > maximum:
                maximum = current_short

            # The middle vertex is the only extremum that is not on a band
            # edge, so a row that straddles it has to take it into account.
            if row < mid_y < upper:
                if mid_x < minimum:
                    minimum = mid_x
                elif mid_x > maximum:
                    maximum = mid_x

            previous_long = current_long
            previous_short = current_short

            if not minimum < maximum:
                continue
            start = floor(minimum)
            stop = ceil(maximum)
            if start >= stop:
                continue
            emitted_runs += 1
            if emitted_runs > max_run_emissions:
                raise RasterBudgetExceeded("run_emissions", max_run_emissions)
            emitted.append((row, start, stop))

    rows, starts, stops = _merge_spans(emitted)
    if margin_texels:
        expanded: list[tuple[int, int, int]] = []
        for row, start, stop in zip(rows, starts, stops):
            for expanded_row in range(row - margin_texels, row + margin_texels + 1):
                emitted_runs += 1
                if emitted_runs > max_run_emissions:
                    raise RasterBudgetExceeded("run_emissions", max_run_emissions)
                expanded.append(
                    (expanded_row, start - margin_texels, stop + margin_texels)
                )
        rows, starts, stops = _merge_spans(expanded)

    union_runs = len(rows)
    covered_texels = sum(stops) - sum(starts)
    return Coverage(
        spans=numpy.array((rows, starts, stops), dtype=numpy.int64),
        stats=RasterStats(
            triangles=triangle_count,
            degenerate_triangles=degenerate_triangles,
            scanlines=scanlines,
            emitted_runs=emitted_runs,
            union_runs=union_runs,
            covered_texels=covered_texels,
        ),
    )


def _segment_starts(counts: numpy.ndarray) -> numpy.ndarray:
    """Index of each segment's first element in the concatenated array."""
    return numpy.concatenate((numpy.zeros(1, dtype=numpy.int64), numpy.cumsum(counts)))[
        :-1
    ]


def _within_segment(values: numpy.ndarray, counts: numpy.ndarray) -> numpy.ndarray:
    """Running total of `values`, restarting at every segment boundary."""
    if values.shape[0] == 0:
        return values.astype(numpy.int64, copy=False)
    starts = _segment_starts(counts)
    total = numpy.cumsum(values)
    before = numpy.where(starts > 0, total[starts - 1], 0)
    return total - numpy.repeat(before, counts)


def _first_trip(
    tripped: numpy.ndarray,
    polygon: numpy.ndarray,
    position: numpy.ndarray,
    polygon_count: int,
) -> numpy.ndarray:
    """Position of each polygon's earliest tripped element, or a large sentinel.

    Only reached when a budget actually trips, which is a pathological input;
    the unbuffered scatter it uses is not worth paying for on every batch.
    """
    sentinel = position.shape[0] + 1
    result = numpy.full(polygon_count, sentinel, dtype=numpy.int64)
    numpy.minimum.at(result, polygon[tripped], position[tripped])
    return result


def _merge_batch(
    polygon: numpy.ndarray,
    row: numpy.ndarray,
    start: numpy.ndarray,
    stop: numpy.ndarray,
    polygon_count: int,
) -> tuple[numpy.ndarray, numpy.ndarray]:
    """Union overlapping runs inside every (polygon, row) group at once.

    Returns the merged `(3, n)` span array in polygon order and the per-polygon
    run count. The scalar path sorts each polygon separately; one ordering of
    everything is equivalent because the polygon index leads the sort key.
    """
    if start.shape[0] == 0:
        return (
            numpy.zeros((3, 0), dtype=numpy.int64),
            numpy.zeros(polygon_count, dtype=numpy.int64),
        )
    # One composite key beats a three-key lexsort by about 10x. The widths come
    # from the observed ranges; a batch too spread out to pack falls back.
    row_low, start_low = int(row.min()), int(start.min())
    row_bits = int(row.max() - row_low).bit_length()
    start_bits = int(start.max() - start_low).bit_length()
    if polygon_count.bit_length() + row_bits + start_bits <= 62:
        key = (
            (polygon << (row_bits + start_bits))
            | ((row - row_low) << start_bits)
            | (start - start_low)
        )
        order = numpy.argsort(key, kind="stable")
    else:
        order = numpy.lexsort((start, row, polygon))
    polygon, row, start, stop = polygon[order], row[order], start[order], stop[order]

    group = numpy.empty(start.shape[0], dtype=numpy.int64)
    group[0] = 0
    numpy.cumsum((polygon[1:] != polygon[:-1]) | (row[1:] != row[:-1]), out=group[1:])
    # Segmented running maximum of `stop`: offsetting each group past the last
    # makes one global accumulate equivalent to a per-group one.
    span = int(stop.max() - stop.min()) + 1
    running = numpy.maximum.accumulate(stop + group * span) - group * span

    opens = numpy.empty(start.shape[0], dtype=bool)
    opens[0] = True
    opens[1:] = (group[1:] != group[:-1]) | (start[1:] > running[:-1])
    # A merged run ends at the running maximum reached just before the next opens.
    closes = numpy.empty(start.shape[0], dtype=bool)
    closes[:-1] = opens[1:]
    closes[-1] = True

    spans = numpy.array(
        (row[opens], start[opens], running[closes]), dtype=numpy.int64
    )
    return spans, numpy.bincount(polygon[opens], minlength=polygon_count)


def _rasterize_live(
    xs: numpy.ndarray,
    ys: numpy.ndarray,
    triangle_polygon: numpy.ndarray,
    polygon_count: int,
    *,
    margin_texels: int,
    max_scanlines: int,
    max_run_emissions: int,
    reasons: dict[int, str],
) -> tuple[numpy.ndarray, numpy.ndarray, tuple[numpy.ndarray, ...]]:
    """Scanline pass and merge for every non-degenerate triangle at once.

    Records budget failures in `reasons` and drops those polygons, so the merge
    only sees polygons that will produce a coverage.
    """
    live_counts = numpy.bincount(triangle_polygon, minlength=polygon_count)

    # Stable sort by height, matching `sorted(triangle, key=_height)`.
    order = numpy.argsort(ys, axis=1, kind="stable")
    index = numpy.arange(ys.shape[0])[:, None]
    ys, xs = ys[index, order], xs[index, order]
    low_x, mid_x, high_x = xs[:, 0], xs[:, 1], xs[:, 2]
    low_y, mid_y, high_y = ys[:, 0], ys[:, 1], ys[:, 2]

    first_row = numpy.floor(low_y)
    row_count = numpy.maximum(0.0, numpy.ceil(high_y) - first_row).astype(numpy.int64)
    scanlines = numpy.bincount(
        triangle_polygon, weights=row_count, minlength=polygon_count
    ).astype(numpy.int64)

    long_slope = (high_x - low_x) / (high_y - low_y)
    has_lower = mid_y > low_y
    has_upper = high_y > mid_y
    lower_slope = numpy.where(
        has_lower, (mid_x - low_x) / numpy.where(has_lower, mid_y - low_y, 1.0), 0.0
    )
    upper_slope = numpy.where(
        has_upper, (high_x - mid_x) / numpy.where(has_upper, high_y - mid_y, 1.0), 0.0
    )

    # One entry per (triangle, scanline).
    triangle_of_row = numpy.repeat(numpy.arange(row_count.shape[0]), row_count)
    total = triangle_of_row.shape[0]
    # Trailing slice, not a leading one, so an all-degenerate batch stays empty.
    offsets = numpy.concatenate(
        (numpy.zeros(1, dtype=numpy.int64), numpy.cumsum(row_count))
    )[:-1]
    row = (
        numpy.arange(total)
        - numpy.repeat(offsets, row_count)
        + numpy.repeat(first_row, row_count)
    )

    t = triangle_of_row
    t_low_x, t_low_y = low_x[t], low_y[t]
    t_mid_x, t_mid_y = mid_x[t], mid_y[t]
    t_high_x, t_high_y = high_x[t], high_y[t]
    t_long, t_lower, t_upper = long_slope[t], lower_slope[t], upper_slope[t]
    never = numpy.zeros(total, dtype=bool)

    def long_at(y, at_low, at_high):
        result = t_low_x + (y - t_low_y) * t_long
        result = numpy.where(at_low, t_low_x, result)
        return numpy.where(at_high, t_high_x, result)

    def short_at(y, at_low, at_high):
        below = t_low_x + (y - t_low_y) * t_lower
        above = t_mid_x + (y - t_mid_y) * t_upper
        result = numpy.where(
            y < t_mid_y, below, numpy.where(y > t_mid_y, above, t_mid_x)
        )
        result = numpy.where(
            at_low, numpy.where(t_mid_y == t_low_y, t_mid_x, t_low_x), result
        )
        return numpy.where(
            at_high, numpy.where(t_mid_y == t_high_y, t_mid_x, t_high_x), result
        )

    # The scalar loop carries the previous row's cross-sections forward. That is
    # not a real recurrence: it is the value at the band's lower boundary, which
    # is the bottom vertex on a triangle's first row and the scanline elsewhere.
    is_first = row == numpy.repeat(first_row, row_count)
    lower_y = numpy.where(is_first, t_low_y, row)
    previous_long = long_at(lower_y, is_first, never)
    previous_short = short_at(lower_y, is_first, never)

    upper = row + 1.0
    at_top = upper >= t_high_y
    upper_y = numpy.where(at_top, t_high_y, upper)
    current_long = long_at(upper_y, never, at_top)
    current_short = short_at(upper_y, never, at_top)

    # The scalar chain of if/elif is a plain min and max of the four values: a
    # value under the running minimum is necessarily under the running maximum.
    minimum = numpy.minimum(
        numpy.minimum(previous_long, previous_short),
        numpy.minimum(current_long, current_short),
    )
    maximum = numpy.maximum(
        numpy.maximum(previous_long, previous_short),
        numpy.maximum(current_long, current_short),
    )
    # The middle vertex is the only extremum off a band edge. The scalar loop
    # reassigns `upper` to `high_y` on the last band, so this uses the clamp.
    straddles = (row < t_mid_y) & (t_mid_y < upper_y)
    minimum = numpy.where(straddles, numpy.minimum(minimum, t_mid_x), minimum)
    maximum = numpy.where(straddles, numpy.maximum(maximum, t_mid_x), maximum)

    keep = minimum < maximum
    start = numpy.floor(minimum[keep]).astype(numpy.int64)
    stop = numpy.ceil(maximum[keep]).astype(numpy.int64)
    nonempty = start < stop
    start, stop = start[nonempty], stop[nonempty]
    run_triangle = triangle_of_row[keep][nonempty]
    run_row = row[keep][nonempty].astype(numpy.int64)
    run_polygon = triangle_polygon[run_triangle]

    runs_per_triangle = numpy.bincount(run_triangle, minlength=row_count.shape[0])
    emitted = numpy.bincount(
        triangle_polygon, weights=runs_per_triangle, minlength=polygon_count
    ).astype(numpy.int64)

    over_scanlines = _within_segment(row_count, live_counts) > max_scanlines
    over_runs = _within_segment(runs_per_triangle, live_counts) > max_run_emissions
    if over_scanlines.any() or over_runs.any():
        # The scalar loop checks the scanline budget for a triangle before
        # emitting any of its runs, so an equal trip position reports scanlines.
        position = numpy.arange(triangle_polygon.shape[0]) - numpy.repeat(
            _segment_starts(live_counts), live_counts
        )
        first_scanline = _first_trip(
            over_scanlines, triangle_polygon, position, polygon_count
        )
        first_run = _first_trip(over_runs, triangle_polygon, position, polygon_count)
        for polygon in numpy.flatnonzero(
            numpy.minimum(first_scanline, first_run) <= position.shape[0]
        ):
            reasons[int(polygon)] = (
                "BUDGET_SCANLINES"
                if first_scanline[polygon] <= first_run[polygon]
                else "BUDGET_RUN_EMISSIONS"
            )

    if reasons:
        alive = ~numpy.isin(
            run_polygon,
            numpy.fromiter(reasons, dtype=numpy.int64, count=len(reasons)),
        )
        run_polygon, run_row = run_polygon[alive], run_row[alive]
        start, stop = start[alive], stop[alive]

    spans, per_polygon = _merge_batch(
        run_polygon, run_row, start, stop, polygon_count
    )
    if margin_texels:
        spans, per_polygon, emitted = _expand_margin(
            spans,
            per_polygon,
            emitted,
            polygon_count,
            margin_texels=margin_texels,
            max_run_emissions=max_run_emissions,
            reasons=reasons,
        )

    covered = numpy.bincount(
        numpy.repeat(numpy.arange(polygon_count), per_polygon),
        weights=spans[2] - spans[1],
        minlength=polygon_count,
    ).astype(numpy.int64)
    return spans, per_polygon, (scanlines, emitted, covered)


def _expand_margin(
    spans: numpy.ndarray,
    per_polygon: numpy.ndarray,
    emitted: numpy.ndarray,
    polygon_count: int,
    *,
    margin_texels: int,
    max_run_emissions: int,
    reasons: dict[int, str],
) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    """Widen every merged run and union again, as the scalar tail does."""
    rows_per_run = 2 * margin_texels + 1
    emitted = emitted + per_polygon * rows_per_run
    over = emitted > max_run_emissions
    if over.any():
        for polygon in numpy.flatnonzero(over):
            reasons.setdefault(int(polygon), "BUDGET_RUN_EMISSIONS")
        keep = ~numpy.repeat(over, per_polygon)
        spans = spans[:, keep]
        per_polygon = numpy.where(over, 0, per_polygon)

    run_polygon = numpy.repeat(numpy.arange(polygon_count), per_polygon)
    offsets = numpy.tile(
        numpy.arange(-margin_texels, margin_texels + 1), spans.shape[1]
    )
    return (
        *_merge_batch(
            numpy.repeat(run_polygon, rows_per_run),
            numpy.repeat(spans[0], rows_per_run) + offsets,
            numpy.repeat(spans[1], rows_per_run) - margin_texels,
            numpy.repeat(spans[2], rows_per_run) + margin_texels,
            polygon_count,
        ),
        emitted,
    )


def rasterize_batch(
    triangles: numpy.ndarray,
    counts: numpy.ndarray,
    *,
    margin_texels: int = 0,
    max_scanlines: int = 1_000_000,
    max_run_emissions: int = 2_000_000,
) -> list[Coverage | str]:
    """Union triangle coverage for many original polygons in one pass.

    `triangles` is `(T, 3, 2)` float64 already in texel-edge space; `counts`
    gives the consecutive triangles belonging to each polygon. Each entry of the
    result is that polygon's `Coverage`, or the unsupported reason string the
    single-polygon path would have raised for it.

    `rasterize_polygon` remains the authority. This reproduces it exactly, which
    is what `BatchedRasterizationTests` asserts, and is worth having only because
    a real mesh rasterizes tens of thousands of polygons per analysis.
    """
    if margin_texels < 0:
        raise ValueError("margin_texels cannot be negative")
    if max_scanlines <= 0 or max_run_emissions <= 0:
        raise ValueError("raster budgets must be positive")

    polygon_count = int(counts.shape[0])
    if polygon_count == 0:
        return []
    counts = counts.astype(numpy.int64, copy=False)
    triangle_polygon = numpy.repeat(numpy.arange(polygon_count), counts)
    reasons: dict[int, str] = {}

    # Non-finite UV coordinates fail the whole polygon, as `_validate_triangle`
    # does, and are dropped here so they cannot poison the shared arithmetic.
    finite = numpy.isfinite(triangles).all(axis=(1, 2))
    if not finite.all():
        for index in numpy.flatnonzero(
            numpy.bincount(triangle_polygon[~finite], minlength=polygon_count)
        ):
            reasons[int(index)] = "INVALID_UV"
        keep_triangle = finite & ~numpy.isin(
            triangle_polygon, numpy.fromiter(reasons, dtype=numpy.int64, count=len(reasons))
        )
        triangles = triangles[keep_triangle]
        triangle_polygon = triangle_polygon[keep_triangle]
        counts = numpy.bincount(triangle_polygon, minlength=polygon_count)

    xs = triangles[:, :, 0]
    ys = triangles[:, :, 1]
    ax, ay = xs[:, 0], ys[:, 0]
    bx, by = xs[:, 1], ys[:, 1]
    cx, cy = xs[:, 2], ys[:, 2]
    live = ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) != 0.0
    degenerate_per_polygon = numpy.bincount(
        triangle_polygon[~live], minlength=polygon_count
    )

    spans, per_polygon, stats = _rasterize_live(
        xs[live],
        ys[live],
        triangle_polygon[live],
        polygon_count,
        margin_texels=margin_texels,
        max_scanlines=max_scanlines,
        max_run_emissions=max_run_emissions,
        reasons=reasons,
    )

    scanlines, emitted, covered = stats
    results: list[Coverage | str] = []
    offset = 0
    for index in range(polygon_count):
        width = int(per_polygon[index])
        piece = spans[:, offset : offset + width]
        offset += width
        reason = reasons.get(index)
        if reason is not None:
            results.append(reason)
            continue
        results.append(
            Coverage(
                # A view, not a copy. The parent array lives as long as the
                # coverages built from it, which is bounded by the batch size.
                spans=piece,
                stats=RasterStats(
                    triangles=int(counts[index]),
                    degenerate_triangles=int(degenerate_per_polygon[index]),
                    scanlines=int(scanlines[index]),
                    emitted_runs=int(emitted[index]),
                    union_runs=width,
                    covered_texels=int(covered[index]),
                ),
            )
        )
    return results


def uv_to_texel_edge(uv: Sequence[float], width: int, height: int) -> Point:
    if width <= 0 or height <= 0:
        raise InvalidRasterInput("image dimensions must be positive")
    if len(uv) != 2 or not all(math.isfinite(float(value)) for value in uv):
        raise InvalidRasterInput("UV coordinates must be two finite values")
    return (float(uv[0]) * width, float(uv[1]) * height)
