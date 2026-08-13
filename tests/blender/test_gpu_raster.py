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


#: Every field of `RasterStats`, plus the affected count. Comparing all of them
#: is the point: a kernel that gets the texels right by luck still has to report
#: the same number of emitted runs and unions to have got there the same way.
_COUNTERS = (
    "affected",
    "triangles",
    "degenerate_triangles",
    "scanlines",
    "emitted_runs",
    "union_runs",
    "covered_texels",
)


def _oracle(triangles, counts, grid, mode, settings=_DEFAULTS):
    """The whole answer computed on the CPU alone, in the same shape as GpuCounts."""
    coverages = rasterize_batch(
        triangles,
        counts,
        margin_texels=settings.margin_texels,
        max_scanlines=settings.max_scanlines,
        max_run_emissions=settings.max_run_emissions,
    )
    want = {
        name: numpy.zeros(counts.shape[0], dtype=numpy.int64) for name in _COUNTERS
    }
    reasons = {}
    resolved = iter(
        grid.count_batch([one for one in coverages if not isinstance(one, str)], mode)
    )
    for index, coverage in enumerate(coverages):
        # A rejected polygon has no `RasterStats` at all, so every counter stays
        # zero rather than carrying a partial figure.
        if isinstance(coverage, str):
            reasons[index] = coverage
            continue
        want["affected"][index] = next(resolved)
        for name in _COUNTERS[1:]:
            want[name][index] = getattr(coverage.stats, name)
    return want, reasons


def _assert_matches_cpu(triangles, counts, grid, mode, settings=_DEFAULTS, label=""):
    produced = gpu_raster.counted_batch(
        triangles, counts, grid, mode, settings=settings
    )
    assert produced is not None, f"{label}{mode} batch was refused"
    want, want_reasons = _oracle(triangles, counts, grid, mode, settings)
    assert produced.reasons == want_reasons, (
        label, mode, produced.reasons, want_reasons
    )
    for name in _COUNTERS:
        got = getattr(produced, name)
        differing = int((got != want[name]).sum())
        assert not differing, (
            f"{label}{mode}: {differing} of {counts.shape[0]} {name} counts "
            f"differ, first at {numpy.flatnonzero(got != want[name])[:3]}"
        )
    return produced


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
        _assert_matches_cpu(triangles, counts, grid, mode)


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
            _assert_matches_cpu(
                triangles, counts, grid, mode, label=f"{width}x{height} "
            )


def _fan(centre, radius_x, radius_y, sides, generator):
    """A convex n-gon fan-triangulated the way `_prepare` receives one."""
    angles = numpy.linspace(0.0, 2.0 * numpy.pi, sides, endpoint=False)
    points = numpy.stack(
        (
            centre[0] + numpy.cos(angles) * radius_x,
            centre[1] + numpy.sin(angles) * radius_y,
        ),
        axis=1,
    )
    points += (generator.random(points.shape) - 0.5) * 0.25
    return [[points[0], points[index], points[index + 1]] for index in range(1, sides - 1)]


def assert_awkward_polygons_are_partitioned() -> None:
    """An n-gon past the span cap must not disable the GPU for its neighbours."""
    generator = numpy.random.default_rng(0xFA7)
    grid = _patterned_grid(97, 41, seed=0x0DD)

    pieces, counts = [], []
    for polygon in range(12):
        # Every fourth polygon exceeds the 32-triangle cap and has to go to the
        # CPU while the quads around it stay on the GPU.
        sides = 40 if polygon % 4 == 3 else 4
        fan = _fan(
            (polygon * 23.0 - 40.0, polygon * 11.0 - 30.0), 31.0, 17.0, sides, generator
        )
        pieces.extend(fan)
        counts.append(len(fan))
    triangles = numpy.array(pieces, dtype=numpy.float64)
    counts = numpy.array(counts, dtype=numpy.int64)
    assert (counts > gpu_raster.SPAN_CAP).sum() == 3, counts

    for mode in AddressMode:
        produced = _assert_matches_cpu(triangles, counts, grid, mode, label="mixed ")
        assert produced.reasons == {}, produced.reasons

    # And the same polygons on their own, so the all-CPU partition is covered too.
    over = counts > gpu_raster.SPAN_CAP
    by_triangle = numpy.repeat(over, counts)
    _assert_matches_cpu(
        triangles[by_triangle], counts[over], grid, AddressMode.REPEAT, label="all-slow "
    )


def assert_budget_trips_match_the_cpu() -> None:
    """A polygon over a budget keeps the CPU's reason string and its neighbours."""
    generator = numpy.random.default_rng(0xB0D)
    grid = _patterned_grid(64, 48, seed=0xB1)

    # One tall polygon whose scanline count dwarfs the others, and ordinary ones
    # around it that must survive on the GPU.
    pieces, counts = [], []
    for polygon in range(6):
        tall = polygon == 2
        fan = _fan(
            (polygon * 19.0, 20.0),
            9.0,
            400.0 if tall else 6.0,
            4,
            generator,
        )
        pieces.extend(fan)
        counts.append(len(fan))
    triangles = numpy.array(pieces, dtype=numpy.float64)
    counts = numpy.array(counts, dtype=numpy.int64)

    # Runs are at most one per triangle per row, so a budget below the tall
    # polygon's scanline total but above its neighbours' isolates it. The two
    # budgets are exercised separately because they produce different reasons.
    scanline_limit = AnalysisSettings(max_scanlines=200)
    emission_limit = AnalysisSettings(max_run_emissions=200)
    for settings, expected in (
        (scanline_limit, "BUDGET_SCANLINES"),
        (emission_limit, "BUDGET_RUN_EMISSIONS"),
    ):
        produced = _assert_matches_cpu(
            triangles, counts, grid, AddressMode.REPEAT, settings, label="budget "
        )
        assert produced.reasons == {2: expected}, produced.reasons
        assert produced.affected[3] > 0, "a neighbour lost its count to the trip"


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
    assert empty is not None and empty.covered_texels.size == 0, empty


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
    assert_awkward_polygons_are_partitioned()
    assert_budget_trips_match_the_cpu()
    assert_unhandled_inputs_fall_back()
    gpu_raster.clear_cache()
    print("ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_OK")
