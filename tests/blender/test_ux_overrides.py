# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for UI state, review gating, and per-material overrides."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

import bpy

from addon import runtime
from addon.adapters import analysis as analysis_adapter
from addon.presentation import review_signature
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad


def _select_only(*objects) -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for object_ in objects:
        object_.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def _file_backed_image(name: str, directory: str):
    """Create a lawful tiny FILE image whose pixels are clean after loading."""

    generated = _image(f"{name}_GENERATED_SOURCE")
    path = Path(directory) / f"{name}.png"
    generated.filepath_raw = str(path)
    generated.file_format = "PNG"
    generated.save()
    bpy.data.images.remove(generated)
    image = bpy.data.images.load(str(path), check_existing=False)
    image.name = name
    assert image.source == "FILE" and not image.is_dirty, (
        image.source,
        image.is_dirty,
    )
    return image


def run() -> None:
    _clear_scene()
    temporary_images = tempfile.TemporaryDirectory(prefix="ams-ux-images-")
    auto_image = _file_backed_image("AMS_UX_AUTO_IMAGE", temporary_images.name)
    override_image = _file_backed_image(
        "AMS_UX_OVERRIDE_IMAGE", temporary_images.name
    )
    auto_material, _tree, _principled, _texture = _material(
        "AMS_UX_AUTO_MATERIAL", auto_image
    )
    manual_material = bpy.data.materials.new("AMS_UX_MANUAL_MATERIAL")
    automatic_object = _quad("AMS_UX_AUTOMATIC", auto_material)
    manual_object = _quad("AMS_UX_MANUAL", manual_material)
    manual_object.location.x = 2.0
    _select_only(automatic_object, manual_object)

    override_json = json.dumps(
        [
            {
                "material_name": manual_material.name,
                "image_name": override_image.name,
                "image_channel": "RED",
                "uv_map_name": "UVMap",
                "address_mode": "REPEAT",
            }
        ]
    )
    analyzed = bpy.ops.alpha_material_separator.analyze(
        api_major=1, material_overrides_json=override_json
    )
    assert analyzed == {"FINISHED"}, analyzed
    state = bpy.context.window_manager.alpha_material_separator_api
    payload = json.loads(state.report_json)
    groups = {
        group["material"]: group
        for object_payload in payload["objects"]
        for group in object_payload.get("groups", ())
    }
    assert groups[auto_material.name]["source_kind"] == "UNIQUE_BASE_COLOR_IMAGE_ALPHA"
    assert groups[auto_material.name]["channel"] == "ALPHA"
    assert groups[manual_material.name]["source_kind"] == "EXPLICIT_OVERRIDE"
    assert groups[manual_material.name]["channel"] == "RED"
    assert groups[manual_material.name]["image"] == override_image.name
    assert groups[manual_material.name]["uv_map"] == "UVMap"
    assert payload["counts"]["MIXED"] == 1, payload
    assert payload["counts"]["OPAQUE"] == 1, payload
    unrelated_image = bpy.data.images.new(
        "AMS_UX_UNRELATED_IMAGE", width=1, height=1, alpha=True
    )
    assert runtime._relevant_update_scope(automatic_object) == "OBJECT"
    assert runtime._relevant_update_scope(automatic_object.data) == "MESH"
    assert runtime._relevant_update_scope(auto_material) == "MATERIAL"
    assert runtime._relevant_update_scope(auto_image) == "IMAGE"
    assert runtime._relevant_update_scope(unrelated_image) == ""

    settings = bpy.context.window_manager.alpha_material_separator_settings
    ui = bpy.context.window_manager.alpha_material_separator_ui
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        classes={"ALPHA_AFFECTED", "MIXED"},
        selection_mode="REPLACE",
        enter_edit_mode=True,
        preview_assignment_plan=True,
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        derived_conflict_policy=settings.derived_conflict_policy,
    )
    assert preview == {"FINISHED"}, preview
    assert automatic_object.mode == "EDIT" and manual_object.mode == "EDIT"
    signature = review_signature(
        state.analysis_id,
        settings.mixed_policy,
        settings.suppressed_policy,
        settings.unsupported_policy,
        settings.derived_conflict_policy,
    )
    assert runtime.review_matches(
        bpy.context.window_manager, state.analysis_id, signature
    ), (
        ui.reviewed_analysis_id,
        ui.reviewed_policy_signature,
        state.analysis_id,
        signature,
        runtime.dirty_reason(),
    )

    # Leaving the multi-object preview can emit a generic Mesh update even
    # though only mode and face-selection state changed.  Keep the reviewed
    # report and prove validity with the structural fingerprint: this path must
    # not read image pixels through the full preparation routine or evict UV
    # coverage cached by the completed analysis.
    bpy.ops.object.mode_set(mode="OBJECT")
    sentinel_coverage = object()
    runtime.coverage_set("AMS_REVALIDATION_SENTINEL", sentinel_coverage)
    runtime.mark_recheck("MESH_UPDATED", "MESH")
    assert runtime.validation_state() == runtime.VALIDATION_RECHECK_PENDING
    assert state.validation_state == runtime.VALIDATION_RECHECK_PENDING
    assert json.loads(state.pending_scopes_json) == ["MESH"]
    assert not runtime.dirty_reason()
    assert runtime.review_matches(
        bpy.context.window_manager, state.analysis_id, signature
    )
    report = runtime.report(state.analysis_id)
    assert report is not None
    original_prepare = analysis_adapter._prepare

    def unexpected_full_validation(*_args, **_kwargs):
        raise AssertionError("mesh-only revalidation read image inputs")

    analysis_adapter._prepare = unexpected_full_validation
    try:
        valid, reason = analysis_adapter.validate_report(report)
    finally:
        analysis_adapter._prepare = original_prepare
    assert valid and reason == "OK", reason
    validation = runtime.snapshot()
    assert validation["validation_state"] == runtime.VALIDATION_CLEAN, validation
    assert validation["last_validation_image_digest_rows"] == 0, validation
    assert validation["last_validation_rasterized_polygons"] == 0, validation
    assert state.validation_state == runtime.VALIDATION_CLEAN
    assert json.loads(state.pending_scopes_json) == []
    assert validation["last_validation_mode"] == "STRUCTURAL", validation
    assert runtime.coverage_get("AMS_REVALIDATION_SENTINEL") is sentinel_coverage
    assert runtime.review_matches(
        bpy.context.window_manager, state.analysis_id, signature
    )

    settings.mixed_policy = "KEEP_SOURCE"
    assert not ui.reviewed_analysis_id, ui.reviewed_analysis_id
    settings.mixed_policy = "TO_ALPHA"

    manual_material.name = "AMS_UX_MANUAL_RENAMED"
    added = bpy.ops.alpha_material_separator.add_material_override(
        material_name=manual_material.name
    )
    assert added == {"FINISHED"}, added
    assert settings.material_overrides[0].material == manual_material
    manual_material.name = "AMS_UX_MANUAL_RENAMED_AGAIN"
    assert settings.material_overrides[0].material.name == manual_material.name
    removed = bpy.ops.alpha_material_separator.remove_material_override(index=0)
    assert removed == {"FINISHED"}, removed
    assert len(settings.material_overrides) == 0

    _select_only(automatic_object)
    unused = bpy.ops.alpha_material_separator.analyze(
        material_overrides_json=json.dumps(
            [{"material_name": manual_material.name}]
        )
    )
    assert unused == {"CANCELLED"}, unused
    assert state.last_status_code == "OVERRIDE_TARGET_NOT_SELECTED", state.last_status_json
    conflict = bpy.ops.alpha_material_separator.analyze(
        image_name=auto_image.name,
        material_overrides_json=json.dumps(
            [{"material_name": auto_material.name}]
        ),
    )
    assert conflict == {"CANCELLED"}, conflict
    assert state.last_status_code == "OVERRIDE_CONFLICT", state.last_status_json

    runtime.finish_analysis(bpy.context.window_manager)
    prior_report = runtime.report()
    assert prior_report is not None
    assert runtime.begin_analysis(bpy.context.window_manager)
    runtime.update_analysis(bpy.context.window_manager, 5, 10, "Testing")
    runtime.update_analysis(bpy.context.window_manager, 3, 10, "Testing")
    assert ui.analysis_progress == 0.5, ui.analysis_progress
    cancel = bpy.ops.alpha_material_separator.cancel_analysis()
    assert cancel == {"FINISHED"}, cancel
    assert runtime.cancellation_requested(bpy.context.window_manager)
    runtime.finish_analysis(bpy.context.window_manager)
    assert not ui.is_analyzing and ui.analysis_progress == 0.0
    assert runtime.report() is prior_report
    temporary_images.cleanup()
    print("ALPHA_MATERIAL_SEPARATOR_UX_OVERRIDE_TESTS_OK")
