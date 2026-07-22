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


if __name__ == "__main__":
    unittest.main()
