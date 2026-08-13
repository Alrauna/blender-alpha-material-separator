# SPDX-License-Identifier: GPL-3.0-or-later
"""The GPU kernel against the CPU rasterizer, which is the only oracle here.

Every comparison demands equality. A tolerance would defeat the point: the
kernel exists only because it can reproduce `rasterize_batch` plus `count_batch`
exactly, and a machine where it cannot must fail the probe and fall back rather
than return something close.

These live under `tests/blender/` because they need a GPU context. On a machine
without one they report a skip instead of passing quietly.
"""

from __future__ import annotations

import numpy

from addon.adapters import gpu_raster
from addon.core import AddressMode, AlphaGrid, AnalysisSettings, rasterize_batch

_DEFAULTS = AnalysisSettings()


def _oracle(triangles, counts, grid, mode, *, margin_texels=0):
    coverages = rasterize_batch(triangles, counts, margin_texels=margin_texels)
    assert not any(isinstance(one, str) for one in coverages), coverages
    return (
        numpy.array([one.stats.covered_texels for one in coverages], dtype=numpy.int64),
        numpy.array(grid.count_batch(coverages, mode), dtype=numpy.int64),
    )


def _patterned_grid(width, height, seed):
    generator = numpy.random.default_rng(seed)
    plane = (generator.random((height, width)) < 0.37).astype(numpy.uint8)
    return AlphaGrid(width, height, plane.reshape(-1).tobytes())


def assert_probe_is_total() -> None:
    """`available()` answers, caches, and never lets a failure escape."""
    first = gpu_raster.available()
    assert isinstance(first, bool), type(first)
    assert gpu_raster.available() is first, "probe is not stable across calls"


def assert_modes_cross_edges() -> None:
    """Runs that leave the image on both sides, and rows that leave it too.

    Each mode fails differently outside the image, so the fixture has to leave
    it in every direction: runs longer than a whole period, runs starting at a
    negative multiple of the width, rows above and below, and for MIRROR a run
    long enough to cross the fold more than once.
    """
    grid = _patterned_grid(53, 17, seed=0x5EED)
    quads = []
    counts = []
    for low_x, low_y, high_x, high_y in (
        (-121.5, -40.25, -60.0, -34.5),   # entirely left of the image
        (-30.0, 2.25, 12.75, 9.5),        # straddling the left edge
        (4.0, 1.5, 49.0, 15.25),          # wholly inside
        (30.5, 6.0, 88.25, 13.75),        # straddling the right edge
        (200.0, 30.5, 261.5, 44.0),       # entirely right and below
        (-70.0, -3.0, 190.5, 5.25),       # longer than several whole periods
    ):
        quads.append([[low_x, low_y], [high_x, low_y], [high_x, high_y]])
        quads.append([[low_x, low_y], [high_x, high_y], [low_x, high_y]])
        counts.append(2)
    triangles = numpy.array(quads, dtype=numpy.float64)
    counts = numpy.array(counts, dtype=numpy.int64)

    for mode in AddressMode:
        produced = gpu_raster.counted_batch(
            triangles, counts, grid, mode, settings=_DEFAULTS
        )
        assert produced is not None, f"{mode} batch was refused"
        covered, affected = produced
        want_covered, want_affected = _oracle(triangles, counts, grid, mode)
        assert numpy.array_equal(covered, want_covered), (
            mode, covered, want_covered
        )
        assert numpy.array_equal(affected, want_affected), (
            mode, affected, want_affected
        )


def assert_exact_at_scale() -> None:
    """Thousands of polygons per image, with the realistic tier's UV character.

    Scaled down from the benchmark tier so the headless suite stays quick. What
    matters is preserved: UVs six times the unit square and offset negative, so
    most runs wrap; several image sizes including a non-square one; degenerate
    triangles mixed in; and n-gons, not only quads.
    """
    generator = numpy.random.default_rng(0xA1FA)
    for width, height, polygons in ((512, 512, 3000), (256, 128, 3000), (61, 29, 2000)):
        grid = _patterned_grid(width, height, seed=width * 31 + height)
        # Fan-triangulated convex quads and pentagons, jittered around a centre,
        # then scaled into texel space the way `uv_to_texel_edge` does.
        sides = generator.integers(3, 6, size=polygons)
        counts = (sides - 2).astype(numpy.int64)
        pieces = []
        for polygon, side in enumerate(sides):
            angles = numpy.sort(generator.random(side)) * 2.0 * numpy.pi
            radius = 0.02 + generator.random(side) * 0.9
            centre = generator.random(2) * 6.0 - 1.0
            points = centre + numpy.stack(
                (numpy.cos(angles) * radius, numpy.sin(angles) * radius), axis=1
            )
            points *= (width, height)
            if polygon % 83 == 0:
                # A degenerate triangle has to be dropped, not rasterized.
                points[1] = points[0]
            pieces.extend(
                [points[0], points[index], points[index + 1]]
                for index in range(1, side - 1)
            )
        triangles = numpy.array(pieces, dtype=numpy.float64)

        for mode in AddressMode:
            produced = gpu_raster.counted_batch(
                triangles, counts, grid, mode, settings=_DEFAULTS
            )
            assert produced is not None, f"{width}x{height} {mode} batch was refused"
            covered, affected = produced
            want_covered, want_affected = _oracle(triangles, counts, grid, mode)
            for name, got, want in (
                ("covered", covered, want_covered),
                ("affected", affected, want_affected),
            ):
                differing = int((got != want).sum())
                assert not differing, (
                    f"{width}x{height} {mode}: {differing} of {polygons} {name} "
                    f"counts differ, first at {numpy.flatnonzero(got != want)[:3]}"
                )


def assert_unhandled_inputs_fall_back() -> None:
    """Anything the kernel does not implement returns None rather than guessing."""
    grid = _patterned_grid(64, 32, seed=7)
    triangles = numpy.array(
        [[[1.0, 2.0], [40.0, 2.0], [40.0, 20.0]]], dtype=numpy.float64
    )
    counts = numpy.array([1], dtype=numpy.int64)

    margined = AnalysisSettings(margin_texels=1)
    assert (
        gpu_raster.counted_batch(
            triangles, counts, grid, AddressMode.REPEAT, settings=margined
        )
        is None
    ), "a raster margin must fall back; the kernel does not dilate"

    empty = gpu_raster.counted_batch(
        numpy.zeros((0, 3, 2)),
        numpy.zeros(0, dtype=numpy.int64),
        grid,
        AddressMode.REPEAT,
        settings=_DEFAULTS,
    )
    assert empty is not None and empty[0].size == 0, empty


def run() -> None:
    assert_probe_is_total()
    if not gpu_raster.available():
        why = gpu_raster.reason()
        # A machine with no usable GPU skips. A machine whose GPU answers wrongly
        # is a defect: it must fail here rather than disappear into a skip.
        assert not why.startswith("MISMATCH"), why
        print(f"SKIP: the GPU kernel tests did not run: {why}")
        print("ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_SKIPPED")
        return
    assert_modes_cross_edges()
    assert_exact_at_scale()
    assert_unhandled_inputs_fall_back()
    gpu_raster.clear_cache()
    print("ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_OK")
