# SPDX-License-Identifier: GPL-3.0-or-later
"""Correctness tests for exact positive-area rasterization."""

from __future__ import annotations

import math
import random
import unittest
import unittest.mock

import numpy

from addon.core import raster
from addon.core import (
    InvalidRasterInput,
    RasterBudgetExceeded,
    rasterize_batch,
    rasterize_polygon,
    uv_to_texel_edge,
)


def _clip_axis(polygon, axis, boundary, keep_above):
    if not polygon:
        return []
    result = []

    def inside(point):
        return point[axis] >= boundary if keep_above else point[axis] <= boundary

    previous = polygon[-1]
    previous_inside = inside(previous)
    for current in polygon:
        current_inside = inside(current)
        if current_inside != previous_inside:
            delta = current[axis] - previous[axis]
            if delta:
                scale = (boundary - previous[axis]) / delta
                result.append(
                    (
                        previous[0] + scale * (current[0] - previous[0]),
                        previous[1] + scale * (current[1] - previous[1]),
                    )
                )
        if current_inside:
            result.append(current)
        previous = current
        previous_inside = current_inside
    return result


def _positive_area_in_cell(triangle, x, y):
    polygon = list(triangle)
    polygon = _clip_axis(polygon, 0, x, True)
    polygon = _clip_axis(polygon, 0, x + 1, False)
    polygon = _clip_axis(polygon, 1, y, True)
    polygon = _clip_axis(polygon, 1, y + 1, False)
    if len(polygon) < 3:
        return False
    area2 = sum(
        first[0] * second[1] - first[1] * second[0]
        for first, second in zip(polygon, polygon[1:] + polygon[:1])
    )
    return abs(area2) > 1e-10


def _oracle_cells(triangle):
    start_x = math.floor(min(point[0] for point in triangle))
    stop_x = math.ceil(max(point[0] for point in triangle))
    start_y = math.floor(min(point[1] for point in triangle))
    stop_y = math.ceil(max(point[1] for point in triangle))
    return {
        (x, y)
        for y in range(start_y, stop_y)
        for x in range(start_x, stop_x)
        if _positive_area_in_cell(triangle, x, y)
    }


def _coverage_cells(coverage):
    return {
        (x, int(row))
        for row, start, stop in zip(coverage.rows, coverage.starts, coverage.stops)
        for x in range(start, stop)
    }


_HUGE = 1.0e7
# `exact` marks the cases whose areas stay far enough above the oracle's own
# 1e-10 area epsilon for equality to be a meaningful assertion.
_ADVERSARIAL_CASES = {
    "vertices on texel boundaries": (
        ((0.0, 0.0), (3.0, 0.0), (0.0, 3.0)), True),
    "negative vertices on boundaries": (
        ((-2.0, -2.0), (2.0, -2.0), (-2.0, 2.0)), True),
    "horizontal edge on a boundary": (
        ((1.0, 2.0), (5.0, 2.0), (3.0, 4.5)), True),
    "vertical edge on a boundary": (
        ((2.0, 1.0), (2.0, 5.0), (4.5, 3.0)), True),
    "flat bottom": (((0.5, 1.0), (3.5, 1.0), (2.0, 4.25)), True),
    "flat top": (((0.5, 4.0), (3.5, 4.0), (2.0, 1.25)), True),
    "middle vertex on an integer row": (
        ((0.0, 0.0), (1.0, 2.0), (4.0, 5.0)), True),
    "middle vertex inside a band": (
        ((0.0, 0.0), (5.0, 2.5), (1.0, 5.0)), True),
    "near-horizontal edge": (
        ((0.0, 1.0), (10.0, 1.0 + 1.0e-9), (5.0, 3.0)), True),
    "near-horizontal sliver": (
        ((0.0, 1.0), (10.0, 1.0 + 1.0e-9), (5.0, 1.0 + 2.0e-9)), False),
    "near-vertical edge": (
        ((1.0, 0.0), (1.0 + 1.0e-9, 10.0), (3.0, 5.0)), True),
    "near-vertical sliver": (
        ((1.0, 0.0), (1.0 + 1.0e-9, 10.0), (1.0 + 2.0e-9, 5.0)), False),
    "sub-texel triangle": (((0.1, 0.1), (0.2, 0.1), (0.1, 0.2)), True),
    "sub-texel on a corner": (
        ((2.5, 2.5), (2.5001, 2.5), (2.5, 2.5001)), True),
    "sub-texel straddling a boundary": (
        (
            (1.0 - 1.0e-9, 1.0 - 1.0e-9),
            (1.0 + 1.0e-9, 1.0 - 1.0e-9),
            (1.0, 1.0 + 1.0e-9),
        ),
        False,
    ),
    "collinear degenerate": (((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)), True),
    "duplicated vertex degenerate": (
        ((1.0, 1.0), (1.0, 1.0), (3.0, 3.0)), True),
    "single point degenerate": (((2.0, 2.0), (2.0, 2.0), (2.0, 2.0)), True),
    "horizontal degenerate": (((0.0, 2.0), (4.0, 2.0), (7.0, 2.0)), True),
    "edge-only contact": (((2.0, 0.0), (2.0, 2.0), (4.0, 1.0)), True),
    "point-only contact at a corner": (
        ((2.0, 2.0), (4.0, 3.0), (3.0, 5.0)), True),
    "negative UVs": (((-3.5, -2.25), (-0.5, -3.75), (-1.25, -0.5)), True),
    "tiled UVs spanning many texels": (
        ((-4.5, -4.5), (12.5, 3.25), (3.0, 14.75)), True),
    "large accepted coordinates": (
        ((8192.0, 4096.0), (8195.5, 4096.25), (8193.0, 4099.0)), True),
    "coordinates near internal limits": (
        ((_HUGE, _HUGE), (_HUGE + 2.5, _HUGE), (_HUGE, _HUGE + 3.25)), False),
    "limits with sub-ulp spacing": (
        (
            (_HUGE, _HUGE),
            (math.nextafter(_HUGE, math.inf), _HUGE + 4.0),
            (_HUGE + 3.0, _HUGE + 2.0),
        ),
        False,
    ),
}


def _randomized_quads(count):
    random_source = random.Random(0xB0A7)
    for _ in range(count):
        corners = [
            (random_source.randint(-20, 20) / 4, random_source.randint(-20, 20) / 4)
            for _corner in range(4)
        ]
        yield (
            (corners[0], corners[1], corners[2]),
            (corners[0], corners[2], corners[3]),
        )


class RasterizationTests(unittest.TestCase):
    def test_texel_edge_mapping(self):
        self.assertEqual(uv_to_texel_edge((0.25, -0.5), 8, 4), (2.0, -2.0))

    def test_boundary_touch_has_no_extra_cell(self):
        triangle = ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0))
        coverage = rasterize_polygon((triangle,))
        self.assertEqual(_coverage_cells(coverage), {(0, 0), (1, 0), (0, 1)})

    def test_polygon_triangle_union_deduplicates_cells(self):
        triangles = (
            ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0)),
            ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
        )
        coverage = rasterize_polygon(triangles)
        self.assertEqual(_coverage_cells(coverage), {(0, 0), (1, 0), (0, 1), (1, 1)})
        self.assertEqual(coverage.stats.covered_texels, 4)

    def test_margin_is_applied_after_union(self):
        triangles = (
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
            ((0.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        )
        coverage = rasterize_polygon(triangles, margin_texels=1)
        self.assertEqual(
            _coverage_cells(coverage),
            {(x, y) for y in range(-1, 2) for x in range(-1, 2)},
        )

    def test_degenerate_triangle_emits_no_cells(self):
        coverage = rasterize_polygon((((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),))
        self.assertEqual(coverage.spans.shape, (3, 0))
        self.assertEqual(coverage.stats.degenerate_triangles, 1)

    def test_scanline_and_run_budgets_raise(self):
        tall = (((0.0, 0.0), (1.0, 0.0), (0.0, 10.0)),)
        with self.assertRaises(RasterBudgetExceeded) as scanlines:
            rasterize_polygon(tall, max_scanlines=9)
        self.assertEqual(scanlines.exception.budget, "scanlines")
        with self.assertRaises(RasterBudgetExceeded) as runs:
            rasterize_polygon(tall, max_run_emissions=5)
        self.assertEqual(runs.exception.budget, "run_emissions")

    def test_fixed_seed_randomized_against_clipping_oracle(self):
        random_source = random.Random(0xA17A)
        compared = 0
        for _ in range(500):
            triangle = tuple(
                (
                    random_source.randint(-12, 12) / 4,
                    random_source.randint(-12, 12) / 4,
                )
                for _point in range(3)
            )
            if abs(
                (triangle[1][0] - triangle[0][0])
                * (triangle[2][1] - triangle[0][1])
                - (triangle[1][1] - triangle[0][1])
                * (triangle[2][0] - triangle[0][0])
            ) < 1e-12:
                continue
            compared += 1
            actual = _coverage_cells(rasterize_polygon((triangle,)))
            self.assertEqual(actual, _oracle_cells(triangle), triangle)
        self.assertGreater(compared, 450)

    def _assert_covers_oracle(self, triangle, label="", exact=False):
        """Coverage must never miss a positive-area cell, and stay tight when
        the coordinates are exactly representable."""
        cells = _coverage_cells(rasterize_polygon((triangle,)))
        oracle = _oracle_cells(triangle)
        context = label or repr(triangle)
        self.assertEqual(oracle - cells, set(), f"under-covered {context}")
        if exact:
            self.assertEqual(cells, oracle, context)

    def test_adversarial_cases_cover_the_positive_area_oracle(self):
        for label, (triangle, exact) in _ADVERSARIAL_CASES.items():
            with self.subTest(label):
                self._assert_covers_oracle(triangle, label=label, exact=exact)
                margined = _coverage_cells(
                    rasterize_polygon((triangle,), margin_texels=1)
                )
                plain = _coverage_cells(rasterize_polygon((triangle,)))
                self.assertEqual(plain - margined, set(), f"margin dropped {label}")

    def test_fixed_seed_randomized_cases_never_under_cover(self):
        random_source = random.Random(0x5CA71E)

        def quarter():
            return random_source.randint(-24, 24) / 4

        def boundary_snapped():
            value = float(random_source.randint(-8, 8))
            offset = random_source.choice(
                (0.0, 1.0e-12, -1.0e-12, 1.0e-9, -1.0e-9, 0.5, 1.0e-6)
            )
            return value + offset

        def wide():
            return random_source.uniform(-64.0, 64.0)

        def near_limit():
            return 1.0e7 + random_source.uniform(-4.0, 4.0)

        # Only the quarter grid is exactly representable, so it is the only
        # family where the oracle's area epsilon makes equality meaningful.
        families = ((quarter, True), (boundary_snapped, False), (wide, False),
                    (near_limit, False))
        for index in range(2400):
            axis, exact = families[index % len(families)]
            triangle = tuple((axis(), axis()) for _point in range(3))
            if index % 7 == 0:  # force flat and repeated-vertex configurations
                triangle = (triangle[0], (triangle[1][0], triangle[0][1]), triangle[2])
            self._assert_covers_oracle(triangle, exact=exact)

    def test_fixed_seed_randomized_quads_match_the_oracle(self):
        for triangles in _randomized_quads(400):
            cells = _coverage_cells(rasterize_polygon(triangles))
            oracle = _oracle_cells(triangles[0]) | _oracle_cells(triangles[1])
            self.assertEqual(cells, oracle, triangles)

    def test_results_are_deterministic(self):
        triangles = (
            ((-1.25, 0.1), (4.5, 1.2), (0.25, 3.75)),
            ((0.25, 3.75), (4.5, 1.2), (5.0, 4.0)),
        )
        first = rasterize_polygon(triangles)
        for _ in range(20):
            repeated = rasterize_polygon(triangles)
            self.assertTrue(numpy.array_equal(repeated.spans, first.spans))
            self.assertEqual(repeated.stats, first.stats)


class BatchedRasterizationTests(unittest.TestCase):
    """`rasterize_batch` must equal `rasterize_polygon` polygon for polygon.

    The scalar path stays the authority: it is the one checked against the
    positive-area oracle, so equality with it is the whole correctness argument
    for batching. These compare spans and stats, not just covered cells.
    """

    def _scalar(self, polygons, **kwargs):
        results = []
        for triangles in polygons:
            try:
                results.append(rasterize_polygon(triangles, **kwargs))
            except RasterBudgetExceeded as error:
                results.append(f"BUDGET_{error.budget.upper()}")
            except InvalidRasterInput:
                results.append("INVALID_UV")
        return results

    def _batched(self, polygons, **kwargs):
        counts = numpy.array([len(item) for item in polygons], dtype=numpy.int64)
        flat = [triangle for triangles in polygons for triangle in triangles]
        triangles = numpy.array(flat, dtype=numpy.float64).reshape(len(flat), 3, 2)
        return rasterize_batch(triangles, counts, **kwargs)

    def _assert_batch_matches(self, polygons, **kwargs):
        expected = self._scalar(polygons, **kwargs)
        actual = self._batched(polygons, **kwargs)
        self.assertEqual(len(actual), len(expected))
        for index, (mine, reference) in enumerate(zip(actual, expected)):
            with self.subTest(polygon=index):
                if isinstance(reference, str):
                    self.assertEqual(mine, reference)
                    continue
                self.assertNotIsInstance(mine, str, f"polygon {index} failed")
                self.assertTrue(
                    numpy.array_equal(mine.spans, reference.spans),
                    f"spans differ at polygon {index}",
                )
                self.assertEqual(mine.stats, reference.stats)
        return actual

    def test_batch_matches_the_scalar_path_on_the_adversarial_cases(self):
        polygons = [(triangle,) for triangle, _exact in _ADVERSARIAL_CASES.values()]
        self._assert_batch_matches(polygons)
        self._assert_batch_matches(polygons, margin_texels=1)

    def test_batch_matches_the_scalar_path_on_randomized_quads(self):
        polygons = list(_randomized_quads(400))
        results = self._assert_batch_matches(polygons)
        covered = sum(
            item.stats.covered_texels
            for item in results
            if not isinstance(item, str)
        )
        self.assertGreater(covered, 10_000)

    def test_batch_isolates_a_failing_polygon_from_its_neighbours(self):
        """A budget or invalid-UV failure must not disturb the rest of the batch.

        Scalar rasterization fails one call at a time, so this risk only exists
        once polygons share a pass.
        """
        healthy = (((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)),)
        tall = (((0.0, 0.0), (1.0, 0.0), (0.0, 40.0)),)
        infinite = (((0.0, 0.0), (float("inf"), 0.0), (0.0, 2.0)),)
        polygons = [healthy, tall, healthy, infinite, healthy]
        results = self._assert_batch_matches(
            polygons, max_scanlines=20, max_run_emissions=100
        )
        self.assertEqual(results[1], "BUDGET_SCANLINES")
        self.assertEqual(results[3], "INVALID_UV")
        for position in (0, 2, 4):
            self.assertEqual(_coverage_cells(results[position]), {(0, 0), (1, 0), (0, 1)})

        run_limited = self._batched(
            [healthy, tall, healthy], max_run_emissions=5
        )
        self.assertEqual(run_limited[1], "BUDGET_RUN_EMISSIONS")
        self.assertEqual(_coverage_cells(run_limited[0]), {(0, 0), (1, 0), (0, 1)})

    def test_batch_applies_the_margin_after_the_union(self):
        quad = (
            ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
            ((0.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        )
        results = self._assert_batch_matches([quad], margin_texels=1)
        self.assertEqual(
            _coverage_cells(results[0]),
            {(x, y) for y in range(-1, 2) for x in range(-1, 2)},
        )
        # The margin expansion emits runs of its own and stays under the budget.
        self.assertGreater(results[0].stats.emitted_runs, 3)
        self.assertEqual(
            self._batched([quad], margin_texels=1, max_run_emissions=4)[0],
            "BUDGET_RUN_EMISSIONS",
        )

    def test_batch_handles_empty_and_all_degenerate_input(self):
        degenerate = (((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),)
        empty = rasterize_batch(
            numpy.zeros((0, 3, 2), dtype=numpy.float64),
            numpy.zeros(0, dtype=numpy.int64),
        )
        self.assertEqual(empty, [])
        results = self._assert_batch_matches([degenerate, degenerate])
        for item in results:
            self.assertEqual(item.spans.shape, (3, 0))
            self.assertEqual(item.stats.degenerate_triangles, 1)

    def test_batch_matches_when_the_composite_sort_key_overflows(self):
        """Far-apart polygons force the lexsort fallback.

        The fast path packs polygon, row and start into one int64. A batch whose
        coordinate ranges do not fit has to fall back and still be exact. The
        magnitude stays well under 2^52 so both triangles are still exact and
        non-degenerate; it is the *spread* between them that overflows the key.
        """
        far = 2.0**30
        polygons = [
            (((0.0, 0.0), (3.0, 0.0), (0.0, 3.0)),),
            (((far, far), (far + 4.0, far), (far, far + 4.0)),),
        ]
        with unittest.mock.patch.object(
            raster.numpy, "lexsort", wraps=numpy.lexsort
        ) as lexsort:
            results = self._assert_batch_matches(polygons)
        self.assertTrue(lexsort.called, "the fast key did not overflow")
        self.assertGreater(results[1].stats.covered_texels, 0)


if __name__ == "__main__":
    unittest.main()
