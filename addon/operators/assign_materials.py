# SPDX-License-Identifier: GPL-3.0-or-later
"""Atomic undoable material-slot assignment from a reviewed analysis."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

from .. import api_contract, runtime
from ..adapters.analysis import validate_report
from ..adapters.assignment import build_assignment_plan, execute_assignment_plan


class ALPHA_MATERIAL_SEPARATOR_OT_assign_materials(bpy.types.Operator):
    """Assign reviewed face groups to safe local derived materials."""

    bl_idname = "alpha_material_separator.assign_materials"
    bl_label = "Assign Alpha Materials"
    bl_description = "Create or reuse local alpha variants and assign reviewed faces"
    bl_options = {"REGISTER", "UNDO"}

    api_major: IntProperty(name="API Major", default=1, min=1)
    expected_analysis_id: StringProperty(name="Expected Analysis ID", default="")
    mixed_policy: EnumProperty(
        name="Mixed Faces",
        items=(
            ("TO_ALPHA", "Move to Alpha", "Move mixed faces to the alpha variant"),
            ("KEEP_SOURCE", "Keep Source", "Leave mixed faces on the source"),
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Block this material group"),
        ),
        default="TO_ALPHA",
    )
    suppressed_policy: EnumProperty(
        name="Suppressed Evidence",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Conservative default"),
            ("TO_ALPHA", "Move to Alpha", "Move after informed review"),
            ("KEEP_SOURCE", "Keep Source", "Leave after informed review"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
    unsupported_policy: EnumProperty(
        name="Unsupported Faces",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Conservative default"),
            ("KEEP_SOURCE", "Keep Source", "Leave unsupported faces unchanged"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
    derived_conflict_policy: EnumProperty(
        name="Derived Conflict",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Preserve conflicting data"),
            ("REUSE_EXISTING", "Reuse Existing", "Explicitly retain the existing variant"),
            ("CREATE_NEW_VARIANT", "Create New", "Preserve old variant and create another"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )

    def _status(self, context, code: str, message: str, **details) -> None:
        state = context.window_manager.alpha_material_separator_api
        payload = api_contract.status_payload(code, message, **details)
        state.last_status_code = code
        state.last_status_json = api_contract.dumps(payload)

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
        runtime.clear_dirty()

        plan = build_assignment_plan(
            report,
            mixed_policy=self.mixed_policy,
            suppressed_policy=self.suppressed_policy,
            unsupported_policy=self.unsupported_policy,
            conflict_policy=self.derived_conflict_policy,
        )
        plan_payload = plan.public_payload()
        actionable = bool(plan.mutations) or any(
            decision.action in {"CREATE", "REUSE"}
            for decision in plan.decisions.values()
        )
        if not actionable:
            self._status(
                context,
                "ASSIGNMENT_BLOCKED" if plan.blocked else "ASSIGNMENT_NO_CHANGES",
                "No safe material assignment is available",
                plan=plan_payload,
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

        runtime.clear()
        state = context.window_manager.alpha_material_separator_api
        state.analysis_id = ""
        state.report_json = "{}"
        code = "ASSIGNMENT_COMPLETE_WITH_SKIPS" if plan.blocked else "ASSIGNMENT_COMPLETE"
        self._status(
            context,
            code,
            "Reviewed material assignment completed",
            changes=changes,
            plan=plan_payload,
        )
        return {"FINISHED"}
