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
    assignment_plan_signature,
    guidance_for,
    requires_confirmation,
    review_signature,
)


class ALPHA_MATERIAL_SEPARATOR_OT_assign_materials(bpy.types.Operator):
    """Assign reviewed face groups to safe local derived materials."""

    bl_idname = "alpha_material_separator.assign_materials"
    bl_label = "Assign Alpha Materials"
    bl_description = "Create or reuse local alpha variants and assign reviewed faces"
    bl_options = {"REGISTER", "UNDO"}

    api_major: IntProperty(name="API Major", default=1, min=1)
    expected_analysis_id: StringProperty(name="Expected Analysis ID", default="")
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

    _confirmation_report_json = "{}"
    _confirmation_plan_json = "{}"
    _confirmation_plan_signature = ""

    def _status(self, context, code: str, message: str, **details) -> None:
        state = context.window_manager.alpha_material_separator_api
        payload = api_contract.status_payload(code, message, **details)
        state.last_status_code = code
        state.last_status_json = api_contract.dumps(payload)

    def invoke(self, context: bpy.types.Context, _event) -> set[str]:
        """Show a warning summary only when the reviewed plan needs attention."""
        self._confirmation_plan_signature = ""
        report = runtime.report(self.expected_analysis_id)
        if report is None or runtime.dirty_reason():
            return self.execute(context)
        restore_edit_mode = (
            context.object is not None and context.object.mode == "EDIT"
        )
        if restore_edit_mode:
            bpy.ops.object.mode_set(mode="OBJECT")
        valid, reason = validate_report(report)
        if restore_edit_mode and context.object is not None:
            bpy.ops.object.mode_set(mode="EDIT")
        if not valid:
            self._status(
                context,
                "STALE_ANALYSIS",
                "Analysis inputs changed; run analysis again",
                reason=reason,
            )
            return {"CANCELLED"}
        plan = build_assignment_plan(
            report,
            mixed_policy=self.mixed_policy,
            suppressed_policy=self.suppressed_policy,
            unsupported_policy=self.unsupported_policy,
            conflict_policy=self.derived_conflict_policy,
        )
        plan_payload = plan.public_payload()
        current_review_signature = review_signature(
            report.analysis_id,
            self.mixed_policy,
            self.suppressed_policy,
            self.unsupported_policy,
            self.derived_conflict_policy,
            plan_payload,
        )
        if (
            self.expected_review_signature
            and current_review_signature != self.expected_review_signature
        ):
            runtime.clear_review(context.window_manager)
            self._status(
                context,
                "REVIEW_CHANGED",
                "The material plan changed after preview; preview the faces again",
                plan=plan_payload,
            )
            return {"CANCELLED"}
        actionable = plan.actionable
        if not actionable:
            return self.execute(context)
        report_payload = report.public_payload()
        if not requires_confirmation(report_payload, plan_payload):
            return self.execute(context)
        self._confirmation_report_json = api_contract.dumps(report_payload)
        self._confirmation_plan_json = api_contract.dumps(plan_payload)
        self._confirmation_plan_signature = assignment_plan_signature(plan_payload)
        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, _context) -> None:
        layout = self.layout
        report = json.loads(self._confirmation_report_json)
        plan = json.loads(self._confirmation_plan_json)
        counts = report.get("counts", {})
        layout.label(text="Review warnings before material assignment", icon="ERROR")
        layout.label(text=f"Faces to move: {plan.get('faces_to_reassign', 0)}")
        layout.label(text=f"Additional material slots: {plan.get('planned_additional_slots', 0)}")
        if counts.get("MIXED", 0):
            layout.label(text=f"Mixed faces: {counts['MIXED']} (cannot be split without topology changes)")
        if counts.get("SUPPRESSED", 0):
            layout.label(text=f"Below-significance faces: {counts['SUPPRESSED']}")
        if counts.get("UNSUPPORTED", 0):
            layout.label(text=f"Faces that could not be analyzed: {counts['UNSUPPORTED']}")
        uncertain_to_alpha = plan.get("face_local_unsupported_to_alpha", 0)
        if uncertain_to_alpha:
            layout.label(
                text=f"Uncertain faces moving conservatively to alpha: {uncertain_to_alpha}",
                icon="INFO",
            )
        skipped = sum(report.get("skip_counts", {}).values())
        blocked = len(plan.get("blocked", []))
        unchanged = plan.get("material_source_groups_left_unchanged", 0)
        if skipped or blocked or unchanged:
            layout.label(
                text=(
                    f"Skipped objects: {skipped}; blocked material groups: {blocked}; "
                    f"unresolved groups left unchanged: {unchanged}"
                )
            )
        for object_result in report.get("objects", ()):
            if object_result.get("skip_reason"):
                title, _remedy = guidance_for(object_result["skip_reason"])
                layout.label(
                    text=(
                        f"Skip object {object_result.get('name', 'unknown')}: "
                        f"{title}"
                    ),
                    icon="ERROR",
                )
        for blocked_group in plan.get("blocked", ()):
            title, _remedy = guidance_for(blocked_group.get("reason"))
            layout.label(
                text=(
                    f"Skip material {blocked_group.get('material', 'unknown')}: "
                    f"{title}"
                ),
                icon="ERROR",
            )
        for disposition in plan.get("dispositions", ()):
            if disposition.get("action") != "LEAVE_UNCHANGED_NO_ALPHA_SOURCE":
                continue
            layout.label(
                text=(
                    f"Leave {disposition.get('material', 'unknown')} unchanged: "
                    "no alpha source was selected"
                ),
                icon="INFO",
            )
        destinations = plan.get("destinations", {})
        for source, derived in sorted(destinations.items()):
            layout.label(text=f"{source} -> {derived}", icon="MATERIAL")
        for disposition in plan.get("dispositions", ()):
            face_count = int(disposition.get("faces_to_alpha", 0))
            if not face_count:
                continue
            layout.label(
                text=(
                    f"{disposition.get('object', 'Object')} / "
                    f"{disposition.get('material', 'Material')}: "
                    f"{face_count} faces"
                )
            )
        layout.separator()
        layout.label(text="A local alpha material may be created or reused.")
        layout.label(text="Reviewed slots and face material indices may change.")
        layout.label(text="Source graphs and mesh topology stay unchanged.")
        layout.label(text="Press Ctrl+Z to undo.")

    def execute(self, context: bpy.types.Context) -> set[str]:
        if self.api_major != api_contract.API_VERSION[0]:
            self._status(context, "API_INCOMPATIBLE", "Unsupported API major")
            return {"CANCELLED"}
        report = runtime.report(self.expected_analysis_id)
        if report is None:
            self._status(
                context, "ANALYSIS_ID_MISMATCH", "The reviewed analysis is unavailable"
            )
            return {"CANCELLED"}
        restore_edit_mode = context.object is not None and context.object.mode == "EDIT"
        if restore_edit_mode:
            # Object-mode mesh arrays are the authoritative base-mesh input.  Edit
            # Mode may expose a temporarily unsynchronised RNA view even when the
            # user changed only face selection during preview.
            bpy.ops.object.mode_set(mode="OBJECT")
        if runtime.dirty_reason() == "SETTINGS_CHANGED":
            self._status(context, "STALE_ANALYSIS", "Analysis settings changed")
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return {"CANCELLED"}
        valid, reason = validate_report(report)
        if not valid:
            self._status(
                context,
                "STALE_ANALYSIS",
                "Analysis inputs changed; run analysis again",
                reason=reason,
            )
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return {"CANCELLED"}
        plan = build_assignment_plan(
            report,
            mixed_policy=self.mixed_policy,
            suppressed_policy=self.suppressed_policy,
            unsupported_policy=self.unsupported_policy,
            conflict_policy=self.derived_conflict_policy,
        )
        plan_payload = plan.public_payload()
        current_review_signature = review_signature(
            report.analysis_id,
            self.mixed_policy,
            self.suppressed_policy,
            self.unsupported_policy,
            self.derived_conflict_policy,
            plan_payload,
        )
        if (
            self.expected_review_signature
            and current_review_signature != self.expected_review_signature
        ):
            runtime.clear_review(context.window_manager)
            self._status(
                context,
                "REVIEW_CHANGED",
                "The material plan changed after preview; preview the faces again",
                plan=plan_payload,
            )
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return {"CANCELLED"}
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
