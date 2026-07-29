# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative SUPPRESSED and UNSUPPORTED assignment policy tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import bpy

from addon import runtime
from addon.adapters.assignment import (
    ObjectMutation,
    build_assignment_plan,
    execute_assignment_plan,
)
from addon.operators.assign_materials import (
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials,
    _CONFIRMATION_TEXT,
    _CONFIRMATION_TITLE,
    _confirmation_dialog_width,
)
from addon.presentation import (
    already_separated_tooltip,
    assignment_confirmation_lines,
    review_signature,
    ui_text_lines,
)
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad
from tests.blender.test_assignment import _analyze, _assign


class _CancelledDialogWindowManager:
    def __init__(self, real):
        self._real = real
        self.options = None

    def __getattr__(self, name):
        return getattr(self._real, name)

    def invoke_props_dialog(self, _operator, **options):
        self.options = options
        return {"CANCELLED"}


class _DialogRecordingLayout:
    def __init__(self):
        self.labels = []
        self.separators = 0

    def label(self, *, text="", icon="NONE"):
        self.labels.append((text, icon))

    def separator(self):
        self.separators += 1


def _partial_support_object(name, source, unresolved):
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    vertices = tuple(
        (x + offset, y, 0.0)
        for offset in (0.0, 2.0, 4.0, 6.0, 8.0)
        for x, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    )
    mesh.from_pydata(
        vertices,
        (),
        (
            (0, 1, 2, 3),
            (4, 5, 6, 7),
            (8, 9, 10, 11),
            (12, 13, 14, 15),
            (16, 17, 18, 19),
        ),
    )
    mesh.materials.append(source)
    mesh.materials.append(unresolved)
    mesh.polygons[0].material_index = 0
    mesh.polygons[1].material_index = 0
    mesh.polygons[2].material_index = 0
    mesh.polygons[3].material_index = 0
    mesh.polygons[4].material_index = 1
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    normal = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    alpha_only = ((0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5))
    opaque_only = ((0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5))
    modern = getattr(uv_layer, "uv", None)
    for polygon in mesh.polygons:
        if polygon.index == 1:
            coordinates = ((0.0, 0.0),) * 4
        elif polygon.index == 2:
            coordinates = alpha_only
        elif polygon.index == 3:
            coordinates = opaque_only
        else:
            coordinates = normal
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
    short_lines = ("Move 2 reviewed faces to alpha materials.",)
    long_lines = (
        "Only material slots and face assignments change—no topology "
        "or source shader changes. Ctrl+Z to undo.",
    )
    assert _confirmation_dialog_width(short_lines, 1920) == 420
    assert _confirmation_dialog_width(long_lines, 1920) == 560
    assert _confirmation_dialog_width(long_lines, 500) == 436
    assert _CONFIRMATION_TITLE == "Apply Material Separation"
    assert _CONFIRMATION_TEXT == "Apply"

    _clear_scene()
    image = _image("AMS_POLICY_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_POLICY_SOURCE", image)
    object_ = _quad("AMS_POLICY_OBJECT", material)

    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    report = json.loads(state.report_json)
    assert report["counts"]["SUPPRESSED"] == 1, report
    suppressed_report = runtime.report(state.analysis_id)
    suppressed_blocked_plan = build_assignment_plan(
        suppressed_report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    suppressed_move_plan = build_assignment_plan(
        suppressed_report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="TO_ALPHA",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert (
        suppressed_blocked_plan.public_payload()["suppressed_faces_to_alpha"]
        == 0
    )
    assert suppressed_move_plan.public_payload()["suppressed_faces_to_alpha"] == 1
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
    assert payload["counts"]["ALPHA_AFFECTED"] == 1, payload
    assert payload["counts"]["OPAQUE"] == 1, payload
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
    blocked_payload = blocked_plan.public_payload()
    assert blocked_payload["mixed_faces_to_alpha"] == 0, blocked_payload
    keep_plan = build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="KEEP_SOURCE",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert keep_plan.public_payload()["faces_to_reassign"] == 2
    assert keep_plan.skipped_group_count == 0, keep_plan.public_payload()
    assert keep_plan.partial_group_count == 1, keep_plan.public_payload()
    assert keep_plan.unchanged_group_count == 1, keep_plan.public_payload()
    plan = build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    public_plan = plan.public_payload()
    assert public_plan["faces_to_reassign"] == 3, public_plan
    assert public_plan["mixed_faces_to_alpha"] == 1, public_plan
    assert public_plan["suppressed_faces_to_alpha"] == 0, public_plan
    assert public_plan["face_local_unsupported_to_alpha"] == 1, public_plan
    assert public_plan["material_source_groups_left_unchanged"] == 1, public_plan
    assert not plan.blocked, public_plan

    indices_before_dialog = tuple(
        polygon.material_index for polygon in partial.data.polygons
    )
    slots_before_dialog = tuple(
        slot.material for slot in partial.material_slots
    )
    dialog_window_manager = _CancelledDialogWindowManager(
        bpy.context.window_manager
    )
    operator = SimpleNamespace(
        api_major=1,
        expected_analysis_id=analysis_id,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        expected_review_signature="",
        _confirmation_plan_signature="",
        _confirmation_plan_json="{}",
    )
    operator.expected_review_signature = review_signature(
        analysis_id,
        operator.mixed_policy,
        operator.suppressed_policy,
        operator.unsupported_policy,
        operator.derived_conflict_policy,
        public_plan,
    )
    cancelled = ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.invoke(
        operator,
        SimpleNamespace(
            window_manager=dialog_window_manager,
            object=bpy.context.object,
            window=SimpleNamespace(width=1920),
        ),
        None,
    )
    assert cancelled == {"CANCELLED"}, cancelled
    assert dialog_window_manager.options == {
        "width": 560,
        "title": "Apply Material Separation",
        "confirm_text": "Apply",
    }
    assert operator._confirmation_draw_width == 560
    assert json.loads(operator._confirmation_plan_json) == public_plan
    confirmation_lines = assignment_confirmation_lines(public_plan)

    dialog_draw = _DialogRecordingLayout()
    operator.layout = dialog_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        operator,
        SimpleNamespace(region=SimpleNamespace(type="WINDOW", width=180)),
    )
    assert dialog_draw.labels[0][0] == confirmation_lines[0]
    assert dialog_draw.separators == 1

    hud_draw = _DialogRecordingLayout()
    operator.layout = hud_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        operator,
        SimpleNamespace(region=SimpleNamespace(type="HUD", width=220)),
    )
    expected_hud_text = [
        wrapped
        for sentence in confirmation_lines
        for wrapped in ui_text_lines(sentence, 220)
    ]
    assert [text for text, _icon in hud_draw.labels] == expected_hud_text
    assert len(hud_draw.labels) > len(dialog_draw.labels)
    assert hud_draw.separators == 1

    fallback_draw = _DialogRecordingLayout()
    operator.layout = fallback_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        operator,
        SimpleNamespace(region=SimpleNamespace(type="HUD", width=0)),
    )
    expected_fallback_text = [
        wrapped
        for sentence in confirmation_lines
        for wrapped in ui_text_lines(sentence, 220)
    ]
    assert [text for text, _icon in fallback_draw.labels] == expected_fallback_text

    missing_context_draw = _DialogRecordingLayout()
    operator.layout = missing_context_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(operator, None)
    assert missing_context_draw.labels == dialog_draw.labels
    assert tuple(
        polygon.material_index for polygon in partial.data.polygons
    ) == indices_before_dialog
    assert tuple(
        slot.material for slot in partial.material_slots
    ) == slots_before_dialog

    # An unexpected execution failure must restore slots, face assignments, and
    # any newly-created derived material before the operator reports failure.
    original_slots = tuple(slot.material for slot in partial.material_slots)
    original_indices = tuple(polygon.material_index for polygon in partial.data.polygons)
    original_material_count = len(bpy.data.materials)
    plan.mutations.append(ObjectMutation(partial, unresolved_material, (4,)))
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
    assert [polygon.select for polygon in partial.data.polygons] == [
        True,
        True,
        True,
        False,
        False,
    ]

    assigned, assigned_state = _assign(analysis_id, unsupported_policy="TO_ALPHA")
    assert assigned == {"FINISHED"}, assigned_state.last_status_json
    assert assigned_state.last_status_code == "ASSIGNMENT_COMPLETE_WITH_SKIPS"
    assert [polygon.material_index for polygon in partial.data.polygons] == [
        2,
        2,
        2,
        0,
        1,
    ]
    completion = json.loads(assigned_state.last_status_json)
    assert completion["changes"]["changed_faces"] == 3, completion
    assert completion["changes"]["unchanged_material_groups"] == 1, completion
    slot_count = len(partial.material_slots)
    analysis_id = _analyze(partial)
    rerun_plan = build_assignment_plan(
        runtime.report(analysis_id),
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert (
        rerun_plan.already_derived
        and rerun_plan.has_skips
        and not rerun_plan.actionable
    )
    assert already_separated_tooltip(
        already_derived=bool(rerun_plan.already_derived),
        actionable=rerun_plan.actionable,
    )
    repeated, repeated_state = _assign(
        analysis_id, unsupported_policy="TO_ALPHA"
    )
    assert repeated == {"FINISHED"}, repeated_state.last_status_json
    assert repeated_state.last_status_code == "ASSIGNMENT_NO_CHANGES"
    assert len(partial.material_slots) == slot_count
    assert [polygon.material_index for polygon in partial.data.polygons] == [
        2,
        2,
        2,
        0,
        1,
    ]

    # A CANCEL_SOURCE_MATERIAL policy is source-wide across selected objects:
    # one collapsed-UV face must prevent a different object using the same
    # source from being changed under that explicit Expert policy.
    _clear_scene()
    shared_image = _image("AMS_SHARED_POLICY_IMAGE")
    shared_source, _tree, _principled, _texture = _material(
        "AMS_SHARED_POLICY_SOURCE", shared_image
    )
    shared_unresolved = bpy.data.materials.new("AMS_SHARED_POLICY_UNRESOLVED")
    uncertain_object = _partial_support_object(
        "AMS_SHARED_POLICY_UNCERTAIN", shared_source, shared_unresolved
    )
    ordinary_object = _quad("AMS_SHARED_POLICY_ORDINARY", shared_source)
    ordinary_object.location.y = 2.0
    uncertain_object.select_set(True)
    ordinary_object.select_set(True)
    bpy.context.view_layer.objects.active = uncertain_object
    shared_analysis_id = _analyze(uncertain_object, ordinary_object)
    shared_report = runtime.report(shared_analysis_id)
    source_wide_block = build_assignment_plan(
        shared_report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="CANCEL_SOURCE_MATERIAL",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert not source_wide_block.actionable, source_wide_block.public_payload()
    assert len(source_wide_block.blocked) == 1, source_wide_block.public_payload()
    source_dispositions = [
        item
        for item in source_wide_block.dispositions
        if item.material_pointer == shared_source.as_pointer()
    ]
    assert len(source_dispositions) == 2, source_wide_block.public_payload()
    assert all(item.action == "SKIP_GROUP" for item in source_dispositions)
    print("ALPHA_MATERIAL_SEPARATOR_ASSIGNMENT_POLICY_TESTS_OK")
