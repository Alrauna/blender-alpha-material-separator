# SPDX-License-Identifier: GPL-3.0-or-later
"""Atomic undoable material-slot assignment from a reviewed analysis."""

from __future__ import annotations

import json

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from .. import api_contract, runtime
from ..adapters.analysis import validate_report
from ..adapters.assignment import build_assignment_plan, execute_assignment_plan
from ..presentation import (
    _UI_AVERAGE_CHARACTER_WIDTH,
    assignment_confirmation_lines,
    assignment_plan_signature,
    requires_confirmation,
    review_signature,
    ui_text_lines,
)

_CONFIRMATION_MIN_WIDTH = 420
_CONFIRMATION_MAX_WIDTH = 560
_CONFIRMATION_WINDOW_MARGIN = 64
_CONFIRMATION_TEXT_PADDING = 32
_CONFIRMATION_TITLE = "Apply Material Separation"
_CONFIRMATION_TEXT = "Apply"
_ADJUST_LAST_OPERATION_FALLBACK_WIDTH = 220


def _confirmation_dialog_width(
    lines: tuple[str, ...],
    window_width: int,
) -> int:
    longest = max((len(line) for line in lines), default=0)
    preferred = max(
        _CONFIRMATION_MIN_WIDTH,
        min(
            _CONFIRMATION_MAX_WIDTH,
            longest * _UI_AVERAGE_CHARACTER_WIDTH
            + _CONFIRMATION_TEXT_PADDING,
        ),
    )
    usable_window = max(1, int(window_width) - _CONFIRMATION_WINDOW_MARGIN)
    return min(preferred, usable_window)


def _validated_plan(operator, context):
    if operator.api_major != api_contract.API_VERSION[0]:
        operator._status(context, "API_INCOMPATIBLE", "Unsupported API major")
        return None
    report = runtime.report(operator.expected_analysis_id)
    if report is None:
        operator._status(
            context, "ANALYSIS_ID_MISMATCH", "The reviewed analysis is unavailable"
        )
        return None
    if runtime.dirty_reason() == "SETTINGS_CHANGED":
        operator._status(context, "STALE_ANALYSIS", "Analysis settings changed")
        return None
    valid, reason = validate_report(report)
    if not valid:
        operator._status(
            context,
            "STALE_ANALYSIS",
            "Analysis inputs changed; run analysis again",
            reason=reason,
        )
        return None
    plan = build_assignment_plan(
        report,
        mixed_policy=operator.mixed_policy,
        suppressed_policy=operator.suppressed_policy,
        unsupported_policy=operator.unsupported_policy,
        conflict_policy=operator.derived_conflict_policy,
    )
    plan_payload = plan.public_payload()
    current_review_signature = review_signature(
        report.analysis_id,
        operator.mixed_policy,
        operator.suppressed_policy,
        operator.unsupported_policy,
        operator.derived_conflict_policy,
        plan_payload,
    )
    if (
        operator.expected_review_signature
        and current_review_signature != operator.expected_review_signature
    ):
        runtime.clear_review(context.window_manager)
        operator._status(
            context,
            "REVIEW_CHANGED",
            "The material plan changed after preview; preview the faces again",
            plan=plan_payload,
        )
        return None
    return report, plan, plan_payload


class ALPHA_MATERIAL_SEPARATOR_OT_assign_materials(bpy.types.Operator):
    """Assign reviewed face groups to safe local derived materials."""

    bl_idname = "alpha_material_separator.assign_materials"
    bl_label = "Assign Alpha Materials"
    bl_description = "Create or reuse local alpha variants and assign reviewed faces"
    bl_options = {"REGISTER", "UNDO"}

    api_major: IntProperty(name="API Major", default=1, min=1)
    expected_analysis_id: StringProperty(name="Expected Analysis ID", default="")
    ui_description: StringProperty(
        default="", options={"HIDDEN", "SKIP_SAVE"}
    )
    expected_review_signature: StringProperty(
        name="Expected Review Signature",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    mixed_policy: EnumProperty(
        name="Mixed Faces",
        items=(
            ("TO_ALPHA", "Move to Alpha", "Move mixed faces to the alpha variant"),
            ("KEEP_SOURCE", "Keep Source", "Leave mixed faces on the source"),
            (
                "CANCEL_SOURCE_MATERIAL",
                "Skip this entire material group",
                "Do not change any faces using this source material",
            ),
        ),
        default="TO_ALPHA",
    )
    suppressed_policy: EnumProperty(
        name="Suppressed Evidence",
        items=(
            (
                "CANCEL_SOURCE_MATERIAL",
                "Skip this entire material group",
                "Conservative default",
            ),
            ("TO_ALPHA", "Move to Alpha", "Move after informed review"),
            ("KEEP_SOURCE", "Keep Source", "Leave after informed review"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
    unsupported_policy: EnumProperty(
        name="Unsupported Faces",
        items=(
            (
                "CANCEL_SOURCE_MATERIAL",
                "Skip this entire material group",
                "Conservative default",
            ),
            ("KEEP_SOURCE", "Keep Source", "Leave unsupported faces unchanged"),
            (
                "TO_ALPHA",
                "Move Face-Local Uncertainty to Alpha",
                "Move only uncertain faces whose material alpha source was resolved",
            ),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
    derived_conflict_policy: EnumProperty(
        name="Derived Conflict",
        items=(
            (
                "CANCEL_SOURCE_MATERIAL",
                "Skip this entire material group",
                "Preserve conflicting data",
            ),
            ("REUSE_EXISTING", "Reuse Existing", "Explicitly retain the existing variant"),
            ("CREATE_NEW_VARIANT", "Create New", "Preserve old variant and create another"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )

    _confirmation_plan_json = "{}"
    _confirmation_plan_signature = ""
    _confirmation_previewed = True
    _confirmation_draw_width = _CONFIRMATION_MIN_WIDTH

    @classmethod
    def description(cls, _context, properties):
        return properties.ui_description or cls.bl_description

    def _status(self, context, code: str, message: str, **details) -> None:
        state = context.window_manager.alpha_material_separator_api
        api_contract.publish_status(state, code, message, **details)

    def invoke(self, context: bpy.types.Context, _event) -> set[str]:
        """Show a warning summary only when the reviewed plan needs attention."""
        self._confirmation_plan_signature = ""
        restore_edit_mode = (
            context.object is not None and context.object.mode == "EDIT"
        )
        if restore_edit_mode:
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            prepared = _validated_plan(self, context)
        finally:
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
        if prepared is None:
            return {"CANCELLED"}
        report, plan, plan_payload = prepared
        previewed = (
            not self.expected_review_signature
            or runtime.review_matches(
                context.window_manager,
                report.analysis_id,
                self.expected_review_signature,
            )
        )
        self._confirmation_previewed = previewed
        actionable = plan.actionable
        if not actionable:
            return self.execute(context)
        if previewed and not requires_confirmation(
            report.public_payload(),
            plan_payload,
        ):
            return self.execute(context)
        lines = assignment_confirmation_lines(
            plan_payload,
            previewed=previewed,
        )
        self._confirmation_draw_width = _confirmation_dialog_width(
            lines,
            context.window.width,
        )
        self._confirmation_plan_json = api_contract.dumps(plan_payload)
        self._confirmation_plan_signature = assignment_plan_signature(plan_payload)
        return context.window_manager.invoke_props_dialog(
            self,
            width=self._confirmation_draw_width,
            title=_CONFIRMATION_TITLE,
            confirm_text=_CONFIRMATION_TEXT,
        )

    def draw(self, context) -> None:
        plan = json.loads(self._confirmation_plan_json)
        lines = assignment_confirmation_lines(
            plan,
            previewed=self._confirmation_previewed,
        )
        draw_width = self._confirmation_draw_width
        region = getattr(context, "region", None)
        if getattr(region, "type", "") == "HUD":
            region_width = int(getattr(region, "width", 0) or 0)
            draw_width = (
                region_width
                if region_width > 0
                else _ADJUST_LAST_OPERATION_FALLBACK_WIDTH
            )
        for line in lines[:-1]:
            for wrapped in ui_text_lines(line, draw_width):
                self.layout.label(text=wrapped)
        self.layout.separator()
        for wrapped in ui_text_lines(lines[-1], draw_width):
            self.layout.label(text=wrapped)

    def execute(self, context: bpy.types.Context) -> set[str]:
        restore_edit_mode = context.object is not None and context.object.mode == "EDIT"
        if restore_edit_mode:
            # Object-mode mesh arrays are the authoritative base-mesh input.  Edit
            # Mode may expose a temporarily unsynchronised RNA view even when the
            # user changed only face selection during preview.
            bpy.ops.object.mode_set(mode="OBJECT")
        prepared = _validated_plan(self, context)
        if prepared is None:
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return {"CANCELLED"}
        _report, plan, plan_payload = prepared
        if (
            self._confirmation_plan_signature
            and assignment_plan_signature(plan_payload)
            != self._confirmation_plan_signature
        ):
            runtime.clear_review(context.window_manager)
            self._status(
                context,
                "PREFLIGHT_CHANGED",
                "The material plan changed while confirmation was open",
                plan=plan_payload,
            )
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return {"CANCELLED"}
        actionable = plan.actionable
        if not actionable:
            unresolved_groups = sum(
                item.action == "LEAVE_UNCHANGED_NO_ALPHA_SOURCE"
                for item in plan.dispositions
            )
            unchanged_groups = plan.unchanged_group_count
            if plan.blocked:
                message = "No safe material assignment is available"
            elif plan.already_derived:
                message = "Already separated - no additional changes"
            elif unresolved_groups:
                message = (
                    "No resolved alpha material needs separation; "
                    "unresolved materials were left unchanged"
                )
            else:
                message = "No alpha-affected faces need material separation"
            self._status(
                context,
                "ASSIGNMENT_BLOCKED" if plan.blocked else "ASSIGNMENT_NO_CHANGES",
                message,
                plan=plan_payload,
            )
            ui = context.window_manager.alpha_material_separator_ui
            ui.last_completion_json = api_contract.dumps(
                api_contract.status_payload(
                    "ASSIGNMENT_BLOCKED" if plan.blocked else "ASSIGNMENT_NO_CHANGES",
                    message,
                    changes={
                        "added_material_slots": 0,
                        "changed_faces": 0,
                        "created_materials": 0,
                        "reused_materials": 0,
                        "blocked_material_groups": len(plan.blocked),
                        "partial_material_groups": plan.partial_group_count,
                        "retained_faces_by_policy": sum(
                            item.retained_by_policy for item in plan.dispositions
                        ),
                        "skipped_objects": len(plan.skipped_objects),
                        "skipped_material_groups": plan.skipped_group_count,
                        "unchanged_material_groups": unchanged_groups,
                    },
                    plan=plan_payload,
                )
            )
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return {"CANCELLED" if plan.blocked else "FINISHED"}

        try:
            changes = execute_assignment_plan(plan)
        except Exception as error:
            self._status(context, "ASSIGNMENT_FAILED", str(error), plan=plan_payload)
            return {"CANCELLED"}
        finally:
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")

        runtime.clear(preserve_completion=True)
        state = context.window_manager.alpha_material_separator_api
        state.analysis_id = ""
        state.report_json = "{}"
        code = "ASSIGNMENT_COMPLETE_WITH_SKIPS" if plan.has_skips else "ASSIGNMENT_COMPLETE"
        self._status(
            context,
            code,
            "Reviewed material assignment completed",
            changes=changes,
            plan=plan_payload,
        )
        context.window_manager.alpha_material_separator_ui.last_completion_json = (
            state.last_status_json
        )
        runtime.tag_redraw()
        return {"FINISHED"}
