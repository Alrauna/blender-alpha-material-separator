# SPDX-License-Identifier: GPL-3.0-or-later
"""Addressing and classification contract tests."""

from __future__ import annotations

import random
import unittest

import numpy

from addon.core import (
    AddressMode,
    AlphaGrid,
    AnalysisSettings,
    FaceClass,
    classify_polygon,
    rasterize_polygon,
    uv_to_texel_edge,
)
from addon.core.alpha import _prefix_rows

SQUARE = (
    ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0)),
    ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0)),
)


def _reference_prefix(values):
    """Arbitrary-precision prefix sums the fixed-width version must reproduce."""
    result = [0]
    total = 0
    for value in values:
        total += int(value)
        result.append(total)
    return result


def _prefix(values):
    """One row's prefix sums out of the row-block builder."""
    block = numpy.frombuffer(values, dtype=numpy.uint8).reshape(1, len(values))
    return _prefix_rows(block)[0].tolist()


def _resolve_index(value, size, mode):
    """Where one virtual coordinate lands, or None outside a clipped image."""
    if mode is AddressMode.CLIP:
        return value if 0 <= value < size else None
    if mode is AddressMode.EXTEND:
        return min(max(value, 0), size - 1)
    if mode is AddressMode.REPEAT:
        return value % size
    position = value % (2 * size)
    return position if position < size else 2 * size - 1 - position


def _oracle_count_run(width, height, affected, row, start, stop, mode):
    """Count one run cell by cell, with no prefix sums involved."""
    resolved_row = _resolve_index(row, height, mode)
    total = 0
    for x in range(start, stop):
        column = _resolve_index(x, width, mode)
        if resolved_row is None or column is None:
            total += 1  # outside a clipped image counts as transparent
        else:
            total += bool(affected[resolved_row * width + column])
    return total


def _iter_runs(coverage):
    """Half-open runs in the flat representation, one triple at a time."""
    return zip(coverage.rows, coverage.starts, coverage.stops)


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

    def test_row_prefix_counting_matches_a_cell_by_cell_oracle(self):
        random_source = random.Random(0xA1FA)
        for width, height in ((1, 1), (1, 5), (5, 1), (2, 3), (7, 4), (64, 3)):
            affected = bytes(
                random_source.randint(0, 1) for _cell in range(width * height)
            )
            grid = AlphaGrid(width, height, affected)
            for mode in AddressMode:
                for _case in range(40):
                    row = random_source.randint(-2 * height - 1, 2 * height + 1)
                    start = random_source.randint(-2 * width - 1, 2 * width + 1)
                    stop = start + random_source.randint(0, 3 * width + 2)
                    self.assertEqual(
                        grid.count_run(row, start, stop, mode),
                        _oracle_count_run(
                            width, height, affected, row, start, stop, mode
                        ),
                        (width, height, mode, row, start, stop, affected),
                    )

    def test_row_prefix_counting_handles_all_on_and_all_off_rows(self):
        for width in (1, 3, 33):
            for filler in (0, 1):
                affected = bytes([filler]) * (width * 2)
                grid = AlphaGrid(width, 2, affected)
                for mode in AddressMode:
                    for row in (-1, 0, 1, 2):
                        for start, stop in ((0, width), (-width, 2 * width), (2, 2)):
                            self.assertEqual(
                                grid.count_run(row, start, stop, mode),
                                _oracle_count_run(
                                    width, 2, affected, row, start, stop, mode
                                ),
                                (width, filler, mode, row, start, stop),
                            )

    def test_prefix_values_match_the_arbitrary_precision_reference(self):
        random_source = random.Random(0x9E3D)
        rows = {
            "empty": b"",
            "single unaffected": bytes((0,)),
            "single affected": bytes((1,)),
            "all unaffected": bytes(1024),
            "all affected": bytes([1]) * 1024,
            "alternating": bytes(index % 2 for index in range(1024)),
            "random": bytes(
                random_source.randint(0, 1) for _cell in range(1024)
            ),
            # An 8K row is the widest the supported image sizes produce; the
            # MIRROR form below doubles it.
            "maximum width": bytes([1]) * 8192,
        }
        for label, values in rows.items():
            with self.subTest(label):
                self.assertEqual(
                    _prefix(values), _reference_prefix(values), label
                )
                mirrored = values + values[::-1]
                self.assertEqual(
                    _prefix(mirrored),
                    _reference_prefix(mirrored),
                    f"{label} mirrored",
                )

    def test_row_prefix_counts_are_plain_integers(self):
        grid = AlphaGrid(4, 2, bytes((1, 0, 1, 1, 0, 0, 1, 0)))
        for mode in AddressMode:
            count = grid.count_run(0, -3, 9, mode)
            self.assertIs(type(count), int, mode)


class BatchedCountingTests(unittest.TestCase):
    """`count_batch` counts a whole step chunk at once.

    Per-polygon counting spends a Python call on each of the millions of runs a
    real mesh produces. The batched form is only worth having if it is exactly
    equal, so every case here is checked against both the per-polygon counter
    and the cell-by-cell oracle.
    """

    def _coverages(self, random_source, width, height, count):
        coverages = []
        for _polygon in range(count):
            def coordinate(size):
                return random_source.randint(-2 * size - 2, 3 * size + 2) / 2

            triangles = tuple(
                tuple(
                    (coordinate(width), coordinate(height)) for _point in range(3)
                )
                for _triangle in range(random_source.randint(1, 2))
            )
            coverages.append(
                rasterize_polygon(triangles, max_scanlines=10_000_000,
                                  max_run_emissions=10_000_000)
            )
        return coverages

    def test_batched_counts_match_per_polygon_and_the_oracle(self):
        random_source = random.Random(0xB47C)
        for width, height in ((1, 1), (3, 5), (7, 4), (16, 16), (64, 3)):
            affected = bytes(
                random_source.randint(0, 1) for _cell in range(width * height)
            )
            grid = AlphaGrid(width, height, affected)
            coverages = self._coverages(random_source, width, height, 12)
            # Guard against the comparison passing because there is nothing to
            # compare: these cases must produce real runs on both sides.
            self.assertGreater(
                sum(one.spans.shape[1] for one in coverages), 20, (width, height)
            )
            for mode in AddressMode:
                with self.subTest(size=(width, height), mode=mode):
                    batched = grid.count_batch(coverages, mode)
                    self.assertEqual(
                        list(batched),
                        [grid.count_coverage(one, mode) for one in coverages],
                    )
                    self.assertEqual(
                        list(batched),
                        [
                            sum(
                                _oracle_count_run(
                                    width, height, affected, row, start, stop, mode
                                )
                                for row, start, stop in _iter_runs(one)
                            )
                            for one in coverages
                        ],
                    )

    def test_batched_counts_survive_empty_and_absent_coverage(self):
        grid = AlphaGrid(4, 2, bytes((1, 0, 1, 1, 0, 0, 1, 0)))
        # A fully degenerate polygon contributes no runs, so the batch has to
        # keep its slot rather than shifting every later polygon's total.
        empty = rasterize_polygon((((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),))
        solid = rasterize_polygon((((0.0, 0.0), (4.0, 0.0), (0.0, 2.0)),))
        for mode in AddressMode:
            with self.subTest(mode=mode):
                self.assertEqual(
                    list(grid.count_batch((empty, solid, empty), mode)),
                    [0, grid.count_coverage(solid, mode), 0],
                )
        self.assertEqual(list(grid.count_batch((), AddressMode.REPEAT)), [])

    def test_batched_counts_are_plain_integers(self):
        grid = AlphaGrid(4, 2, bytes((1, 0, 1, 1, 0, 0, 1, 0)))
        coverage = rasterize_polygon((((0.0, 0.0), (4.0, 0.0), (0.0, 2.0)),))
        for mode in AddressMode:
            for count in grid.count_batch((coverage,), mode):
                self.assertIs(type(count), int, mode)


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
