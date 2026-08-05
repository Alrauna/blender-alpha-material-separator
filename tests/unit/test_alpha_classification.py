# SPDX-License-Identifier: GPL-3.0-or-later
"""Addressing and classification contract tests."""

from __future__ import annotations

import unittest

from addon.core import (
    AddressMode,
    AlphaGrid,
    AnalysisSettings,
    FaceClass,
    classify_polygon,
    uv_to_texel_edge,
)

SQUARE = (
    ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0)),
    ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
)


class AlphaAddressingTests(unittest.TestCase):
    def setUp(self):
        self.grid = AlphaGrid(2, 2, (False, True, True, False))

    def test_repeat(self):
        self.assertEqual(self.grid.count_run(0, -2, 4, AddressMode.REPEAT), 3)

    def test_mirror(self):
        self.assertEqual(self.grid.count_run(0, -2, 6, AddressMode.MIRROR), 4)

    def test_extend(self):
        self.assertEqual(self.grid.count_run(0, -2, 4, AddressMode.EXTEND), 3)

    def test_clip_outside_is_transparent(self):
        self.assertEqual(self.grid.count_run(0, -2, 4, AddressMode.CLIP), 5)
        self.assertEqual(self.grid.count_run(-1, -2, 4, AddressMode.CLIP), 6)

    def test_threshold_is_strictly_below(self):
        grid = AlphaGrid.from_alpha_values(2, 1, (0.998, 0.999), threshold=0.999)
        self.assertEqual(grid.affected, bytes((True, False)))


class ClassificationTests(unittest.TestCase):
    def test_uvs_outside_zero_one_sample_with_image_addressing(self):
        grid = AlphaGrid(2, 1, (False, True))

        def square(u0, u1, v0, v1):
            uv_triangles = (
                ((u0, v0), (u1, v0), (u1, v1)),
                ((u0, v0), (u1, v1), (u0, v1)),
            )
            return tuple(
                tuple(uv_to_texel_edge(point, grid.width, grid.height) for point in triangle)
                for triangle in uv_triangles
            )

        cases = (
            (AddressMode.REPEAT, square(2.0, 2.5, -1.0, 0.0), FaceClass.OPAQUE),
            (AddressMode.REPEAT, square(-1.5, -1.0, 2.0, 3.0), FaceClass.ALPHA_AFFECTED),
            (AddressMode.EXTEND, square(2.0, 2.5, 2.0, 3.0), FaceClass.ALPHA_AFFECTED),
            (AddressMode.CLIP, square(-1.5, -1.0, -2.0, -1.0), FaceClass.ALPHA_AFFECTED),
            (AddressMode.MIRROR, square(1.0, 1.5, 2.0, 3.0), FaceClass.ALPHA_AFFECTED),
        )
        for mode, triangles, expected in cases:
            with self.subTest(mode=mode, expected=expected):
                result = classify_polygon(triangles, grid, address_mode=mode)
                self.assertEqual(result.classification, expected)
                self.assertNotEqual(result.classification, FaceClass.UNSUPPORTED)

    def test_opaque(self):
        result = classify_polygon(SQUARE, AlphaGrid(2, 2, (False,) * 4))
        self.assertEqual(result.classification, FaceClass.OPAQUE)
        self.assertEqual((result.covered_texels, result.affected_texels), (4, 0))

    def test_fully_affected(self):
        result = classify_polygon(SQUARE, AlphaGrid(2, 2, (True,) * 4))
        self.assertEqual(result.classification, FaceClass.ALPHA_AFFECTED)
        self.assertEqual((result.affected_texels, result.opaque_texels), (4, 0))

    def test_mixed(self):
        result = classify_polygon(SQUARE, AlphaGrid(2, 2, (True, False, False, False)))
        self.assertEqual(result.classification, FaceClass.MIXED)
        self.assertEqual(result.affected_fraction, 0.25)

    def test_suppressed_retains_evidence_and_failed_gates(self):
        settings = AnalysisSettings(
            min_affected_texels=2,
            min_affected_fraction=0.5,
        )
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=settings,
        )
        self.assertEqual(result.classification, FaceClass.SUPPRESSED)
        self.assertEqual(result.affected_texels, 1)
        self.assertEqual(result.unsuppressed_shape, FaceClass.MIXED)
        self.assertEqual(
            result.failed_gates,
            ("MIN_AFFECTED_TEXELS", "MIN_AFFECTED_FRACTION"),
        )

    def test_degenerate_uv_is_unsupported(self):
        result = classify_polygon(
            (((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),),
            AlphaGrid(1, 1, (False,)),
        )
        self.assertEqual(result.classification, FaceClass.UNSUPPORTED)
        self.assertEqual(result.unsupported_reason, "NO_POSITIVE_AREA_UV_COVERAGE")

    def test_budget_failure_is_unsupported_not_approximate(self):
        settings = AnalysisSettings(max_scanlines=2)
        result = classify_polygon(
            (((0.0, 0.0), (1.0, 0.0), (0.0, 3.0)),),
            AlphaGrid(1, 1, (False,)),
            settings=settings,
        )
        self.assertEqual(result.classification, FaceClass.UNSUPPORTED)
        self.assertEqual(result.unsupported_reason, "BUDGET_SCANLINES")

    def test_affected_count_equal_to_minimum_is_not_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_texels=1),
        )
        self.assertEqual(result.classification, FaceClass.MIXED)
        self.assertEqual(result.failed_gates, ())

    def test_affected_count_below_minimum_is_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_texels=2),
        )
        self.assertEqual(result.classification, FaceClass.SUPPRESSED)
        self.assertEqual(result.failed_gates, ("MIN_AFFECTED_TEXELS",))

    def test_affected_fraction_equal_to_minimum_is_not_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_fraction=0.25),
        )
        self.assertEqual(result.classification, FaceClass.MIXED)
        self.assertEqual(result.failed_gates, ())

    def test_affected_fraction_below_minimum_is_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_fraction=0.26),
        )
        self.assertEqual(result.classification, FaceClass.SUPPRESSED)
        self.assertEqual(result.failed_gates, ("MIN_AFFECTED_FRACTION",))

    def test_texel_minimums_of_zero_and_one_never_suppress(self):
        # A face with no affected texels returns OPAQUE before the gates run,
        # so affected is always at least one here. Both values are no-ops.
        for minimum in (0, 1):
            with self.subTest(minimum=minimum):
                result = classify_polygon(
                    SQUARE,
                    AlphaGrid(2, 2, (True, False, False, False)),
                    settings=AnalysisSettings(min_affected_texels=minimum),
                )
                self.assertEqual(result.classification, FaceClass.MIXED)
                self.assertEqual(result.failed_gates, ())

    def test_margin_expands_coverage_and_can_reclassify_a_face(self):
        centre = tuple(
            1 <= x <= 2 and 1 <= y <= 2
            for y in range(4)
            for x in range(4)
        )
        grid = AlphaGrid(4, 4, centre)
        face = (
            ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0)),
            ((1.0, 1.0), (3.0, 3.0), (1.0, 3.0)),
        )

        exact = classify_polygon(face, grid, settings=AnalysisSettings())
        self.assertEqual(exact.classification, FaceClass.ALPHA_AFFECTED)
        self.assertEqual(exact.covered_texels, 4)
        self.assertEqual(exact.affected_fraction, 1.0)

        expanded = classify_polygon(
            face, grid, settings=AnalysisSettings(margin_texels=1)
        )
        self.assertEqual(expanded.classification, FaceClass.MIXED)
        self.assertEqual(expanded.covered_texels, 16)
        self.assertEqual(expanded.affected_texels, 4)
        self.assertEqual(expanded.affected_fraction, 0.25)


if __name__ == "__main__":
    unittest.main()
