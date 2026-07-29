# SPDX-License-Identifier: GPL-3.0-or-later
"""Guided Simple and Expert Blender interface."""

from __future__ import annotations

import json

import bpy

from . import runtime
from .adapters.assignment import build_assignment_plan
from .overrides import dumps_material_overrides
from .presentation import (
    CLASS_COPY,
    alpha_source_advisory,
    already_separated_tooltip,
    classes_to_move,
    guidance_for,
    review_material_cards,
    review_signature,
    ui_text_lines,
    workflow_view,
)


def _json(value: str) -> dict:
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _label_lines(
    layout,
    text: str,
    *,
    icon: str = "NONE",
    available_width: int,
) -> None:
    """Draw readable copy in narrow sidebars where Blender does not wrap labels."""

    for index, line in enumerate(ui_text_lines(text, available_width)):
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


def _policy_signature(state, settings, plan_payload=None) -> str:
    return review_signature(
        state.analysis_id,
        settings.mixed_policy,
        settings.suppressed_policy,
        settings.unsupported_policy,
        settings.derived_conflict_policy,
        plan_payload,
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


def _draw_completion(layout, ui, state, *, available_width: int) -> None:
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
        "ASSIGNMENT_NO_CHANGES": payload.get("message", "No changes needed"),
        "ASSIGNMENT_BLOCKED": "Nothing was changed",
    }.get(code, payload.get("message", "Material assignment finished"))
    box.label(text=heading, icon=icon)
    changes = payload.get("changes", {})
    if code == "ASSIGNMENT_NO_CHANGES":
        _label_lines(
            box,
            payload.get("message", "No additional changes"),
            available_width=available_width,
        )
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
        skipped_objects = changes.get("skipped_objects", 0)
        if skipped_objects:
            box.label(text=f"Objects skipped: {skipped_objects}", icon="ERROR")
        partial_groups = changes.get("partial_material_groups", 0)
        if partial_groups:
            box.label(
                text=f"Partially changed material groups: {partial_groups}",
                icon="INFO",
            )
        retained_faces = changes.get("retained_faces_by_policy", 0)
        if retained_faces:
            box.label(
                text=f"Faces kept by policy: {retained_faces}",
                icon="INFO",
            )
        unchanged_groups = changes.get("unchanged_material_groups", 0)
        if unchanged_groups:
            box.label(
                text=f"Unresolved material groups left unchanged: {unchanged_groups}",
                icon="INFO",
            )
        for item in changes.get("materials", ()):
            box.label(text=f"{item.get('source', '')} -> {item.get('derived', '')}")
    box.label(text="Ctrl+Z to undo.", icon="INFO")
    box.label(text="Analyze again to review another run.")
    box.label(text="Next: export the model to Unity.")
    box.label(text="Bind opaque and alpha materials there.")


def _draw_status_problem(layout, state, *, available_width: int) -> None:
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
        _label_lines(box, message, available_width=available_width)
    _label_lines(box, remedy, available_width=available_width)


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
        region = getattr(context, "region", None)
        available_width = int(getattr(region, "width", 320) or 320)
        window_manager = context.window_manager
        state = window_manager.alpha_material_separator_api
        settings = window_manager.alpha_material_separator_settings
        ui = window_manager.alpha_material_separator_ui
        eligible = _eligible_objects(context)
        material_overrides_json, invalid_overrides = _override_payload(settings)
        current_report = runtime.report(state.analysis_id)
        report_payload = _json(state.report_json) if current_report else {}
        stale = bool(runtime.dirty_reason())
        try:
            current_plan = (
                _plan(current_report, settings)
                if current_report is not None and not stale
                else None
            )
        except (AttributeError, KeyError, ReferenceError, RuntimeError):
            current_plan = None
            stale = True
        plan_payload = current_plan.public_payload() if current_plan else {}
        reviewed = runtime.review_matches(
            window_manager,
            state.analysis_id,
            _policy_signature(state, settings, plan_payload),
        )
        actionable = bool(current_plan and current_plan.actionable)
        no_change_tooltip = already_separated_tooltip(
            already_derived=bool(current_plan and current_plan.already_derived),
            actionable=actionable,
        )
        already_separated = bool(no_change_tooltip)
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
                available_width=available_width,
            )

        _draw_status_problem(layout, state, available_width=available_width)
        _draw_completion(layout, ui, state, available_width=available_width)

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
                review.label(text="Inputs Changed — Analyze Again", icon="ERROR")
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
                preview.ui_description = no_change_tooltip
                preview.classes = set(
                    classes_to_move(settings.mixed_policy, settings.suppressed_policy)
                )
                preview.selection_mode = "REPLACE"
                preview.enter_edit_mode = True
                preview.preview_assignment_plan = True
                preview.mixed_policy = settings.mixed_policy
                preview.suppressed_policy = settings.suppressed_policy
                preview.unsupported_policy = settings.unsupported_policy
                preview.derived_conflict_policy = settings.derived_conflict_policy
                if reviewed:
                    review.label(text="Preview complete: selected faces use alpha.", icon="CHECKMARK")
                    review.label(text="Press Tab when finished inspecting.")

                for object_result in report_payload.get("objects", ()):
                    if object_result.get("skip_reason"):
                        title, remedy = guidance_for(object_result["skip_reason"])
                        warning = review.box()
                        warning.alert = True
                        warning.label(text=f"{object_result.get('name', 'Object')}: {title}", icon="ERROR")
                        _label_lines(
                            warning,
                            remedy,
                            available_width=available_width,
                        )

                material_cards = review_material_cards(report_payload)
                advisory = alpha_source_advisory(material_cards)
                if advisory:
                    notice = review.box()
                    _label_lines(
                        notice,
                        advisory[0],
                        icon="INFO",
                        available_width=available_width,
                    )
                    _label_lines(
                        notice,
                        advisory[1],
                        available_width=available_width,
                    )

                disclosure = review.row()
                disclosure.prop(
                    ui,
                    "show_material_details",
                    text=f"Material Details ({len(material_cards)})",
                    icon=(
                        "TRIA_DOWN"
                        if ui.show_material_details
                        else "TRIA_RIGHT"
                    ),
                    emboss=False,
                )
                if ui.show_material_details:
                    for group in material_cards:
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
                            face_local = group.get("unsupported_scopes", {}).get(
                                "FACE_LOCAL", 0
                            )
                            if face_local:
                                if settings.unsupported_policy == "TO_ALPHA":
                                    uncertain_action = "will use alpha"
                                elif settings.unsupported_policy == "KEEP_SOURCE":
                                    uncertain_action = "will stay on the source"
                                else:
                                    uncertain_action = "will skip this material group"
                                detail.label(
                                    text=(
                                        f"{face_local} uncertain face"
                                        f"{'s' if face_local != 1 else ''} "
                                        f"{uncertain_action}"
                                    ),
                                    icon="INFO",
                                )
                        else:
                            title, remedy = guidance_for(group.get("resolution"))
                            detail.label(
                                text="Left unchanged — no alpha source selected",
                                icon="INFO",
                            )
                            _label_lines(
                                detail,
                                title,
                                available_width=available_width,
                            )
                            _label_lines(
                                detail,
                                remedy,
                                available_width=available_width,
                            )
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
            uncertain_to_alpha = plan_payload.get(
                "face_local_unsupported_to_alpha", 0
            )
            if uncertain_to_alpha:
                assignment.label(
                    text=f"Uncertain faces moving to alpha: {uncertain_to_alpha}",
                    icon="INFO",
                )
            unchanged_groups = plan_payload.get(
                "material_source_groups_left_unchanged", 0
            )
            if unchanged_groups:
                assignment.label(
                    text=(
                        f"Unresolved material groups left unchanged: {unchanged_groups}"
                    ),
                    icon="INFO",
                )
            if current_plan and current_plan.blocked:
                assignment.alert = True
                assignment.label(
                    text=f"Material groups skipped: {len(current_plan.blocked)}",
                    icon="ERROR",
                )
                for blocked in current_plan.blocked[:3]:
                    title, remedy = guidance_for(blocked.get("reason"))
                    assignment.label(text=f"{blocked.get('material', '')}: {title}")
                    _label_lines(
                        assignment,
                        remedy,
                        available_width=available_width,
                    )
            if not reviewed and actionable and not stale:
                assignment.label(
                    text="Preview is optional; use it to inspect faces before applying.",
                    icon="INFO",
                )
            if already_separated:
                assignment.label(text="Already separated — no additional changes", icon="CHECKMARK")
            elif not actionable and current_plan and current_plan.blocked:
                assignment.label(text="No material group is safe to change.")
            elif not actionable and unchanged_groups:
                assignment.label(
                    text="Nothing can be separated until an alpha source is selected."
                )
            row = assignment.row()
            row.enabled = bool(view["can_apply"])
            assign = row.operator(
                "alpha_material_separator.assign_materials",
                text="Apply Material Separation",
                icon="CHECKMARK",
            )
            assign.expected_analysis_id = state.analysis_id
            assign.ui_description = no_change_tooltip
            assign.mixed_policy = settings.mixed_policy
            assign.suppressed_policy = settings.suppressed_policy
            assign.unsupported_policy = settings.unsupported_policy
            assign.derived_conflict_policy = settings.derived_conflict_policy
            assign.expected_review_signature = _policy_signature(
                state, settings, plan_payload
            )

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
        has_face_local_unsupported = any(
            group.get("unsupported_scopes", {}).get("FACE_LOCAL", 0)
            for object_result in report.get("objects", ())
            for group in object_result.get("groups", ())
        )
        if has_face_local_unsupported:
            layout.prop(settings, "unsupported_policy")
            shown = True
        current_plan = _plan(runtime.report(state.analysis_id), settings)
        conflict_reasons = {
            item.get("reason")
            for item in (current_plan.blocked if current_plan else ())
        } - {
            "FACE_LOCAL_UNSUPPORTED_FACES",
            "MIXED_FACES",
            "SUPPRESSED_FACES",
            "UNSUPPORTED_FACES",
        }
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
        layout.label(text=f"Validation: {runtime.validation_state()}")
        pending = sorted(runtime.pending_scopes())
        if pending:
            layout.label(text=f"Pending scopes: {', '.join(pending)}")
        if runtime.dirty_reason():
            layout.label(text=f"Confirmed stale: {runtime.dirty_reason()}")
        layout.operator(
            "alpha_material_separator.query_capabilities",
            text="Refresh Capability JSON",
            icon="INFO",
        )
