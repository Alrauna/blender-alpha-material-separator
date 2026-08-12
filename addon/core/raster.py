# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic positive-area UV triangle rasterization."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from operator import itemgetter

from .model import Coverage, InvalidRasterInput, RasterBudgetExceeded, RasterStats

Point = tuple[float, float]
Triangle = tuple[Point, Point, Point]
Run = tuple[int, int]

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


def _merge_runs(runs: Iterable[Run]) -> tuple[Run, ...]:
    ordered = sorted(runs)
    if not ordered:
        return ()
    merged: list[Run] = []
    start, stop = ordered[0]
    for next_start, next_stop in ordered[1:]:
        if next_start <= stop:
            stop = max(stop, next_stop)
        else:
            merged.append((start, stop))
            start, stop = next_start, next_stop
    merged.append((start, stop))
    return tuple(merged)


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

    rows: dict[int, list[Run]] = defaultdict(list)
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
            rows[row].append((start, stop))

    unioned = {row: _merge_runs(runs) for row, runs in rows.items()}
    if margin_texels:
        expanded: dict[int, list[Run]] = defaultdict(list)
        for row in sorted(unioned):
            for start, stop in unioned[row]:
                for expanded_row in range(row - margin_texels, row + margin_texels + 1):
                    emitted_runs += 1
                    if emitted_runs > max_run_emissions:
                        raise RasterBudgetExceeded("run_emissions", max_run_emissions)
                    expanded[expanded_row].append(
                        (start - margin_texels, stop + margin_texels)
                    )
        unioned = {row: _merge_runs(runs) for row, runs in expanded.items()}

    stable_rows = {row: unioned[row] for row in sorted(unioned) if unioned[row]}
    union_runs = sum(len(runs) for runs in stable_rows.values())
    covered_texels = sum(
        stop - start for runs in stable_rows.values() for start, stop in runs
    )
    return Coverage(
        rows=stable_rows,
        stats=RasterStats(
            triangles=triangle_count,
            degenerate_triangles=degenerate_triangles,
            scanlines=scanlines,
            emitted_runs=emitted_runs,
            union_runs=union_runs,
            covered_texels=covered_texels,
        ),
    )


def uv_to_texel_edge(uv: Sequence[float], width: int, height: int) -> Point:
    if width <= 0 or height <= 0:
        raise InvalidRasterInput("image dimensions must be positive")
    if len(uv) != 2 or not all(math.isfinite(float(value)) for value in uv):
        raise InvalidRasterInput("UV coordinates must be two finite values")
    return (float(uv[0]) * width, float(uv[1]) * height)
