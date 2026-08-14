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

import contextlib
import os

import bpy
import numpy

from addon.adapters import analysis as analysis_module
from addon.adapters import gpu_raster
from addon.adapters.analysis import AnalysisConfig, AnalysisEngine
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


def _assert_matches_cpu(
    triangles,
    counts,
    grid,
    mode,
    settings=_DEFAULTS,
    label="",
    high_precision=True,
):
    """Bit-equality with the CPU, which is the double-precision kernel's contract.

    `high_precision` defaults to on because that is what these fixtures demand:
    coordinates near `1e7` with sub-ulp spacing cannot survive a 24-bit
    significand. The single-precision kernel is held to the same equality on the
    one fixture built to be exact at that width.
    """
    produced = gpu_raster.counted_batch(
        triangles, counts, grid, mode, settings=settings, high_precision=high_precision
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


@contextlib.contextmanager
def _fresh_probe(**patches):
    """Re-probe inside the block, with patches applied, then put it all back.

    The probe caches one shader and one reason per precision and never runs
    twice, so a test that wants to see it decide differently has to clear the
    cache first and restore this machine's real answers afterwards.
    """
    shaders, reasons = dict(gpu_raster._shaders), dict(gpu_raster._reasons)
    originals = {name: getattr(gpu_raster, name) for name in patches}
    for name, value in patches.items():
        setattr(gpu_raster, name, value)
    gpu_raster._shaders.clear()
    try:
        yield
    finally:
        for name, value in originals.items():
            setattr(gpu_raster, name, value)
        gpu_raster._shaders.clear()
        gpu_raster._shaders.update(shaders)
        gpu_raster._reasons.clear()
        gpu_raster._reasons.update(reasons)


def assert_probe_is_total() -> None:
    """`available()` answers, caches, and never lets a failure escape."""
    first = gpu_raster.available()
    assert isinstance(first, bool), type(first)
    assert gpu_raster.available() is first, "probe is not stable across calls"


def assert_background_needs_an_opt_in() -> None:
    """A background Blender stays on the CPU unless the machine opts in.

    Asking for a context where there is no display server is not a recoverable
    failure: the Linux runner exits on a missing `libEGL.so.1` and the Windows
    one takes an access violation, and neither reaches an `except` clause. The
    opt-in is what still lets a machine with a working headless GPU — this one —
    run everything below.
    """
    assert bpy.app.background, "these tests only run in a background Blender"

    opted_in = os.environ.pop(gpu_raster._BACKGROUND_OPT_IN, None)
    try:
        with _fresh_probe():
            assert gpu_raster.available() is False, (
                "background probed the GPU uninvited"
            )
            assert gpu_raster.reason().startswith(
                "UNAVAILABLE: background"
            ), gpu_raster.reason()
    finally:
        if opted_in is not None:
            os.environ[gpu_raster._BACKGROUND_OPT_IN] = opted_in


def assert_the_probe_measures_fp64() -> None:
    """The kernel's fp64 requirement is measured here, not denied by backend name.

    A deny list goes stale the moment a driver gains or loses the capability, and
    it cannot see the harder case at all: a backend that accepts `double` and
    quietly computes it in single precision compiles fine, fails the self-test,
    and is then reported as a defect rather than as a missing capability.
    """
    assert gpu_raster._has_fp64() is True, gpu_raster.reason(high_precision=True)

    # The fixture only discriminates because single precision cannot hold it. A
    # value float32 could reproduce would make the probe answer yes on a
    # demoting backend, which is the case it exists to catch.
    single = numpy.float32(1.0) + numpy.float32(2.0) ** numpy.float32(-52)
    assert single == numpy.float32(1.0), single


def assert_fp32_is_the_default_probe() -> None:
    """A GPU without fp64 still accelerates; it only loses the exact mode.

    The probe answers two questions now, and the double-precision one no longer
    decides the first. A backend that cannot compute `double` runs the default
    single-precision kernel like any other, and what turns off is the checkbox
    that would have asked for double.
    """
    with _fresh_probe(_has_fp64=lambda: False):
        assert gpu_raster.available() is True, gpu_raster.reason()
        assert gpu_raster.reason() == "OK", gpu_raster.reason()
        assert gpu_raster.available(high_precision=True) is False, (
            "a backend without fp64 was accepted for high precision"
        )
        assert gpu_raster.reason(high_precision=True).startswith("NO_FP64"), (
            gpu_raster.reason(high_precision=True)
        )


def assert_the_fp32_kernel_matches_the_cpu() -> None:
    """Single precision, held to the same equality, on a fixture built for it.

    Every coordinate is exactly representable at 24 bits and every vertical
    extent is a power of two, so each slope division is exact and the CPU's
    counts are reachable without a tolerance. That is what makes a mismatch here
    mean "this driver computes wrongly" rather than "single precision rounds",
    which is the same thing the adversarial fixture does for double precision.
    """
    quads, counts, grid = gpu_raster._fixture(high_precision=False)
    for mode in AddressMode:
        _assert_matches_cpu(
            quads, counts, grid, mode, label="fp32 ", high_precision=False
        )


def assert_the_setting_can_refuse_the_gpu() -> None:
    """`use_gpu=False` is the manual fallback, and it has to reach the engine.

    It is not in `AnalysisConfig.payload()` on purpose: both devices produce the
    same report, so the choice of device must not enter the input signature and
    make a completed report stale.
    """
    object_ = _scene(64)
    assert AnalysisEngine([object_], AnalysisConfig())._gpu
    engine = AnalysisEngine([object_], AnalysisConfig(use_gpu=False))
    assert not engine._gpu, "the setting did not reach the engine"
    assert AnalysisConfig().payload() == AnalysisConfig(use_gpu=False).payload()


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
            triangles,
            counts,
            grid,
            AddressMode.REPEAT,
            settings=margined,
            high_precision=True,
        )
        is None
    ), "a raster margin must fall back; the kernel does not dilate"

    empty = gpu_raster.counted_batch(
        numpy.zeros((0, 3, 2)),
        numpy.zeros(0, dtype=numpy.int64),
        grid,
        AddressMode.REPEAT,
        settings=_DEFAULTS,
        high_precision=True,
    )
    assert empty is not None and empty.covered_texels.size == 0, empty


def _scene(polygons: int):
    """One patterned image, one material, one grid of quads with wrapping UVs."""
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    width, height = 37, 23
    image = bpy.data.images.new("AMS_GPU_EQ", width=width, height=height, alpha=True)
    generator = numpy.random.default_rng(0xE0)
    pixels = numpy.ones((height * width, 4), dtype=numpy.float32)
    pixels[:, 3] = (generator.random(height * width) < 0.41).astype(numpy.float32)
    image.pixels.foreach_set(pixels.reshape(-1))

    material = bpy.data.materials.new("AMS_GPU_EQ_MAT")
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.is_active_output = True
    principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    tree.links.new(texture.outputs["Color"], principled.inputs["Base Color"])
    tree.links.new(texture.outputs["Alpha"], principled.inputs["Alpha"])
    material.blend_method = "BLEND"

    columns = 16
    vertices, faces = [], []
    for polygon in range(polygons):
        column, row = polygon % columns, polygon // columns
        base = len(vertices)
        vertices.extend(
            (
                (float(column), float(row), 0.0),
                (column + 1.0, float(row), 0.0),
                (column + 1.0, row + 1.0, 0.0),
                (float(column), row + 1.0, 0.0),
            )
        )
        faces.append((base, base + 1, base + 2, base + 3))
    mesh = bpy.data.meshes.new("AMS_GPU_EQ_MESH")
    mesh.from_pydata(vertices, (), faces)
    mesh.materials.append(material)

    # UVs several times the unit square and offset negative, so runs wrap in
    # both directions and the kernel's addressing is exercised rather than
    # only its rasterization.
    layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    layer.active_render = True
    corners = generator.random((polygons, 2)) * 5.0 - 2.0
    extent = 0.05 + generator.random((polygons, 2)) * 1.4
    quad = numpy.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    uvs = corners[:, None, :] + quad[None, :, :] * extent[:, None, :]
    layer.uv.foreach_set("vector", uvs.reshape(-1).astype(numpy.float32))

    object_ = bpy.data.objects.new("AMS_GPU_EQ_OBJ", mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    return object_


@contextlib.contextmanager
def _submitting_every(polygons: int):
    """Shrink the submit threshold so a small fixture still fills the pipeline.

    The shipped 16,384 would hold every face in these scenes to the very last
    flush, which is worth testing but is not what the pipeline tests are for.
    """
    original = analysis_module._GPU_SUBMIT_POLYGONS
    analysis_module._GPU_SUBMIT_POLYGONS = polygons
    try:
        yield
    finally:
        analysis_module._GPU_SUBMIT_POLYGONS = original


def _report(object_, *, on_gpu: bool, budget: int = 64):
    engine = AnalysisEngine([object_], AnalysisConfig())
    assert engine._gpu, "the probe passed but the engine did not take the GPU path"
    engine._gpu = on_gpu
    while not engine.step(budget):
        pass
    assert engine._inflight is None, "a completed step left a chunk on the GPU"
    assert not engine._pending, "a completed step left polygons unsubmitted"
    return engine.finish()


def assert_the_engine_agrees_with_itself() -> None:
    """A whole analysis on the GPU equals the same analysis on the CPU.

    Face by face, not in aggregate: two paths can reach the same totals from
    different per-face answers, and the report is per-face.
    """
    object_ = _scene(200)
    on_gpu = _report(object_, on_gpu=True)
    on_cpu = _report(object_, on_gpu=False)

    assert on_gpu.counts == on_cpu.counts, (on_gpu.counts, on_cpu.counts)
    for pointer, wanted in on_cpu.object_results.items():
        produced = on_gpu.object_results[pointer]
        assert produced.skipped_reason == wanted.skipped_reason
        assert set(produced.faces) == set(wanted.faces), "different polygons analyzed"
        for index, face in wanted.faces.items():
            assert produced.faces[index].result == face.result, (
                index,
                produced.faces[index].result,
                face.result,
            )
    assert on_cpu.counts.total() == 200, on_cpu.counts

    # The raster counters are part of the report, so they have to agree too.
    for name in (
        "triangles",
        "degenerate_triangles",
        "scanlines",
        "emitted_runs",
        "union_runs",
        "covered_texels",
    ):
        assert on_gpu.metrics[name] == on_cpu.metrics[name], (
            name,
            on_gpu.metrics[name],
            on_cpu.metrics[name],
        )

    # The one deliberate report difference: the GPU counts what it skipped
    # instead of hits and misses, because a fused kernel has nothing to cache.
    assert on_gpu.metrics["coverage_cache_bypassed"] == 200, on_gpu.metrics
    assert "coverage_cache_misses" not in on_gpu.metrics, on_gpu.metrics
    assert "coverage_cache_hits" not in on_gpu.metrics, on_gpu.metrics
    assert on_cpu.metrics["coverage_cache_bypassed"] == 0, on_cpu.metrics
    assert (
        on_cpu.metrics["coverage_cache_hits"] + on_cpu.metrics["coverage_cache_misses"]
        == 200
    ), on_cpu.metrics


def assert_the_pipeline_survives_small_steps() -> None:
    """Many short steps, each ending with the previous chunk still on the GPU.

    A chunk is recorded one flush after it is deferred, so the step size decides
    how much work is in flight when a step returns. The engine has to give the
    same report whatever that size is.
    """
    object_ = _scene(200)
    wanted = _report(object_, on_gpu=False, budget=200)

    with _submitting_every(8):
        engine = AnalysisEngine([object_], AnalysisConfig())
        assert engine._gpu
        carried = 0
        while not engine.step(8):
            carried += engine._inflight is not None
        # Without this the test would still pass on an engine that drained
        # every step, which is the thing it exists to rule out.
        assert carried >= 20, carried
        produced = engine.finish()

    assert produced.counts == wanted.counts, (produced.counts, wanted.counts)
    for pointer, expected in wanted.object_results.items():
        faces = produced.object_results[pointer].faces
        for index, face in expected.faces.items():
            assert faces[index].result == face.result, index


def assert_held_polygons_are_never_dropped() -> None:
    """At the shipped threshold every face in a small scene is held to the end.

    That is the ordinary case for any mesh under 16,384 polygons, and the whole
    report then depends on one forced flush at completion firing.
    """
    object_ = _scene(200)
    assert analysis_module._GPU_SUBMIT_POLYGONS > 200, "the scene must fit the hold"

    engine = AnalysisEngine([object_], AnalysisConfig())
    assert engine._gpu
    submitted = 0
    while not engine.step(8):
        submitted += engine._inflight is not None
    assert submitted == 0, "something was submitted before the hold was reached"
    produced = engine.finish()

    assert produced.counts.total() == 200, produced.counts
    wanted = _report(object_, on_gpu=False, budget=200)
    assert produced.counts == wanted.counts, (produced.counts, wanted.counts)


def assert_work_in_flight_is_never_lost() -> None:
    """The two ways an incomplete run can reach a caller, both refused.

    `finish` must not build a short report over a chunk still on the GPU, and
    `cancel` must drop the handles rather than leave their textures alive.
    """
    object_ = _scene(64)
    with _submitting_every(8):
        engine = AnalysisEngine([object_], AnalysisConfig())
        assert engine._gpu
        assert not engine.step(8)
        assert engine._inflight is not None, "the step recorded what it should defer"
        try:
            engine.finish()
        except RuntimeError:
            pass
        else:
            raise AssertionError("finish built a report over a chunk on the GPU")

        engine.cancel()
        assert engine._inflight is None, "cancel left GPU textures held"


def run() -> None:
    assert_probe_is_total()
    # Outside the skip below on purpose: this is the guard that keeps a machine
    # without a display server out of the GPU entirely, so it has to be proven
    # exactly where the kernel cannot run.
    assert_background_needs_an_opt_in()
    if not gpu_raster.available():
        why = gpu_raster.reason()
        # A machine with no usable GPU skips. A machine whose GPU answers wrongly
        # is a defect: it must fail here rather than disappear into a skip.
        assert not why.startswith("MISMATCH"), why
        print(f"SKIP: the GPU kernel tests did not run: {why}")
        print("ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_SKIPPED")
        return
    assert_the_probe_measures_fp64()
    assert_fp32_is_the_default_probe()
    assert_the_fp32_kernel_matches_the_cpu()
    assert_the_setting_can_refuse_the_gpu()
    assert_modes_cross_edges()
    assert_exact_at_scale()
    assert_awkward_polygons_are_partitioned()
    assert_budget_trips_match_the_cpu()
    assert_unhandled_inputs_fall_back()
    assert_the_engine_agrees_with_itself()
    assert_the_pipeline_survives_small_steps()
    assert_held_polygons_are_never_dropped()
    assert_work_in_flight_is_never_lost()
    gpu_raster.clear_cache()
    print("ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_OK")
