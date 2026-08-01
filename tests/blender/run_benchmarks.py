# SPDX-License-Identifier: GPL-3.0-or-later
"""Recorded local performance characterization; output stays ignored."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import gc
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from addon import runtime  # noqa: E402
from addon.adapters.analysis import (  # noqa: E402
    AnalysisConfig,
    AnalysisEngine,
    validate_report,
)
from addon.adapters.image_data import read_image_snapshot  # noqa: E402
from addon.adapters.assignment import build_assignment_plan  # noqa: E402
from addon.core import AddressMode, RasterBudgetExceeded, rasterize_polygon  # noqa: E402
from addon.operators.assign_materials import _validated_plan  # noqa: E402
from addon.presentation import review_signature  # noqa: E402


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _memory() -> dict[str, int]:
    counters = _PROCESS_MEMORY_COUNTERS_EX()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info = kernel32.K32GetProcessMemoryInfo
    get_process_memory_info.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_PROCESS_MEMORY_COUNTERS_EX),
        wintypes.DWORD,
    )
    get_process_memory_info.restype = wintypes.BOOL
    if not get_process_memory_info(
        get_current_process(),
        ctypes.byref(counters),
        counters.cb,
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return {
        "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        "private_bytes": int(counters.PrivateUsage),
        "working_set_bytes": int(counters.WorkingSetSize),
    }


def _material(name: str, image):
    material = bpy.data.materials.new(name)
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
    return material


def _grid_fixture(name, segments, image_sizes, material_count, uv_scale=1.0, uv_offset=0.0):
    images = [
        bpy.data.images.new(
            f"{name}_IMAGE_{index:02d}", width=size, height=size, alpha=True
        )
        for index, size in enumerate(image_sizes)
    ]
    vertices = [
        (float(x), float(y), 0.0)
        for y in range(segments + 1)
        for x in range(segments + 1)
    ]
    stride = segments + 1
    faces = []
    for y in range(segments):
        for x in range(segments):
            first = y * stride + x
            faces.append((first, first + 1, first + stride + 1, first + stride))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, (), faces)
    materials = [
        _material(
            f"{name}_MATERIAL_{index:02d}",
            images[index % len(images)],
        )
        for index in range(material_count)
    ]
    for material in materials:
        mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.material_index = polygon.index % material_count
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    modern = getattr(uv_layer, "uv", None)
    for loop in mesh.loops:
        x, y, _z = vertices[loop.vertex_index]
        uv = (
            uv_offset + uv_scale * x / segments,
            uv_offset + uv_scale * y / segments,
        )
        if modern is not None:
            modern[loop.index].vector = uv
        else:
            uv_layer.data[loop.index].uv = uv
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    return object_, images, materials


def _run_analysis(object_, *, clear_coverage):
    if clear_coverage:
        runtime.clear_coverage_cache()
    started = time.perf_counter()
    engine = AnalysisEngine((object_,), AnalysisConfig())
    while not engine.step(4096):
        pass
    report = engine.finish()
    elapsed = time.perf_counter() - started
    return elapsed, dict(report.metrics), report


def _digest_benchmark(size: int) -> dict:
    image = bpy.data.images.new(
        f"AMS_DIGEST_{size}", width=size, height=size, alpha=True
    )
    times = []
    retained = None
    for run in range(6):
        started = time.perf_counter()
        snapshot = read_image_snapshot(image, channel="ALPHA", threshold=0.999)
        elapsed = time.perf_counter() - started
        if run:
            times.append(elapsed)
        retained = snapshot
        if run < 5:
            del snapshot
            gc.collect()
    prefix_started = time.perf_counter()
    for row in range(size):
        retained.grid.count_run(row, 0, size, AddressMode.REPEAT)
    prefix_first = time.perf_counter() - prefix_started
    prefix_started = time.perf_counter()
    for row in range(size):
        retained.grid.count_run(row, 0, size, AddressMode.REPEAT)
    prefix_reuse = time.perf_counter() - prefix_started
    result = {
        "digest_seconds_median_5": statistics.median(times),
        "digest_seconds_runs": times,
        "image_size": size,
        "prefix_build_seconds": prefix_first,
        "prefix_reuse_seconds": prefix_reuse,
        "memory": _memory(),
        "texels": size * size,
    }
    del retained
    bpy.data.images.remove(image)
    gc.collect()
    print(f"DIGEST {size} complete", flush=True)
    return result


def _analysis_benchmark(tier: dict) -> dict:
    object_, images, materials = _grid_fixture(**tier)
    cold_times = []
    cold_metrics = None
    for run in range(6):
        elapsed, metrics, _report = _run_analysis(object_, clear_coverage=True)
        if run:
            cold_times.append(elapsed)
        cold_metrics = metrics
    reuse_time, reuse_metrics, _report = _run_analysis(object_, clear_coverage=False)
    images[0].pixels[3] = 0.5
    changed_image_time, changed_metrics, _report = _run_analysis(
        object_, clear_coverage=False
    )
    result = {
        "cold_seconds_median_5": statistics.median(cold_times),
        "cold_seconds_runs": cold_times,
        "coverage_reuse_seconds": reuse_time,
        "coverage_reuse_with_changed_image_seconds": changed_image_time,
        "cold_metrics": cold_metrics,
        "reuse_metrics": reuse_metrics,
        "changed_image_metrics": changed_metrics,
        "image_sizes": tier["image_sizes"],
        "material_count": tier["material_count"],
        "memory": _memory(),
        "polygons": len(object_.data.polygons),
        "triangles": len(object_.data.polygons) * 2,
        "uv_scale": tier.get("uv_scale", 1.0),
    }
    mesh = object_.data
    bpy.data.objects.remove(object_, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    for material in materials:
        bpy.data.materials.remove(material)
    for image in images:
        bpy.data.images.remove(image)
    runtime.clear_coverage_cache()
    gc.collect()
    print(f"ANALYSIS {tier['name']} complete", flush=True)
    return result


def _revalidation_benchmark() -> dict:
    temporary_images = tempfile.TemporaryDirectory(prefix="ams-benchmark-revalidation-")
    object_, images, materials = _grid_fixture(
        "revalidation",
        70,
        [1024],
        2,
    )
    clean_images = []
    for index, image in enumerate(images):
        image.pixels[3] = 0.0
        filepath = Path(temporary_images.name) / f"revalidation-{index}.png"
        image.filepath_raw = str(filepath)
        image.file_format = "PNG"
        image.save()
        clean = bpy.data.images.load(str(filepath), check_existing=False)
        clean.name = f"revalidation_FILE_IMAGE_{index:02d}"
        for material in materials:
            for node in material.node_tree.nodes:
                if getattr(node, "image", None) == image:
                    node.image = clean
        bpy.data.images.remove(image)
        clean_images.append(clean)
    images = clean_images
    assert all(image.source == "FILE" and not image.is_dirty for image in images)
    cold_seconds, cold_metrics, report = _run_analysis(
        object_, clear_coverage=True
    )
    runtime.set_report(report)
    policies = {
        "mixed_policy": "TO_ALPHA",
        "suppressed_policy": "CANCEL_SOURCE_MATERIAL",
        "unsupported_policy": "TO_ALPHA",
        "conflict_policy": "CANCEL_SOURCE_MATERIAL",
    }
    expected_plan = build_assignment_plan(report, **policies)
    expected_payload = expected_plan.public_payload()
    expected_signature = review_signature(
        report.analysis_id,
        policies["mixed_policy"],
        policies["suppressed_policy"],
        policies["unsupported_policy"],
        policies["conflict_policy"],
        expected_payload,
    )
    preflight_before = {
        "indices": tuple(
            polygon.material_index for polygon in object_.data.polygons
        ),
        "slots": tuple(slot.material for slot in object_.material_slots),
        "materials": tuple(
            sorted(material.as_pointer() for material in bpy.data.materials)
        ),
        "report": runtime.report(report.analysis_id),
    }
    operator = SimpleNamespace(
        api_major=1,
        expected_analysis_id=report.analysis_id,
        expected_review_signature=expected_signature,
        mixed_policy=policies["mixed_policy"],
        suppressed_policy=policies["suppressed_policy"],
        unsupported_policy=policies["unsupported_policy"],
        derived_conflict_policy=policies["conflict_policy"],
        _status=lambda *_args, **_kwargs: None,
    )
    context = SimpleNamespace(window_manager=bpy.context.window_manager)
    preflight_times = []
    preflight_plan = None
    for run in range(6):
        started = time.perf_counter()
        prepared = _validated_plan(operator, context)
        elapsed = time.perf_counter() - started
        if prepared is None:
            raise RuntimeError("Apply preflight did not produce a valid plan")
        prepared_report, preflight_plan, _payload = prepared
        if prepared_report is not report or not preflight_plan.actionable:
            raise RuntimeError(
                "Apply preflight changed report identity or actionability"
            )
        if run:
            preflight_times.append(elapsed)
    preflight_after = {
        "indices": tuple(
            polygon.material_index for polygon in object_.data.polygons
        ),
        "slots": tuple(slot.material for slot in object_.material_slots),
        "materials": tuple(
            sorted(material.as_pointer() for material in bpy.data.materials)
        ),
        "report": runtime.report(report.analysis_id),
    }
    preflight_mutation_free = preflight_after == preflight_before
    if not preflight_mutation_free:
        raise RuntimeError("Apply preflight mutated Blender or report state")
    preflight_snapshot = runtime.snapshot()
    bpy.ops.object.select_all(action="DESELECT")
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_
    times = []
    final_snapshot = {}
    for run in range(6):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        if runtime.validation_state() != runtime.VALIDATION_RECHECK_PENDING:
            # Keep the measured validation path deterministic if this Blender
            # build coalesces the mode transition before the handler observes it.
            runtime.mark_recheck("MESH_UPDATED", "MESH")
        started = time.perf_counter()
        valid, reason = validate_report(report)
        elapsed = time.perf_counter() - started
        if not valid:
            raise RuntimeError(f"structural revalidation failed: {reason}")
        if run:
            times.append(elapsed)
        final_snapshot = runtime.snapshot()
    median = statistics.median(times)
    result = {
        "cold_analysis_seconds": cold_seconds,
        "cold_metrics": cold_metrics,
        "mode_exit_recheck_seconds_median_5": median,
        "mode_exit_recheck_seconds_runs": times,
        "ratio_to_cold_analysis": median / max(cold_seconds, 1e-12),
        "last_validation_image_digest_rows": final_snapshot.get(
            "last_validation_image_digest_rows"
        ),
        "last_validation_rasterized_polygons": final_snapshot.get(
            "last_validation_rasterized_polygons"
        ),
        "last_validation_mode": final_snapshot.get("last_validation_mode"),
        "last_validation_component_hash_calls": final_snapshot.get(
            "last_validation_component_hash_calls"
        ),
        "last_validation_coverage_hits": final_snapshot.get(
            "last_validation_coverage_hits"
        ),
        "last_validation_coverage_misses": final_snapshot.get(
            "last_validation_coverage_misses"
        ),
        "last_validation_elapsed_seconds": final_snapshot.get(
            "last_validation_elapsed_seconds"
        ),
        "coverage_cache_entries": final_snapshot.get("coverage_cache_entries"),
        "target_under_one_second": median < 1.0,
        "target_under_fifteen_percent_cold": median < cold_seconds * 0.15,
        "apply_preflight_seconds_median_5": statistics.median(preflight_times),
        "apply_preflight_seconds_runs": preflight_times,
        "apply_preflight_ratio_to_cold_analysis": (
            statistics.median(preflight_times) / max(cold_seconds, 1e-12)
        ),
        "apply_preflight_actionable": bool(preflight_plan.actionable),
        "apply_preflight_mutation_free": preflight_mutation_free,
        "apply_preflight_last_validation_component_hash_calls": (
            preflight_snapshot.get("last_validation_component_hash_calls", 0)
        ),
        "apply_preflight_last_validation_image_digest_rows": (
            preflight_snapshot.get("last_validation_image_digest_rows", 0)
        ),
        "apply_preflight_last_validation_rasterized_polygons": (
            preflight_snapshot.get("last_validation_rasterized_polygons", 0)
        ),
        "apply_preflight_last_validation_coverage_hits": preflight_snapshot.get(
            "last_validation_coverage_hits", 0
        ),
        "apply_preflight_last_validation_coverage_misses": preflight_snapshot.get(
            "last_validation_coverage_misses", 0
        ),
    }
    runtime.clear()
    mesh = object_.data
    bpy.data.objects.remove(object_, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    for material in materials:
        bpy.data.materials.remove(material)
    for image in images:
        bpy.data.images.remove(image)
    temporary_images.cleanup()
    gc.collect()
    print("REVALIDATION complete", flush=True)
    return result


def _pathological() -> dict:
    triangle = (((0.0, 0.0), (1.0, 0.0), (0.0, 1_000_001.0)),)
    started = time.perf_counter()
    reason = ""
    try:
        rasterize_polygon(triangle, max_scanlines=1_000_000)
    except RasterBudgetExceeded as error:
        reason = error.budget
    return {
        "budget": reason,
        "seconds": time.perf_counter() - started,
        "terminated": reason == "scanlines",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--only",
        choices=("all", "revalidation"),
        default="all",
        help="Run the complete release baseline or only the mode/revalidation tier",
    )
    args = parser.parse_args(argv)
    tiers = (
        {"name": "small", "segments": 70, "image_sizes": [1024], "material_count": 1},
        {
            "name": "typical",
            "segments": 224,
            "image_sizes": [2048, 2048, 4096],
            "material_count": 10,
        },
        {
            "name": "high",
            "segments": 388,
            "image_sizes": [4096, 4096, 8192],
            "material_count": 16,
        },
        {
            "name": "large_tiled_uv",
            "segments": 70,
            "image_sizes": [1024],
            "material_count": 4,
            "uv_scale": 4.0,
            "uv_offset": -1.5,
        },
    )
    result = {
        "blender_version": bpy.app.version_string,
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": platform.python_version(),
        },
        "method": "one discarded warm-up, median of five measured runs",
        "revalidation": _revalidation_benchmark(),
        "schema_version": 2,
    }
    if args.only == "all":
        result.update(
            {
                "analysis": {
                    tier["name"]: _analysis_benchmark(tier) for tier in tiers
                },
                "digest": {
                    str(size): _digest_benchmark(size)
                    for size in (1024, 2048, 4096, 8192)
                },
                "pathological": _pathological(),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"BENCHMARK_OUTPUT {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    raise SystemExit(main(script_args))
