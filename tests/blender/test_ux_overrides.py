# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for UI state, review gating, and per-material overrides."""

from __future__ import annotations

import json

import bpy

from addon import runtime
from addon.presentation import review_signature
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad


def _select_only(*objects) -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for object_ in objects:
        object_.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def run() -> None:
    _clear_scene()
    auto_image = _image("AMS_UX_AUTO_IMAGE")
    override_image = _image("AMS_UX_OVERRIDE_IMAGE")
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

    settings = bpy.context.window_manager.alpha_material_separator_settings
    ui = bpy.context.window_manager.alpha_material_separator_ui
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        classes={"ALPHA_AFFECTED", "MIXED"},
        selection_mode="REPLACE",
        enter_edit_mode=False,
    )
    assert preview == {"FINISHED"}, preview
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
    print("ALPHA_MATERIAL_SEPARATOR_UX_OVERRIDE_TESTS_OK")
