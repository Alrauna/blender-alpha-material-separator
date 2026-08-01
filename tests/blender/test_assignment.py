# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless safe-assignment and derived-identity integration tests."""

from __future__ import annotations

import bpy

from addon.adapters.fingerprints import material_fingerprint
from addon.adapters.material_metadata import (
    DERIVED_FINGERPRINT,
    ROLE,
    ROLE_ALPHA_VARIANT,
    SOURCE_FINGERPRINT,
    SOURCE_NAME,
    VARIANT_UUID,
    inspect_metadata,
)
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad


def _select_only(*objects) -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for object_ in objects:
        object_.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def _analyze(*objects):
    _select_only(*objects)
    result = bpy.ops.alpha_material_separator.analyze()
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    return state.analysis_id


def _assign(analysis_id, **policies):
    result = bpy.ops.alpha_material_separator.assign_materials(
        expected_analysis_id=analysis_id,
        **policies,
    )
    return result, bpy.context.window_manager.alpha_material_separator_api


def run() -> None:
    _clear_scene()
    image = _image("AMS_ASSIGN_IMAGE")
    source, _tree, principled, _texture = _material("AMS_ASSIGN_SOURCE", image)
    first = _quad("AMS_ASSIGN_A", source)
    second = _quad("AMS_ASSIGN_B", source)
    unselected = _quad("AMS_ASSIGN_UNSELECTED", source)
    _select_only(first, second)

    source_fingerprint_before = material_fingerprint(source)
    source_keys_before = set(source.keys())
    analysis_id = _analyze(first, second)
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=analysis_id,
        classes={"MIXED"},
        enter_edit_mode=True,
    )
    assert preview == {"FINISHED"}, preview
    assert first.mode == "EDIT" and second.mode == "EDIT"
    result, state = _assign(analysis_id)
    assert result == {"FINISHED"}, state.last_status_json
    assert state.last_status_code == "ASSIGNMENT_COMPLETE", state.last_status_json

    derived = [
        material
        for material in bpy.data.materials
        if inspect_metadata(material).kind == "DERIVED"
        and inspect_metadata(material).source == source
    ]
    assert len(derived) == 1, derived
    derived = derived[0]
    assert derived[ROLE] == ROLE_ALPHA_VARIANT
    assert derived.get(VARIANT_UUID)
    assert derived.get(SOURCE_FINGERPRINT)
    assert derived.get(DERIVED_FINGERPRINT) == material_fingerprint(derived)
    assert len(first.material_slots) == 2 and len(second.material_slots) == 2
    assert first.material_slots[1].material == derived
    assert second.material_slots[1].material == derived
    assert first.data.polygons[0].material_index == 1
    assert second.data.polygons[0].material_index == 1

    assert len(unselected.material_slots) == 1
    assert unselected.data.polygons[0].material_index == 0
    assert material_fingerprint(source) == source_fingerprint_before
    assert set(source.keys()) == source_keys_before

    material_count = len(bpy.data.materials)
    first_slot_count = len(first.material_slots)
    second_slot_count = len(second.material_slots)
    analysis_id = _analyze(first, second)
    repeated, repeated_state = _assign(analysis_id)
    assert repeated == {"FINISHED"}, repeated_state.last_status_json
    assert len(bpy.data.materials) == material_count
    assert len(first.material_slots) == first_slot_count
    assert len(second.material_slots) == second_slot_count
    assert first.data.polygons[0].material_index == 1
    assert second.data.polygons[0].material_index == 1

    source.name = "AMS_ASSIGN_SOURCE_RENAMED"
    analysis_id = _analyze(first, second)
    renamed, renamed_state = _assign(analysis_id)
    assert renamed == {"FINISHED"}, renamed_state.last_status_json
    assert derived[SOURCE_NAME] == source.name
    assert len(bpy.data.materials) == material_count

    principled.inputs["Roughness"].default_value = 0.123
    analysis_id = _analyze(first, second)
    blocked, blocked_state = _assign(analysis_id)
    assert blocked == {"CANCELLED"}, blocked_state.last_status_json
    assert blocked_state.last_status_code == "ASSIGNMENT_BLOCKED"
    assert len(bpy.data.materials) == material_count

    analysis_id = _analyze(first, second)
    fresh, fresh_state = _assign(
        analysis_id,
        derived_conflict_policy="CREATE_NEW_VARIANT",
    )
    assert fresh == {"FINISHED"}, fresh_state.last_status_json
    variants = [
        material
        for material in bpy.data.materials
        if inspect_metadata(material).kind == "DERIVED"
        and inspect_metadata(material).source == source
    ]
    assert len(variants) == 2, variants
    assert first.data.polygons[0].material_index == 2
    assert second.data.polygons[0].material_index == 2
    print("ALPHA_MATERIAL_SEPARATOR_ASSIGNMENT_TESTS_OK")
