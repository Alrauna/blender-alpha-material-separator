# SPDX-License-Identifier: GPL-3.0-or-later
"""Guided Simple and Expert Blender interface."""

from __future__ import annotations

import json
import textwrap

import bpy

from . import runtime
from .adapters.assignment import build_assignment_plan
from .overrides import dumps_material_overrides
from .presentation import (
    CLASS_COPY,
    classes_to_move,
    guidance_for,
    review_signature,
    workflow_view,
)


def _json(value: str) -> dict:
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _label_lines(layout, text: str, *, icon: str = "NONE", width: int = 34) -> None:
    """Draw readable copy in narrow sidebars where Blender does not wrap labels."""
    lines = textwrap.wrap(str(text), width=width, break_long_words=False) or [""]
    for index, line in enumerate(lines):
        layout.label(text=line, icon=icon if index == 0 else "NONE")


def _eligible_objects(context) -> tuple[bpy.types.Object, ...]:
    return tuple(obj for obj in context.selected_objects if obj.type == "MESH")


def _override_payload(settings) -> tuple[str, bool]:
    payload = []
    names = set()
    invalid = False
    for item in settings.material_overrides:
        if item.material is None:
            invalid = True
            continue
        name = item.material.name_full
        if name in names:
            invalid = True
        names.add(name)
        payload.append(
            {
                "address_mode": item.address_mode,
                "image_channel": item.image_channel if item.image else "ALPHA",
                "image_name": item.image.name_full if item.image else "",
                "material_name": name,
                "uv_map_name": item.uv_map_name,
            }
        )
    return dumps_material_overrides(payload), invalid


def _set_analysis_properties(operator, settings, material_overrides_json: str) -> None:
    operator.image_name = ""
    operator.uv_map_name = ""
    operator.image_channel = "ALPHA"
    operator.material_overrides_json = material_overrides_json
    operator.address_mode = settings.address_mode
    operator.alpha_threshold = settings.alpha_threshold
    operator.min_affected_texels = settings.min_affected_texels
    operator.min_affected_fraction = settings.min_affected_fraction
    operator.margin_texels = settings.margin_texels
    operator.max_scanlines = settings.max_scanlines
    operator.max_run_emissions = settings.max_run_emissions


def _policy_signature(state, settings) -> str:
    return review_signature(
        state.analysis_id,
        settings.mixed_policy,
        settings.suppressed_policy,
        settings.unsupported_policy,
        settings.derived_conflict_policy,
    )


def _plan(report, settings):
    if report is None:
        return None
    return build_assignment_plan(
        report,
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        conflict_policy=settings.derived_conflict_policy,
    )


def _draw_completion(layout, ui, state) -> None:
    payload = _json(ui.last_completion_json)
    if not payload and state.last_status_code.startswith("ASSIGNMENT_"):
        payload = _json(state.last_status_json)
    if not payload:
        return
    box = layout.box()
    code = payload.get("code", "")
    icon = "ERROR" if code == "ASSIGNMENT_BLOCKED" else "CHECKMARK"
    heading = {
        "ASSIGNMENT_COMPLETE": "Material separation complete",
        "ASSIGNMENT_COMPLETE_WITH_SKIPS": "Completed with skipped groups",
        "ASSIGNMENT_NO_CHANGES": "Already separated",
        "ASSIGNMENT_BLOCKED": "Nothing was changed",
    }.get(code, payload.get("message", "Material assignment finished"))
    box.label(text=heading, icon=icon)
    changes = payload.get("changes", {})
    if code == "ASSIGNMENT_NO_CHANGES":
        box.label(text="Already separated - no additional changes")
    else:
        box.label(text=f"Faces moved: {changes.get('changed_faces', 0)}")
        box.label(
            text=(
                "Alpha materials: "
                f"{changes.get('created_materials', 0)} created, "
                f"{changes.get('reused_materials', 0)} reused"
            )
        )
        box.label(text=f"Material slots added: {changes.get('added_material_slots', 0)}")
        skipped_groups = changes.get("skipped_material_groups", 0)
        if skipped_groups:
            box.label(text=f"Material groups skipped: {skipped_groups}", icon="ERROR")
        for item in changes.get("materials", ()):
            box.label(text=f"{item.get('source', '')} -> {item.get('derived', '')}")
    box.label(text="Ctrl+Z to undo.", icon="INFO")
    box.label(text="Analyze again to review another run.")
    box.label(text="Next: export the model to Unity.")
    box.label(text="Bind opaque and alpha materials there.")


def _draw_status_problem(layout, state) -> None:
    normal = {
        "NOT_QUERIED",
        "OK",
        "ANALYSIS_COMPLETE",
        "PREVIEW_COMPLETE",
        "ASSIGNMENT_COMPLETE",
        "ASSIGNMENT_COMPLETE_WITH_SKIPS",
        "ASSIGNMENT_NO_CHANGES",
        "CLEARED",
    }
    if state.last_status_code in normal:
        return
    payload = _json(state.last_status_json)
    title, remedy = guidance_for(state.last_status_code)
    box = layout.box()
    box.alert = True
    box.label(text=title, icon="ERROR")
    message = payload.get("message", "")
    if message and message != title:
        _label_lines(box, message)
    _label_lines(box, remedy)


class ALPHA_MATERIAL_SEPARATOR_UL_material_overrides(bpy.types.UIList):
    """Compact list of material-specific manual sources."""

    def draw_item(
        self, _context, layout, _data, item, _icon, _active_data, _active_propname, _index
    ) -> None:
        material_name = item.material.name if item.material else "Choose target material"
        image_name = item.image.name if item.image else "automatic image"
        layout.label(text=f"{material_name} - {image_name}", icon="MATERIAL")


class ALPHA_MATERIAL_SEPARATOR_PT_main(bpy.types.Panel):
    """Display the guided Analyze, Review, and Apply workflow."""

    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_main"
    bl_label = "Alpha Material Separator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Alpha Material"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        window_manager = context.window_manager
        state = window_manager.alpha_material_separator_api
        settings = window_manager.alpha_material_separator_settings
        ui = window_manager.alpha_material_separator_ui
        eligible = _eligible_objects(context)
        material_overrides_json, invalid_overrides = _override_payload(settings)
        current_report = runtime.report(state.analysis_id)
        report_payload = _json(state.report_json) if current_report else {}
        current_plan = _plan(current_report, settings)
        plan_payload = current_plan.public_payload() if current_plan else {}
        stale = bool(runtime.dirty_reason())
        reviewed = runtime.review_matches(
            window_manager, state.analysis_id, _policy_signature(state, settings)
        )
        actionable = bool(
            current_plan
            and (
                current_plan.mutations
                or any(
                    decision.action in {"CREATE", "REUSE"}
                    for decision in current_plan.decisions.values()
                )
            )
        )
        view = workflow_view(
            eligible_objects=len(eligible),
            running=ui.is_analyzing,
            has_report=bool(current_report),
            stale=stale,
            reviewed=reviewed,
            actionable=actionable,
            completed=bool(
                _json(ui.last_completion_json)
                or (
                    state.last_status_code.startswith("ASSIGNMENT_")
                    and _json(state.last_status_json)
                )
            ),
        )

        layout.label(text="Opaque faces keep the original material.")
        layout.label(text="Alpha faces use a copied material slot.")
        layout.prop(ui, "mode", expand=True)

        selection = layout.box()
        if eligible:
            selection.label(
                text=f"{len(eligible)} mesh object{'s' if len(eligible) != 1 else ''} selected",
                icon="CHECKMARK",
            )
        else:
            selection.alert = True
            _label_lines(
                selection,
                "Select one or more Mesh objects to begin.",
                icon="ERROR",
            )

        _draw_status_problem(layout, state)
        _draw_completion(layout, ui, state)

        analysis = layout.box()
        analysis.label(text="1. Analyze", icon="VIEWZOOM")
        analysis.label(text="Automatic image and UV detection.")
        if ui.is_analyzing:
            analysis.label(
                text=f"{ui.analysis_stage or 'Analyzing'} - {round(ui.analysis_progress * 100)}%"
            )
            analysis.label(text="Press Esc or click Cancel.")
            analysis.label(text="No partial result is kept.")
            analysis.operator(
                "alpha_material_separator.cancel_analysis",
                text="Cancel Analysis",
                icon="X",
            )
        else:
            if invalid_overrides:
                analysis.alert = True
                analysis.label(text="Finish or remove incomplete manual sources", icon="ERROR")
            row = analysis.row()
            row.enabled = bool(view["can_analyze"]) and not invalid_overrides
            operator = row.operator(
                "alpha_material_separator.analyze",
                text="Analyze Selected Meshes",
                icon="PLAY",
            )
            _set_analysis_properties(operator, settings, material_overrides_json)

        if current_report:
            review = layout.box()
            review.label(text="2. Review", icon="FACESEL")
            if stale:
                review.alert = True
                review.label(text="Inputs Changed - Analyze Again", icon="ERROR")
            else:
                review.label(
                    text=(
                        f"{report_payload.get('analyzed_polygon_count', 0)} faces across "
                        f"{report_payload.get('analyzed_object_count', 0)} objects"
                    )
                )
                counts = report_payload.get("counts", {})
                for key in (
                    "OPAQUE",
                    "ALPHA_AFFECTED",
                    "MIXED",
                    "SUPPRESSED",
                    "UNSUPPORTED",
                ):
                    count = counts.get(key, 0)
                    if count or key in {"OPAQUE", "ALPHA_AFFECTED"}:
                        review.label(text=f"{CLASS_COPY[key][0]}: {count}")
                row = review.row()
                row.enabled = bool(view["can_preview"])
                preview = row.operator(
                    "alpha_material_separator.select_faces",
                    text="Preview Faces to Move",
                    icon="RESTRICT_SELECT_OFF",
                )
                preview.expected_analysis_id = state.analysis_id
                preview.classes = set(
                    classes_to_move(settings.mixed_policy, settings.suppressed_policy)
                )
                preview.selection_mode = "REPLACE"
                preview.enter_edit_mode = True
                if reviewed:
                    review.label(text="Preview complete: selected faces use alpha.", icon="CHECKMARK")
                    review.label(text="Press Tab when finished inspecting.")

                shown_material_cards = set()
                for object_result in report_payload.get("objects", ()):
                    if object_result.get("skip_reason"):
                        title, remedy = guidance_for(object_result["skip_reason"])
                        warning = review.box()
                        warning.alert = True
                        warning.label(text=f"{object_result.get('name', 'Object')}: {title}", icon="ERROR")
                        _label_lines(warning, remedy)
                        continue
                    for group in object_result.get("groups", ()):
                        card_key = (
                            group.get("material"),
                            group.get("supported"),
                            group.get("resolution"),
                            group.get("image"),
                            group.get("uv_map"),
                            group.get("channel"),
                            group.get("address_mode"),
                            group.get("source_method"),
                            group.get("alpha_material"),
                        )
                        if card_key in shown_material_cards:
                            continue
                        shown_material_cards.add(card_key)
                        detail = review.box()
                        detail.label(text=group.get("material", "Material"), icon="MATERIAL")
                        if group.get("supported"):
                            detail.label(text=f"Image: {group.get('image') or 'automatic'}")
                            detail.label(
                                text=(
                                    f"UV: {group.get('uv_map') or 'active render UV'}  "
                                    f"Channel: {group.get('channel', 'ALPHA')}"
                                )
                            )
                            detail.label(text=f"To: {group.get('alpha_material', '')}")
                        else:
                            title, remedy = guidance_for(group.get("resolution"))
                            detail.alert = True
                            detail.label(text=title, icon="ERROR")
                            _label_lines(detail, remedy)
                            fix = detail.operator(
                                "alpha_material_separator.add_material_override",
                                text="Set Manual Alpha Source",
                            )
                            fix.material_name = group.get("material", "")

            assignment = layout.box()
            assignment.label(text="3. Apply", icon="MATERIAL")
            assignment.label(text=f"Faces to move: {plan_payload.get('faces_to_reassign', 0)}")
            assignment.label(
                text=f"Additional material slots: {plan_payload.get('planned_additional_slots', 0)}"
            )
            destinations = plan_payload.get("destinations", {})
            for source, derived in sorted(destinations.items()):
                assignment.label(text=f"{source} -> {derived}")
            if current_plan and current_plan.blocked:
                assignment.alert = True
                assignment.label(
                    text=f"Material groups skipped: {len(current_plan.blocked)}",
                    icon="ERROR",
                )
                for blocked in current_plan.blocked[:3]:
                    title, _remedy = guidance_for(blocked.get("reason"))
                    assignment.label(text=f"{blocked.get('material', '')}: {title}")
            if not reviewed and actionable and not stale:
                assignment.label(text="Preview the faces before applying.", icon="INFO")
            if not actionable and current_plan and current_plan.already_derived:
                assignment.label(text="Already separated - no additional changes", icon="CHECKMARK")
            elif not actionable and current_plan and current_plan.blocked:
                assignment.label(text="Resolve the skipped groups before applying.")
            row = assignment.row()
            row.enabled = bool(view["can_apply"])
            assign = row.operator(
                "alpha_material_separator.assign_materials",
                text="Apply Material Separation",
                icon="CHECKMARK",
            )
            assign.expected_analysis_id = state.analysis_id
            assign.mixed_policy = settings.mixed_policy
            assign.suppressed_policy = settings.suppressed_policy
            assign.unsupported_policy = settings.unsupported_policy
            assign.derived_conflict_policy = settings.derived_conflict_policy

        footer = layout.row(align=True)
        footer.operator(
            "alpha_material_separator.clear_results",
            text="Reset Results",
            icon="X",
        )


class _ExpertPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Alpha Material"
    bl_parent_id = "ALPHA_MATERIAL_SEPARATOR_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        ui = getattr(context.window_manager, "alpha_material_separator_ui", None)
        return ui is not None and ui.mode == "EXPERT"


class ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings(_ExpertPanel, bpy.types.Panel):
    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings"
    bl_label = "Expert Analysis Settings"

    def draw(self, context):
        layout = self.layout
        settings = context.window_manager.alpha_material_separator_settings
        layout.prop(settings, "alpha_threshold")
        layout.prop(settings, "min_affected_texels")
        layout.prop(settings, "min_affected_fraction")
        layout.prop(settings, "margin_texels")
        layout.prop(settings, "address_mode")
        limits = layout.box()
        limits.label(text="Deterministic Safety Limits")
        limits.prop(settings, "max_scanlines")
        limits.prop(settings, "max_run_emissions")


class ALPHA_MATERIAL_SEPARATOR_PT_overrides(_ExpertPanel, bpy.types.Panel):
    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_overrides"
    bl_label = "Manual Alpha Sources"

    def draw(self, context):
        layout = self.layout
        window_manager = context.window_manager
        settings = window_manager.alpha_material_separator_settings
        ui = window_manager.alpha_material_separator_ui
        layout.label(text="Materials not listed here stay automatic.")
        row = layout.row()
        row.template_list(
            "ALPHA_MATERIAL_SEPARATOR_UL_material_overrides",
            "",
            settings,
            "material_overrides",
            ui,
            "override_index",
            rows=2,
        )
        buttons = row.column(align=True)
        buttons.operator(
            "alpha_material_separator.add_material_override", text="", icon="ADD"
        )
        remove = buttons.operator(
            "alpha_material_separator.remove_material_override", text="", icon="REMOVE"
        )
        remove.index = ui.override_index
        if not settings.material_overrides:
            return
        index = min(ui.override_index, len(settings.material_overrides) - 1)
        item = settings.material_overrides[index]
        editor = layout.box()
        editor.prop(item, "material")
        editor.prop(item, "image")
        channel = editor.row()
        channel.enabled = item.image is not None
        channel.prop(item, "image_channel")
        if item.image is None:
            editor.label(text="No image: automatic image and Alpha channel are used.")
        editor.prop(item, "uv_map_name")
        editor.prop(item, "address_mode")


class ALPHA_MATERIAL_SEPARATOR_PT_inspection(_ExpertPanel, bpy.types.Panel):
    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_inspection"
    bl_label = "Inspect Other Classifications"

    def draw(self, context):
        layout = self.layout
        state = context.window_manager.alpha_material_separator_api
        settings = context.window_manager.alpha_material_separator_settings
        layout.prop(settings, "preview_classes")
        layout.prop(settings, "enter_edit_mode")
        row = layout.row()
        row.enabled = bool(state.analysis_id) and not runtime.dirty_reason()
        operator = row.operator(
            "alpha_material_separator.select_faces",
            text="Inspect Selected Classes",
            icon="RESTRICT_SELECT_OFF",
        )
        operator.expected_analysis_id = state.analysis_id
        operator.classes = settings.preview_classes
        operator.enter_edit_mode = settings.enter_edit_mode


class ALPHA_MATERIAL_SEPARATOR_PT_policies(_ExpertPanel, bpy.types.Panel):
    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_policies"
    bl_label = "Exception Policies"

    def draw(self, context):
        layout = self.layout
        state = context.window_manager.alpha_material_separator_api
        settings = context.window_manager.alpha_material_separator_settings
        report = _json(state.report_json)
        counts = report.get("counts", {})
        shown = False
        if counts.get("MIXED", 0):
            layout.prop(settings, "mixed_policy")
            shown = True
        if counts.get("SUPPRESSED", 0):
            layout.prop(settings, "suppressed_policy")
            shown = True
        if counts.get("UNSUPPORTED", 0):
            layout.prop(settings, "unsupported_policy")
            shown = True
        current_plan = _plan(runtime.report(state.analysis_id), settings)
        conflict_reasons = {
            item.get("reason")
            for item in (current_plan.blocked if current_plan else ())
        } - {"MIXED_FACES", "SUPPRESSED_FACES", "UNSUPPORTED_FACES"}
        if conflict_reasons:
            layout.prop(settings, "derived_conflict_policy")
            shown = True
        if not shown:
            layout.label(text="No exception policies are needed for this result.")


class ALPHA_MATERIAL_SEPARATOR_PT_technical(_ExpertPanel, bpy.types.Panel):
    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_technical"
    bl_label = "Technical Details"

    def draw(self, context):
        layout = self.layout
        state = context.window_manager.alpha_material_separator_api
        layout.label(text=f"Status code: {state.last_status_code}")
        layout.label(text=f"Analysis ID: {state.analysis_id or 'none'}")
        if runtime.dirty_reason():
            layout.label(text=f"Dirty hint: {runtime.dirty_reason()}")
        layout.operator(
            "alpha_material_separator.query_capabilities",
            text="Refresh Capability JSON",
            icon="INFO",
        )
