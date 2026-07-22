# SPDX-License-Identifier: GPL-3.0-or-later
"""Analysis, review, preview, and assignment panel."""

from __future__ import annotations

import json

import bpy

from . import runtime
from .adapters.assignment import build_assignment_plan


class ALPHA_MATERIAL_SEPARATOR_PT_main(bpy.types.Panel):
    """Display conservative analysis controls and reviewed report summaries."""

    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_main"
    bl_label = "Alpha Material Separator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Alpha Material"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.window_manager.alpha_material_separator_api
        settings = context.window_manager.alpha_material_separator_settings

        analysis = layout.box()
        analysis.label(text="Analyze Selected Base Meshes", icon="VIEWZOOM")
        analysis.prop(settings, "alpha_threshold")
        row = analysis.row(align=True)
        row.prop(settings, "min_affected_texels")
        row.prop(settings, "min_affected_fraction")
        analysis.prop(settings, "margin_texels")
        analysis.prop(settings, "address_mode")

        override = analysis.box()
        override.label(text="Optional Source Override")
        override.prop(settings, "image_override")
        override.prop(settings, "image_channel")
        override.prop(settings, "uv_map_name")

        operator = analysis.operator(
            "alpha_material_separator.analyze", text="Analyze", icon="PLAY"
        )
        operator.image_name = (
            settings.image_override.name if settings.image_override is not None else ""
        )
        operator.uv_map_name = settings.uv_map_name
        operator.image_channel = settings.image_channel
        operator.address_mode = settings.address_mode
        operator.alpha_threshold = settings.alpha_threshold
        operator.min_affected_texels = settings.min_affected_texels
        operator.min_affected_fraction = settings.min_affected_fraction
        operator.margin_texels = settings.margin_texels
        operator.max_scanlines = settings.max_scanlines
        operator.max_run_emissions = settings.max_run_emissions

        preview = layout.box()
        preview.label(text="Review and Preview", icon="FACESEL")
        preview.prop(settings, "preview_classes")
        preview.prop(settings, "enter_edit_mode")
        preview.enabled = bool(state.analysis_id)
        select_operator = preview.operator(
            "alpha_material_separator.select_faces",
            text="Preview Face Selection",
            icon="RESTRICT_SELECT_OFF",
        )
        select_operator.expected_analysis_id = state.analysis_id
        select_operator.classes = settings.preview_classes
        select_operator.enter_edit_mode = settings.enter_edit_mode

        assignment = layout.box()
        assignment.label(text="Assign Reviewed Materials", icon="MATERIAL")
        assignment.prop(settings, "mixed_policy")
        assignment.prop(settings, "suppressed_policy")
        assignment.prop(settings, "unsupported_policy")
        assignment.prop(settings, "derived_conflict_policy")
        current_report = runtime.report(state.analysis_id)
        if current_report is not None:
            plan = build_assignment_plan(
                current_report,
                mixed_policy=settings.mixed_policy,
                suppressed_policy=settings.suppressed_policy,
                unsupported_policy=settings.unsupported_policy,
                conflict_policy=settings.derived_conflict_policy,
            )
            assignment.label(
                text=f"Faces to reassign: {sum(len(item.face_indices) for item in plan.mutations)}"
            )
            assignment.label(text=f"Additional slots: {plan.planned_slots}")
            if plan.blocked:
                assignment.label(
                    text=f"Blocked material groups: {len(plan.blocked)}",
                    icon="ERROR",
                )
        assignment.enabled = bool(state.analysis_id)
        assign_operator = assignment.operator(
            "alpha_material_separator.assign_materials",
            text="Assign Material Slots",
            icon="CHECKMARK",
        )
        assign_operator.expected_analysis_id = state.analysis_id
        assign_operator.mixed_policy = settings.mixed_policy
        assign_operator.suppressed_policy = settings.suppressed_policy
        assign_operator.unsupported_policy = settings.unsupported_policy
        assign_operator.derived_conflict_policy = settings.derived_conflict_policy

        if runtime.dirty_reason():
            layout.label(text="Inputs changed; validation required", icon="ERROR")

        if state.analysis_id:
            try:
                report = json.loads(state.report_json)
            except (TypeError, json.JSONDecodeError):
                report = {}
            summary = layout.box()
            summary.label(text="Reviewed Analysis Summary")
            counts = report.get("counts", {})
            for key, label in (
                ("OPAQUE", "Opaque"),
                ("ALPHA_AFFECTED", "Alpha-affected"),
                ("MIXED", "Mixed"),
                ("SUPPRESSED", "Suppressed"),
                ("UNSUPPORTED", "Unsupported"),
            ):
                summary.label(text=f"{label}: {counts.get(key, 0)}")
            summary.label(
                text=(
                    "Materials create/reuse: "
                    f"{report.get('materials_to_create_or_reuse', 0)}"
                )
            )
            summary.label(
                text=(
                    "Estimated added slots/sections: "
                    f"{report.get('estimated_additional_material_slots', 0)}"
                )
            )
            if report.get("skip_counts"):
                summary.label(text="Unsafe objects will be skipped", icon="ERROR")

        status = layout.box()
        status.label(text=f"Analysis: {state.analysis_id or 'none'}")
        status.label(text=f"Status: {state.last_status_code}")
        row = status.row(align=True)
        row.operator(
            "alpha_material_separator.query_capabilities",
            text="Capabilities",
            icon="INFO",
        )
        row.operator(
            "alpha_material_separator.clear_results",
            text="Clear",
            icon="X",
        )
