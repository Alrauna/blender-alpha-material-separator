# SPDX-License-Identifier: GPL-3.0-or-later
"""Derived identity, slot movement, undo, deletion, and persistence tests."""

from __future__ import annotations

from pathlib import Path

import bpy

import addon
from addon import runtime
from addon.adapters import material_metadata
from addon.adapters.fingerprints import source_fingerprint
from addon.adapters.material_metadata import (
    SOURCE_FINGERPRINT,
    create_derived_material,
    inspect_metadata,
    resolve_derived_material,
)
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad
from tests.blender.test_assignment import _analyze, _assign, _select_only


def _direct_metadata_transitions() -> None:
    image = _image("AMS_IDENTITY_IMAGE")
    source, _tree, principled, _texture = _material("AMS_IDENTITY_SOURCE", image)
    fingerprint = source_fingerprint(source, "IMAGE_DIGEST")

    material_count = len(bpy.data.materials)
    original_material_fingerprint = material_metadata.material_fingerprint

    def fail_after_copy(_material):
        raise RuntimeError("fault injection after material copy")

    material_metadata.material_fingerprint = fail_after_copy
    try:
        create_derived_material(source, fingerprint)
    except RuntimeError:
        pass
    else:
        raise AssertionError("fault-injected derived creation unexpectedly succeeded")
    finally:
        material_metadata.material_fingerprint = original_material_fingerprint
    assert len(bpy.data.materials) == material_count

    derived = create_derived_material(source, fingerprint)

    source.name = "AMS_IDENTITY_SOURCE_RENAMED"
    renamed_fingerprint = source_fingerprint(source, "IMAGE_DIGEST")
    assert renamed_fingerprint == fingerprint
    renamed = resolve_derived_material(
        source, renamed_fingerprint, conflict_policy="CANCEL_SOURCE_MATERIAL"
    )
    assert renamed.action == "REUSE" and renamed.material == derived, renamed

    principled.inputs["Roughness"].default_value = 0.234
    edited_fingerprint = source_fingerprint(source, "IMAGE_DIGEST")
    blocked = resolve_derived_material(
        source, edited_fingerprint, conflict_policy="CANCEL_SOURCE_MATERIAL"
    )
    assert blocked.action == "BLOCK" and blocked.reason == "SOURCE_CHANGED", blocked
    reuse = resolve_derived_material(
        source, edited_fingerprint, conflict_policy="REUSE_EXISTING"
    )
    assert reuse.action == "REUSE" and reuse.material == derived, reuse
    fresh = resolve_derived_material(
        source, edited_fingerprint, conflict_policy="CREATE_NEW_VARIANT"
    )
    assert fresh.action == "CREATE", fresh

    duplicate_source = source.copy()
    distinct = resolve_derived_material(
        duplicate_source,
        source_fingerprint(duplicate_source, "IMAGE_DIGEST"),
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert distinct.action == "CREATE", distinct

    conflicting_source = source.copy()
    conflicting_source["alpha_material_separator.unknown"] = True
    metadata_conflict = resolve_derived_material(
        conflicting_source,
        source_fingerprint(conflicting_source, "IMAGE_DIGEST"),
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert metadata_conflict.action == "BLOCK"
    assert metadata_conflict.reason == "SOURCE_METADATA_CONFLICT"

    duplicated_derived = derived.copy()
    duplicated = resolve_derived_material(
        source, edited_fingerprint, conflict_policy="CANCEL_SOURCE_MATERIAL"
    )
    assert duplicated.action == "BLOCK" and duplicated.reason == "DUPLICATED_DERIVED"
    duplicated_fresh = resolve_derived_material(
        source, edited_fingerprint, conflict_policy="CREATE_NEW_VARIANT"
    )
    assert duplicated_fresh.action == "CREATE"
    bpy.data.materials.remove(duplicated_derived)

    # Restore source match, then edit only the derived graph.
    derived[SOURCE_FINGERPRINT] = edited_fingerprint
    derived.node_tree.nodes.get("Principled BSDF").inputs["Metallic"].default_value = 0.5
    derived_changed = resolve_derived_material(
        source, edited_fingerprint, conflict_policy="CANCEL_SOURCE_MATERIAL"
    )
    assert derived_changed.action == "BLOCK" and derived_changed.reason == "DERIVED_CHANGED"

    derived.alpha_material_separator_source = None
    assert inspect_metadata(derived).kind == "ORPHAN"


def _assignment_slot_and_undo_transitions() -> None:
    _clear_scene()
    image = _image("AMS_UNDO_IMAGE")
    source, _tree, _principled, _texture = _material("AMS_UNDO_SOURCE", image)
    object_ = _quad("AMS_UNDO_OBJECT", source)
    object_name = object_.name

    bpy.ops.ed.undo_push(message="AMS assignment baseline")
    analysis_id = _analyze(object_)
    assigned, state = _assign(analysis_id)
    assert assigned == {"FINISHED"}, state.last_status_json
    object_ = bpy.data.objects[object_name]
    derived = object_.material_slots[1].material
    derived_pointer = derived.as_pointer()
    assert object_.data.polygons[0].material_index == 1

    if not bpy.app.background:
        bpy.ops.ed.undo()
        object_ = bpy.data.objects[object_name]
        assert len(object_.material_slots) == 1
        assert object_.data.polygons[0].material_index == 0
        bpy.ops.ed.redo()
        object_ = bpy.data.objects[object_name]
        assert len(object_.material_slots) == 2
        assert object_.data.polygons[0].material_index == 1
    else:
        operator_type = bpy.types.ALPHA_MATERIAL_SEPARATOR_OT_assign_materials
        assert "UNDO" in operator_type.bl_options
    derived = object_.material_slots[1].material

    object_.data.materials.pop(index=1)
    assert len(object_.material_slots) == 1
    analysis_id = _analyze(object_)
    restored, restored_state = _assign(analysis_id)
    assert restored == {"FINISHED"}, restored_state.last_status_json
    object_ = bpy.data.objects[object_name]
    assert object_.material_slots[1].material == derived

    # Slot number is not identity: swap source/derived, put the affected face on
    # the source, then verify assignment reuses the same derived at slot zero.
    object_.data.materials[0] = derived
    object_.data.materials[1] = source
    object_.data.polygons[0].material_index = 1
    analysis_id = _analyze(object_)
    moved, moved_state = _assign(analysis_id)
    assert moved == {"FINISHED"}, moved_state.last_status_json
    assert object_.data.polygons[0].material_index == 0
    assert len(object_.material_slots) == 2

    # Slot reassignment after review makes that report stale.
    analysis_id = _analyze(object_)
    replacement = bpy.data.materials.new("AMS_SLOT_REPLACEMENT")
    object_.data.materials[1] = replacement
    stale, stale_state = _assign(analysis_id)
    assert stale == {"CANCELLED"}
    assert stale_state.last_status_code == "STALE_ANALYSIS"

    # Remove and delete the exact variant; a reviewed rerun creates one new variant.
    object_.data.materials[0] = source
    object_.data.materials.pop(index=1)
    object_.data.polygons[0].material_index = 0
    if derived.users == 0:
        bpy.data.materials.remove(derived)
    analysis_id = _analyze(object_)
    recreated, recreated_state = _assign(analysis_id)
    assert recreated == {"FINISHED"}, recreated_state.last_status_json
    assert inspect_metadata(object_.material_slots[1].material).source == source


def _review_plan_transition() -> None:
    _clear_scene()
    image = _image("AMS_REVIEW_PLAN_IMAGE")
    source, _tree, _principled, _texture = _material(
        "AMS_REVIEW_PLAN_SOURCE", image
    )
    object_ = _quad("AMS_REVIEW_PLAN_OBJECT", source)
    analysis_id = _analyze(object_)
    state = bpy.context.window_manager.alpha_material_separator_api
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=analysis_id,
        preview_assignment_plan=True,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        selection_mode="REPLACE",
        enter_edit_mode=False,
    )
    assert preview == {"FINISHED"}, state.last_status_json
    ui = bpy.context.window_manager.alpha_material_separator_ui
    reviewed_signature = ui.reviewed_policy_signature
    report = runtime.report(analysis_id)
    group = next(iter(report.object_results[object_.as_pointer()].groups.values()))
    unexpected_variant = create_derived_material(
        source, group.source_fingerprint
    )
    slots_before = len(object_.material_slots)
    index_before = object_.data.polygons[0].material_index
    changed, changed_state = _assign(
        analysis_id,
        expected_review_signature=reviewed_signature,
        unsupported_policy="TO_ALPHA",
    )
    assert changed == {"CANCELLED"}, changed_state.last_status_json
    assert changed_state.last_status_code == "REVIEW_CHANGED"
    assert len(object_.material_slots) == slots_before
    assert object_.data.polygons[0].material_index == index_before
    assert not ui.reviewed_analysis_id
    bpy.data.materials.remove(unexpected_variant)


def _save_reopen_persistence() -> None:
    _clear_scene()
    image = _image("AMS_PERSIST_IMAGE")
    source, _tree, _principled, _texture = _material("AMS_PERSIST_SOURCE", image)
    object_ = _quad("AMS_PERSIST_OBJECT", source)
    analysis_id = _analyze(object_)
    assigned, state = _assign(analysis_id)
    assert assigned == {"FINISHED"}, state.last_status_json
    derived = object_.material_slots[1].material
    stored_fingerprint = derived[SOURCE_FINGERPRINT]

    output = Path(__file__).resolve().parents[2] / ".test-output" / "metadata-persistence.blend"
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=str(output), load_ui=False, use_scripts=False)
    object_ = bpy.data.objects.get("AMS_PERSIST_OBJECT")
    source = object_.material_slots[0].material
    derived = object_.material_slots[1].material
    state = inspect_metadata(derived)
    assert state.source == source, (
        state.kind,
        state.reason,
        state.source.name if state.source else None,
        source.name if source else None,
    )
    assert state.source_fingerprint == stored_fingerprint
    decision = resolve_derived_material(
        source, stored_fingerprint, conflict_policy="CANCEL_SOURCE_MATERIAL"
    )
    assert decision.action == "REUSE" and decision.material == derived, decision

    addon.unregister()
    assert not hasattr(bpy.types.Material, "alpha_material_separator_source")
    addon.register()
    object_ = bpy.data.objects.get("AMS_PERSIST_OBJECT")
    source = object_.material_slots[0].material
    derived = object_.material_slots[1].material
    assert inspect_metadata(derived).source == source


def run() -> None:
    _clear_scene()
    _direct_metadata_transitions()
    _assignment_slot_and_undo_transitions()
    _review_plan_transition()
    _save_reopen_persistence()
    print("ALPHA_MATERIAL_SEPARATOR_IDENTITY_TRANSITION_TESTS_OK")
