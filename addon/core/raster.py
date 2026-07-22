# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic positive-area UV triangle rasterization."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence

from .model import Coverage, InvalidRasterInput, RasterBudgetExceeded, RasterStats

Point = tuple[float, float]
Triangle = tuple[Point, Point, Point]
Run = tuple[int, int]


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


def _clip_y(
    polygon: list[Point], boundary: float, *, keep_above: bool
) -> list[Point]:
    if not polygon:
        return []
    result: list[Point] = []

    def inside(point: Point) -> bool:
        return point[1] >= boundary if keep_above else point[1] <= boundary

    previous = polygon[-1]
    previous_inside = inside(previous)
    for current in polygon:
        current_inside = inside(current)
        if current_inside != previous_inside:
            dy = current[1] - previous[1]
            if dy != 0.0:
                scale = (boundary - previous[1]) / dy
                result.append(
                    (previous[0] + scale * (current[0] - previous[0]), boundary)
                )
        if current_inside:
            result.append(current)
        previous = current
        previous_inside = current_inside
    return result


def _row_run(triangle: Triangle, row: int) -> Run | None:
    polygon = _clip_y(list(triangle), float(row), keep_above=True)
    polygon = _clip_y(polygon, float(row + 1), keep_above=False)
    if len(polygon) < 3:
        return None
    minimum = min(point[0] for point in polygon)
    maximum = max(point[0] for point in polygon)
    if not minimum < maximum:
        return None
    start = math.floor(minimum)
    stop = math.ceil(maximum)
    return (start, stop) if start < stop else None


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

    for raw_triangle in triangles:
        triangle = _validate_triangle(raw_triangle)
        triangle_count += 1
        if _twice_area(triangle) == 0.0:
            degenerate_triangles += 1
            continue
        first_row = math.floor(min(point[1] for point in triangle))
        stop_row = math.ceil(max(point[1] for point in triangle))
        row_count = max(0, stop_row - first_row)
        if scanlines + row_count > max_scanlines:
            raise RasterBudgetExceeded("scanlines", max_scanlines)
        scanlines += row_count
        for row in range(first_row, stop_row):
            run = _row_run(triangle, row)
            if run is None:
                continue
            emitted_runs += 1
            if emitted_runs > max_run_emissions:
                raise RasterBudgetExceeded("run_emissions", max_run_emissions)
            rows[row].append(run)

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
