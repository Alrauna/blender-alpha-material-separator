# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative SUPPRESSED and UNSUPPORTED assignment policy tests."""

from __future__ import annotations

import json

import bpy

from addon import runtime
from addon.adapters.assignment import (
    ObjectMutation,
    build_assignment_plan,
    execute_assignment_plan,
)
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad
from tests.blender.test_assignment import _analyze, _assign


def _partial_support_object(name, source, unresolved):
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    vertices = tuple(
        (x + offset, y, 0.0)
        for offset in (0.0, 2.0, 4.0)
        for x, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    )
    mesh.from_pydata(
        vertices,
        (),
        ((0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11)),
    )
    mesh.materials.append(source)
    mesh.materials.append(unresolved)
    mesh.polygons[0].material_index = 0
    mesh.polygons[1].material_index = 0
    mesh.polygons[2].material_index = 1
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    normal = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    modern = getattr(uv_layer, "uv", None)
    for polygon in mesh.polygons:
        coordinates = ((0.0, 0.0),) * 4 if polygon.index == 1 else normal
        for offset, loop_index in enumerate(polygon.loop_indices):
            if modern is not None:
                modern[loop_index].vector = coordinates[offset]
            else:
                uv_layer.data[loop_index].uv = coordinates[offset]
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_
    return object_


def run() -> None:
    _clear_scene()
    image = _image("AMS_POLICY_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_POLICY_SOURCE", image)
    object_ = _quad("AMS_POLICY_OBJECT", material)

    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    report = json.loads(state.report_json)
    assert report["counts"]["SUPPRESSED"] == 1, report
    blocked, blocked_state = _assign(state.analysis_id)
    assert blocked == {"CANCELLED"}, blocked_state.last_status_json
    assert object_.data.polygons[0].material_index == 0

    analysis_id = _analyze(object_)
    # Re-run with suppression settings, since _analyze uses defaults.
    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}
    analysis_id = state.analysis_id
    informed, informed_state = _assign(
        analysis_id, suppressed_policy="TO_ALPHA"
    )
    assert informed == {"FINISHED"}, informed_state.last_status_json
    assert object_.data.polygons[0].material_index == 1

    _clear_scene()
    unsupported_material = bpy.data.materials.new("AMS_UNSUPPORTED_SOURCE")
    unsupported = _quad("AMS_UNSUPPORTED_OBJECT", unsupported_material)
    analysis_id = _analyze(unsupported)
    report = json.loads(state.report_json)
    assert report["counts"]["UNSUPPORTED"] == 1, report
    unchanged, unchanged_state = _assign(analysis_id)
    assert unchanged == {"FINISHED"}, unchanged_state.last_status_json
    assert unchanged_state.last_status_code == "ASSIGNMENT_NO_CHANGES"
    analysis_id = _analyze(unsupported)
    kept, kept_state = _assign(analysis_id, unsupported_policy="KEEP_SOURCE")
    assert kept == {"FINISHED"}, kept_state.last_status_json
    assert unsupported.data.polygons[0].material_index == 0

    _clear_scene()
    image = _image("AMS_PARTIAL_IMAGE")
    source, _tree, _principled, _texture = _material(
        "AMS_PARTIAL_SOURCE", image
    )
    unresolved_material = bpy.data.materials.new("AMS_PARTIAL_UNRESOLVED")
    partial = _partial_support_object(
        "AMS_PARTIAL_OBJECT", source, unresolved_material
    )
    analysis_id = _analyze(partial)
    payload = json.loads(state.report_json)
    assert payload["counts"]["MIXED"] == 1, payload
    assert payload["counts"]["UNSUPPORTED"] == 2, payload
    groups = {
        group["material"]: group
        for object_result in payload["objects"]
        for group in object_result.get("groups", ())
    }
    assert groups[source.name]["unsupported_scopes"] == {"FACE_LOCAL": 1}, groups
    assert groups[source.name]["default_disposition"] == "SPLIT", groups
    assert (
        groups[source.name]["default_planned_action"]
        == "MOVE_UNCERTAIN_TO_ALPHA"
    ), groups
    assert groups[unresolved_material.name]["unsupported_scopes"] == {
        "MATERIAL_SOURCE": 1
    }, groups
    assert (
        groups[unresolved_material.name]["default_disposition"]
        == "LEAVE_UNCHANGED"
    ), groups

    settings = bpy.context.window_manager.alpha_material_separator_settings
    assert settings.unsupported_policy == "TO_ALPHA"
    report = runtime.report(analysis_id)
    blocked_plan = build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="CANCEL_SOURCE_MATERIAL",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert len(blocked_plan.blocked) == 1, blocked_plan.public_payload()
    assert blocked_plan.blocked[0]["material"] == source.name
    keep_plan = build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="KEEP_SOURCE",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert keep_plan.public_payload()["faces_to_reassign"] == 1
    assert keep_plan.skipped_group_count == 2, keep_plan.public_payload()
    plan = build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    public_plan = plan.public_payload()
    assert public_plan["faces_to_reassign"] == 2, public_plan
    assert public_plan["face_local_unsupported_to_alpha"] == 1, public_plan
    assert public_plan["material_source_groups_left_unchanged"] == 1, public_plan
    assert not plan.blocked, public_plan

    # An unexpected execution failure must restore slots, face assignments, and
    # any newly-created derived material before the operator reports failure.
    original_slots = tuple(slot.material for slot in partial.material_slots)
    original_indices = tuple(polygon.material_index for polygon in partial.data.polygons)
    original_material_count = len(bpy.data.materials)
    plan.mutations.append(ObjectMutation(partial, unresolved_material, (2,)))
    try:
        execute_assignment_plan(plan)
    except KeyError:
        pass
    else:
        raise AssertionError("fault-injected assignment unexpectedly succeeded")
    assert tuple(slot.material for slot in partial.material_slots) == original_slots
    assert tuple(polygon.material_index for polygon in partial.data.polygons) == original_indices
    assert len(bpy.data.materials) == original_material_count
    plan.mutations.pop()

    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=analysis_id,
        preview_assignment_plan=True,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert preview == {"FINISHED"}, state.last_status_json
    assert partial.mode == "EDIT"
    ui = bpy.context.window_manager.alpha_material_separator_ui
    assert ui.reviewed_analysis_id == analysis_id
    bpy.ops.object.mode_set(mode="OBJECT")
    runtime.mark_recheck("MESH_UPDATED", "MESH")
    assert runtime.validation_state() == runtime.VALIDATION_RECHECK_PENDING
    assert ui.reviewed_analysis_id == analysis_id
    assert [polygon.select for polygon in partial.data.polygons] == [True, True, False]

    assigned, assigned_state = _assign(analysis_id, unsupported_policy="TO_ALPHA")
    assert assigned == {"FINISHED"}, assigned_state.last_status_json
    assert assigned_state.last_status_code == "ASSIGNMENT_COMPLETE_WITH_SKIPS"
    assert [polygon.material_index for polygon in partial.data.polygons] == [2, 2, 1]
    completion = json.loads(assigned_state.last_status_json)
    assert completion["changes"]["changed_faces"] == 2, completion
    assert completion["changes"]["unchanged_material_groups"] == 1, completion
    slot_count = len(partial.material_slots)
    analysis_id = _analyze(partial)
    repeated, repeated_state = _assign(
        analysis_id, unsupported_policy="TO_ALPHA"
    )
    assert repeated == {"FINISHED"}, repeated_state.last_status_json
    assert repeated_state.last_status_code == "ASSIGNMENT_NO_CHANGES"
    assert len(partial.material_slots) == slot_count
    assert [polygon.material_index for polygon in partial.data.polygons] == [2, 2, 1]
    print("ALPHA_MATERIAL_SEPARATOR_ASSIGNMENT_POLICY_TESTS_OK")
