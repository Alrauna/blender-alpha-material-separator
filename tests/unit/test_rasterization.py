# SPDX-License-Identifier: GPL-3.0-or-later
"""Correctness tests for exact positive-area rasterization."""

from __future__ import annotations

import math
import random
import unittest

import numpy

from addon.core import RasterBudgetExceeded, rasterize_polygon, uv_to_texel_edge


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
        huge = 1.0e7
        # `exact` marks the cases whose areas stay far enough above the oracle's
        # own 1e-10 area epsilon for equality to be a meaningful assertion.
        cases = {
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
                ((huge, huge), (huge + 2.5, huge), (huge, huge + 3.25)), False),
            "limits with sub-ulp spacing": (
                (
                    (huge, huge),
                    (math.nextafter(huge, math.inf), huge + 4.0),
                    (huge + 3.0, huge + 2.0),
                ),
                False,
            ),
        }
        for label, (triangle, exact) in cases.items():
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
        random_source = random.Random(0xB0A7)
        for _ in range(400):
            corners = [
                (random_source.randint(-20, 20) / 4, random_source.randint(-20, 20) / 4)
                for _corner in range(4)
            ]
            triangles = (
                (corners[0], corners[1], corners[2]),
                (corners[0], corners[2], corners[3]),
            )
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


if __name__ == "__main__":
    unittest.main()
