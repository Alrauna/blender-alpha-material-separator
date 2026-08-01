# SPDX-License-Identifier: GPL-3.0-or-later
"""Paired harmless/real-change report revalidation and Apply-race tests."""

from __future__ import annotations

import tempfile

import bpy

from addon import runtime
from addon.adapters.analysis import validate_report
from addon.adapters.assignment import build_assignment_plan
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad
from tests.blender.test_ux_overrides import _file_backed_image


class _Update:
    def __init__(self, datablock) -> None:
        self.id = datablock


class _Depsgraph:
    def __init__(self, *datablocks) -> None:
        self.updates = tuple(_Update(datablock) for datablock in datablocks)


def _hint(*datablocks) -> None:
    runtime._depsgraph_hint(None, _Depsgraph(*datablocks))


def _select_only(*objects) -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for object_ in objects:
        object_.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def _analyze_and_review(*objects) -> tuple[object, str]:
    _select_only(*objects)
    analyzed = bpy.ops.alpha_material_separator.analyze()
    assert analyzed == {"FINISHED"}, analyzed
    state = bpy.context.window_manager.alpha_material_separator_api
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
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
    assert ui.reviewed_analysis_id == state.analysis_id
    return runtime.report(state.analysis_id), ui.reviewed_policy_signature


def _apply_must_refuse_without_mutation(
    object_,
    report,
    review_signature: str,
) -> None:
    state = bpy.context.window_manager.alpha_material_separator_api
    slots_before = tuple(
        slot.material.as_pointer() if slot.material else 0
        for slot in object_.material_slots
    )
    indices_before = tuple(
        polygon.material_index for polygon in object_.data.polygons
    )
    result = bpy.ops.alpha_material_separator.assign_materials(
        expected_analysis_id=report.analysis_id,
        expected_review_signature=review_signature,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert result == {"CANCELLED"}, state.last_status_json
    assert state.last_status_code in {"STALE_ANALYSIS", "REVIEW_CHANGED"}, (
        state.last_status_json
    )
    assert tuple(
        slot.material.as_pointer() if slot.material else 0
        for slot in object_.material_slots
    ) == slots_before
    assert tuple(
        polygon.material_index for polygon in object_.data.polygons
    ) == indices_before


def _stable_scene(name: str, directory: str):
    _clear_scene()
    runtime.clear()
    image = _file_backed_image(f"{name}_IMAGE", directory)
    material, tree, principled, texture = _material(f"{name}_MATERIAL", image)
    first = _quad(f"{name}_FIRST", material)
    second = _quad(f"{name}_SECOND", material)
    second.location.x = 2.0
    return image, material, tree, principled, texture, first, second


def _connect_unsupported_alpha(_object, _material, principled) -> None:
    tree = principled.id_data
    value = tree.nodes.new("ShaderNodeValue")
    tree.links.new(value.outputs["Value"], principled.inputs["Alpha"])


def run() -> None:
    temporary_images = tempfile.TemporaryDirectory(prefix="ams-revalidation-")

    # Real Preview -> multi-object Edit Mode -> selection -> Tab transitions.
    (
        image,
        material,
        _tree,
        _principled,
        _texture,
        first,
        second,
    ) = _stable_scene("AMS_HARMLESS", temporary_images.name)
    _select_only(first, second)
    analyzed = bpy.ops.alpha_material_separator.analyze()
    assert analyzed == {"FINISHED"}, analyzed
    state = bpy.context.window_manager.alpha_material_separator_api
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        preview_assignment_plan=True,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert preview == {"FINISHED"}, state.last_status_json
    ui = bpy.context.window_manager.alpha_material_separator_ui
    analysis_id = state.analysis_id
    review_token = ui.reviewed_policy_signature
    sentinel = object()
    runtime.coverage_set("AMS_MATRIX_SENTINEL", sentinel)

    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    _hint(first.data, second.data, first, second)
    report = runtime.report(analysis_id)
    valid, reason = validate_report(report)
    assert valid and reason == "OK", reason
    snapshot = runtime.snapshot()
    assert state.analysis_id == analysis_id
    assert ui.reviewed_policy_signature == review_token
    assert snapshot["last_validation_component_hash_calls"] == 1, snapshot
    assert snapshot["last_validation_image_digest_rows"] == 0, snapshot
    assert snapshot["last_validation_rasterized_polygons"] == 0, snapshot
    assert snapshot["last_validation_coverage_hits"] == 0, snapshot
    assert snapshot["last_validation_coverage_misses"] == 0, snapshot
    assert snapshot["last_validation_elapsed_seconds"] >= 0.0, snapshot
    assert runtime.coverage_get("AMS_MATRIX_SENTINEL") is sentinel

    bpy.context.view_layer.objects.active = second
    _hint(second)
    valid, reason = validate_report(report)
    assert valid and reason == "OK", reason
    assert state.analysis_id == analysis_id
    assert ui.reviewed_policy_signature == review_token

    repeat_preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=analysis_id,
        preview_assignment_plan=True,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert repeat_preview == {"FINISHED"}, state.last_status_json
    bpy.ops.object.mode_set(mode="OBJECT")
    _hint(first.data, second.data)
    valid, reason = validate_report(report)
    assert valid and reason == "OK", reason
    assert state.analysis_id == analysis_id
    assert ui.reviewed_policy_signature == review_token

    unrelated_image = bpy.data.images.new(
        "AMS_MATRIX_UNRELATED_IMAGE", width=1, height=1, alpha=True
    )
    unrelated_material = bpy.data.materials.new("AMS_MATRIX_UNRELATED_MATERIAL")
    unrelated_object = bpy.data.objects.new(
        "AMS_MATRIX_UNRELATED_OBJECT",
        bpy.data.meshes.new("AMS_MATRIX_UNRELATED_MESH"),
    )
    bpy.context.collection.objects.link(unrelated_object)
    generation_before = runtime.snapshot()["hint_generation"]
    _hint(
        unrelated_image,
        unrelated_material,
        unrelated_object,
        unrelated_object.data,
    )
    assert runtime.snapshot()["hint_generation"] == generation_before
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN

    # Ancillary texture pixels are not classification inputs. Editing the
    # surrounding source graph retains classification but requires a fresh
    # exact-plan review because the copied derived material would differ.
    (
        _authority_image,
        authority_material,
        authority_tree,
        authority_principled,
        _authority_texture,
        authority_object,
        _unused,
    ) = _stable_scene("AMS_AUTHORITY_ONLY", temporary_images.name)
    ancillary_image = _image("AMS_AUTHORITY_ONLY_NORMAL")
    ancillary_texture = authority_tree.nodes.new("ShaderNodeTexImage")
    ancillary_texture.image = ancillary_image
    normal_map = authority_tree.nodes.new("ShaderNodeNormalMap")
    authority_tree.links.new(
        ancillary_texture.outputs["Color"], normal_map.inputs["Color"]
    )
    authority_tree.links.new(
        normal_map.outputs["Normal"], authority_principled.inputs["Normal"]
    )
    report, reviewed_signature = _analyze_and_review(authority_object)
    analysis_id = report.analysis_id

    ancillary_image.pixels[3] = 0.25
    ancillary_image.update()
    _hint(ancillary_image)
    valid, reason = validate_report(report)
    assert valid and reason == "OK", reason
    snapshot = runtime.snapshot()
    ui = bpy.context.window_manager.alpha_material_separator_ui
    assert runtime.report(analysis_id) is report
    assert ui.reviewed_policy_signature == reviewed_signature
    assert snapshot["last_validation_image_digest_rows"] == 0, snapshot

    normal_map.inputs["Strength"].default_value = 0.25
    _hint(authority_material)
    valid, reason = validate_report(report)
    assert valid and reason == "OK", reason
    snapshot = runtime.snapshot()
    assert runtime.report(analysis_id) is report
    assert not ui.reviewed_analysis_id
    assert not runtime.review_matches(
        bpy.context.window_manager,
        analysis_id,
        reviewed_signature,
    )
    assert snapshot["last_validation_image_digest_rows"] == 0, snapshot

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
    assert preview == {"FINISHED"}, preview
    assert ui.reviewed_policy_signature
    assert ui.reviewed_policy_signature != reviewed_signature

    # Vertex, UV, slot, shader, and topology changes are paired with the
    # harmless sequence above and must refuse Apply before any mutation.
    structural_cases = (
        (
            "VERTEX",
            lambda object_, _material, _principled: setattr(
                object_.data.vertices[0].co,
                "x",
                object_.data.vertices[0].co.x + 0.125,
            ),
            lambda object_, material: object_.data,
        ),
        (
            "UV",
            lambda object_, _material, _principled: setattr(
                object_.data.uv_layers.active.uv[0].vector,
                "x",
                object_.data.uv_layers.active.uv[0].vector.x + 0.125,
            ),
            lambda object_, material: object_.data,
        ),
        (
            "SHADER",
            _connect_unsupported_alpha,
            lambda object_, material: material,
        ),
    )
    for case_name, mutate, hinted_datablock in structural_cases:
        (
            _image_data,
            case_material,
            _case_tree,
            case_principled,
            _case_texture,
            case_object,
            _unused,
        ) = _stable_scene(f"AMS_TRUE_{case_name}", temporary_images.name)
        report, reviewed_signature = _analyze_and_review(case_object)
        mutate(case_object, case_material, case_principled)
        _hint(hinted_datablock(case_object, case_material))
        _apply_must_refuse_without_mutation(
            case_object, report, reviewed_signature
        )
        assert runtime.validation_state() == runtime.VALIDATION_STALE
        assert not bpy.context.window_manager.alpha_material_separator_ui.reviewed_analysis_id

    # A slot-content change is identity-sensitive even if topology is unchanged.
    (
        _slot_image,
        slot_material,
        _slot_tree,
        _slot_principled,
        _slot_texture,
        slot_object,
        _unused,
    ) = _stable_scene("AMS_TRUE_SLOT", temporary_images.name)
    report, reviewed_signature = _analyze_and_review(slot_object)
    replacement = bpy.data.materials.new("AMS_TRUE_SLOT_REPLACEMENT")
    slot_object.material_slots[0].material = replacement
    _hint(slot_object, slot_object.data)
    _apply_must_refuse_without_mutation(
        slot_object, report, reviewed_signature
    )

    # Generated/already-dirty images may not use the structural-only shortcut.
    _clear_scene()
    runtime.clear()
    generated = _image("AMS_TRUE_GENERATED_IMAGE")
    generated_material, _tree, _principled, _texture = _material(
        "AMS_TRUE_GENERATED_MATERIAL", generated
    )
    generated_object = _quad("AMS_TRUE_GENERATED_OBJECT", generated_material)
    report, reviewed_signature = _analyze_and_review(generated_object)
    current_alpha = float(generated.pixels[3])
    generated.pixels[3] = 1.0 if current_alpha < 0.5 else 0.0
    generated.update()
    _hint(generated_object.data)
    _apply_must_refuse_without_mutation(
        generated_object, report, reviewed_signature
    )
    generated_snapshot = runtime.snapshot()
    assert generated_snapshot["last_validation_mode"] == "FULL", (
        generated_snapshot
    )
    assert generated_snapshot["last_validation_image_digest_rows"] > 0, (
        generated_snapshot
    )

    # A known analysis-setting edit is authoritatively stale without waiting
    # for a depsgraph event.
    (
        _settings_image,
        _settings_material,
        _settings_tree,
        _settings_principled,
        _settings_texture,
        settings_object,
        _unused,
    ) = _stable_scene("AMS_TRUE_SETTINGS", temporary_images.name)
    report, reviewed_signature = _analyze_and_review(settings_object)
    settings = bpy.context.window_manager.alpha_material_separator_settings
    original_threshold = settings.alpha_threshold
    settings.alpha_threshold = max(0.0, original_threshold - 0.01)
    _apply_must_refuse_without_mutation(
        settings_object, report, reviewed_signature
    )
    settings.alpha_threshold = original_threshold

    # File-load, undo, and redo handlers conservatively discard transient
    # reports and review state. The handler is shared by all three registrations.
    report, _reviewed_signature = _analyze_and_review(settings_object)
    assert runtime.report(report.analysis_id) is report
    runtime._clear_on_file_state_change()
    assert runtime.report() is None
    assert not bpy.context.window_manager.alpha_material_separator_ui.reviewed_analysis_id

    temporary_images.cleanup()
    print("ALPHA_MATERIAL_SEPARATOR_REVALIDATION_MATRIX_TESTS_OK")
