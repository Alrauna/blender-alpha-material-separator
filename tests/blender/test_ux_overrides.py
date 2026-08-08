# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for UI state, review gating, and per-material overrides."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import bpy

from addon import api_contract, runtime
from addon.adapters import analysis as analysis_adapter
from addon.adapters.assignment import build_assignment_plan
from addon.operators.assign_materials import (
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials,
)
from addon.operators.select_faces import ALPHA_MATERIAL_SEPARATOR_OT_select_faces
from addon.panel import (
    ALPHA_MATERIAL_SEPARATOR_PT_main,
    _draw_completion,
    _label_lines,
    _override_payload,
)
from addon.presentation import review_signature
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad


class _RecordingLayout:
    def __init__(self, root=None):
        self.root = root or self
        if root is None:
            self.labels = []
            self.properties = []

    def _child(self):
        return _RecordingLayout(self.root)

    def box(self):
        return self._child()

    def row(self, **_kwargs):
        return self._child()

    def label(self, *, text="", icon="NONE"):
        self.root.labels.append((text, icon))

    def prop(self, _data, property_name, **kwargs):
        self.root.properties.append((property_name, kwargs))

    def operator(self, *_args, **_kwargs):
        return SimpleNamespace()

    def separator(self):
        pass


def _draw_main_panel(region_width=None):
    layout = _RecordingLayout()
    context = bpy.context
    if region_width is not None:
        context = SimpleNamespace(
            region=SimpleNamespace(width=region_width),
            selected_objects=bpy.context.selected_objects,
            window_manager=bpy.context.window_manager,
        )
    ALPHA_MATERIAL_SEPARATOR_PT_main.draw(
        SimpleNamespace(layout=layout), context
    )
    return layout


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


def _counts_for(override_json: str) -> dict[str, int]:
    result = bpy.ops.alpha_material_separator.analyze(
        api_major=1, material_overrides_json=override_json
    )
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    return json.loads(state.report_json)["counts"]


def _assert_panel_built_overrides_change_the_result(manual_material, override_image):
    """Prove the panel's payload reaches classification, by counts not by pixels."""

    settings = bpy.context.window_manager.alpha_material_separator_settings
    settings.material_overrides.clear()
    baseline = _counts_for("[]")

    item = settings.material_overrides.add()
    item.material = manual_material
    payload, invalid = _override_payload(settings)
    assert not invalid, payload
    assert json.loads(payload)[0]["image_name"] == "", payload
    # An override with no image resolves through the automatic path that already
    # failed, so the panel currently lets a user build a no-op. Counts prove it.
    assert _counts_for(payload) == baseline, payload

    item.image = override_image
    item.image_channel = "RED"
    payload, invalid = _override_payload(settings)
    assert not invalid, payload
    assert json.loads(payload)[0]["image_channel"] == "RED", payload
    changed = _counts_for(payload)
    assert changed != baseline, (changed, baseline)
    assert changed["UNSUPPORTED"] < baseline["UNSUPPORTED"], (changed, baseline)

    settings.material_overrides.clear()


def run() -> None:
    sentence = "Open Material Details below to review it."

    wide_layout = _RecordingLayout()
    _label_lines(wide_layout, sentence, icon="INFO", available_width=560)
    assert wide_layout.labels == [(sentence, "INFO")]

    narrow_layout = _RecordingLayout()
    _label_lines(narrow_layout, sentence, icon="INFO", available_width=180)
    assert len(narrow_layout.labels) > 1, narrow_layout.labels
    assert " ".join(text for text, _icon in narrow_layout.labels) == sentence
    assert narrow_layout.labels[0][1] == "INFO"
    assert all(icon == "NONE" for _text, icon in narrow_layout.labels[1:])

    tooltip = (
        "All faces on the selected meshes are optimally assigned. "
        "No faces need to be moved."
    )
    for operator_type in (
        ALPHA_MATERIAL_SEPARATOR_OT_select_faces,
        ALPHA_MATERIAL_SEPARATOR_OT_assign_materials,
    ):
        assert (
            operator_type.description(
                None, SimpleNamespace(ui_description=tooltip)
            )
            == tooltip
        )
        assert (
            operator_type.description(None, SimpleNamespace(ui_description=""))
            == operator_type.bl_description
        )

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
    ui = bpy.context.window_manager.alpha_material_separator_ui
    ui.show_material_details = True
    analyzed = bpy.ops.alpha_material_separator.analyze(
        api_major=1, material_overrides_json=override_json
    )
    assert analyzed == {"FINISHED"}, analyzed
    assert not ui.show_material_details
    state = bpy.context.window_manager.alpha_material_separator_api
    payload = json.loads(state.report_json)
    groups = {
        group["material"]: group
        for object_payload in payload["objects"]
        for group in object_payload.get("groups", ())
    }
    assert groups[auto_material.name]["source_kind"] == "UNIQUE_BASE_COLOR_IMAGE_ALPHA"
    assert (
        groups[auto_material.name]["source_method"]
        == groups[auto_material.name]["source_kind"]
    )
    assert groups[auto_material.name]["channel"] == "ALPHA"
    assert groups[manual_material.name]["source_kind"] == "EXPLICIT_OVERRIDE"
    assert groups[manual_material.name]["channel"] == "RED"
    assert groups[manual_material.name]["image"] == override_image.name
    assert groups[manual_material.name]["uv_map"] == "UVMap"
    _assert_panel_built_overrides_change_the_result(manual_material, override_image)
    assert payload["counts"]["MIXED"] == 1, payload
    assert payload["counts"]["OPAQUE"] == 1, payload

    collapsed = _draw_main_panel()
    disclosure = next(
        entry
        for entry in collapsed.properties
        if entry[0] == "show_material_details"
    )
    assert disclosure[1]["text"] == "Material Details (2)"
    assert disclosure[1]["icon"] == "TRIA_RIGHT"
    ui.show_material_details = True
    expanded = _draw_main_panel()
    disclosure = next(
        entry for entry in expanded.properties if entry[0] == "show_material_details"
    )
    assert disclosure[1]["icon"] == "TRIA_DOWN"

    original_report_json = state.report_json
    unsupported_payload = json.loads(original_report_json)
    unsupported_group = unsupported_payload["objects"][0]["groups"][0]
    unsupported_group["supported"] = False
    unsupported_group["resolution"] = "NO_AUTHORITATIVE_ALPHA_IMAGE"
    state.report_json = json.dumps(unsupported_payload)
    try:
        unsupported_panel = _draw_main_panel()
        assert (
            "Left unchanged — no alpha source selected",
            "INFO",
        ) in unsupported_panel.labels
        narrow_panel = _draw_main_panel(region_width=180)
        assert (
            "1 material may need an alpha source.",
            "INFO",
        ) not in narrow_panel.labels
        assert ("1 material may need", "INFO") in narrow_panel.labels
        assert ("an alpha source.", "NONE") in narrow_panel.labels
    finally:
        state.report_json = original_report_json
        ui.show_material_details = False

    active_report = runtime.report(state.analysis_id)
    assert active_report is not None
    runtime.mark_dirty("SETTINGS_CHANGED")
    stale_panel = _draw_main_panel()
    assert ("Inputs Changed — Analyze Again", "ERROR") in stale_panel.labels
    runtime.set_report(active_report)

    completion_layout = _RecordingLayout()
    _draw_completion(
        completion_layout,
        SimpleNamespace(
            last_completion_json=api_contract.dumps(
                api_contract.status_payload(
                    "ASSIGNMENT_NO_CHANGES",
                    "Already separated — no additional changes",
                    changes={},
                )
            )
        ),
        SimpleNamespace(last_status_code="", last_status_json="{}"),
        available_width=420,
    )
    assert (
        "Already separated — no additional changes",
        "CHECKMARK",
    ) in completion_layout.labels

    unrelated_image = bpy.data.images.new(
        "AMS_UX_UNRELATED_IMAGE", width=1, height=1, alpha=True
    )
    assert runtime._relevant_update_scope(automatic_object) == "OBJECT"
    assert runtime._relevant_update_scope(automatic_object.data) == "MESH"
    assert runtime._relevant_update_scope(auto_material) == "MATERIAL"
    assert runtime._relevant_update_scope(auto_image) == "IMAGE"
    assert runtime._relevant_update_scope(unrelated_image) == ""

    settings = bpy.context.window_manager.alpha_material_separator_settings
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
    assert automatic_object.mode == "EDIT"
    assert manual_object.mode == "OBJECT" and not manual_object.select_get()
    reviewed_plan = build_assignment_plan(
        runtime.report(state.analysis_id),
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        conflict_policy=settings.derived_conflict_policy,
    ).public_payload()
    signature = review_signature(
        state.analysis_id,
        settings.mixed_policy,
        settings.suppressed_policy,
        settings.unsupported_policy,
        settings.derived_conflict_policy,
        reviewed_plan,
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
    pending_scopes = set(json.loads(state.pending_scopes_json))
    assert "MESH" in pending_scopes
    assert pending_scopes <= {"MESH", "OBJECT"}, pending_scopes
    assert not runtime.dirty_reason()
    assert runtime.review_matches(
        bpy.context.window_manager, state.analysis_id, signature
    )
    reviewed_state = (
        state.analysis_id,
        ui.reviewed_analysis_id,
        ui.reviewed_policy_signature,
    )
    ui.show_material_details = True
    assert (
        state.analysis_id,
        ui.reviewed_analysis_id,
        ui.reviewed_policy_signature,
    ) == reviewed_state
    ui.show_material_details = False
    assert (
        state.analysis_id,
        ui.reviewed_analysis_id,
        ui.reviewed_policy_signature,
    ) == reviewed_state
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

    raw_preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        classes={"ALPHA_AFFECTED", "MIXED"},
        selection_mode="REPLACE",
        enter_edit_mode=False,
    )
    assert raw_preview == {"FINISHED"}, raw_preview
    assert not ui.reviewed_analysis_id, ui.reviewed_analysis_id
    exact_preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        selection_mode="REPLACE",
        enter_edit_mode=False,
        preview_assignment_plan=True,
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        derived_conflict_policy=settings.derived_conflict_policy,
    )
    assert exact_preview == {"FINISHED"}, exact_preview
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
    runtime.set_review(
        bpy.context.window_manager,
        prior_report.analysis_id,
        "AMS_PRIOR_REVIEW_TOKEN",
    )
    ui.show_material_details = True
    assert runtime.begin_analysis(bpy.context.window_manager)
    assert ui.analysis_stage == "Preparing Inputs"
    assert not ui.analysis_progress_visible
    runtime.update_analysis(bpy.context.window_manager, 5, 10, "Reading Textures")
    assert ui.analysis_progress_visible
    runtime.update_analysis(bpy.context.window_manager, 3, 10, "Reading Textures")
    assert ui.analysis_progress == 0.5, ui.analysis_progress
    runtime.update_analysis(
        bpy.context.window_manager,
        10,
        10,
        "Validating Inputs",
        show_progress=False,
    )
    assert ui.analysis_stage == "Validating Inputs"
    assert not ui.analysis_progress_visible
    assert ui.analysis_progress == 0.5, ui.analysis_progress
    runtime.update_analysis(
        bpy.context.window_manager,
        10,
        10,
        "Analysis Complete",
    )
    assert ui.analysis_progress_visible
    assert ui.analysis_progress == 1.0, ui.analysis_progress
    cancel = bpy.ops.alpha_material_separator.cancel_analysis()
    assert cancel == {"FINISHED"}, cancel
    assert runtime.cancellation_requested(bpy.context.window_manager)
    runtime.finish_analysis(bpy.context.window_manager)
    assert not ui.is_analyzing and ui.analysis_progress == 0.0
    assert not ui.analysis_progress_visible
    assert runtime.report() is prior_report
    assert ui.reviewed_analysis_id == prior_report.analysis_id
    assert ui.reviewed_policy_signature == "AMS_PRIOR_REVIEW_TOKEN"
    assert ui.show_material_details
    temporary_images.cleanup()
    print("ALPHA_MATERIAL_SEPARATOR_UX_OVERRIDE_TESTS_OK")
