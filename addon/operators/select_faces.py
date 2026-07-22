# SPDX-License-Identifier: GPL-3.0-or-later
"""Undoable face-selection preview for a validated analysis report."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from .. import api_contract, runtime
from ..adapters.analysis import validate_report


class ALPHA_MATERIAL_SEPARATOR_OT_select_faces(bpy.types.Operator):
    """Select analyzed base-mesh polygons by classification."""

    bl_idname = "alpha_material_separator.select_faces"
    bl_label = "Preview Classified Faces"
    bl_description = "Select faces from the reviewed, still-valid analysis"
    bl_options = {"REGISTER", "UNDO"}

    api_major: IntProperty(name="API Major", default=1, min=1)
    expected_analysis_id: StringProperty(name="Expected Analysis ID", default="")
    classes: EnumProperty(
        name="Classes",
        items=(
            ("OPAQUE", "Opaque", "No alpha evidence", 1),
            ("ALPHA_AFFECTED", "Alpha-affected", "Every covered texel affected", 2),
            ("MIXED", "Mixed", "Opaque and affected texels coexist", 4),
            ("SUPPRESSED", "Suppressed", "Evidence below significance", 8),
            ("UNSUPPORTED", "Unsupported", "No trustworthy result", 16),
        ),
        options={"ENUM_FLAG"},
        default={"ALPHA_AFFECTED", "MIXED"},
    )
    selection_mode: EnumProperty(
        name="Selection Mode",
        items=(
            ("REPLACE", "Replace", "Replace face selection"),
            ("ADD", "Add", "Add to face selection"),
            ("SUBTRACT", "Subtract", "Remove from face selection"),
        ),
        default="REPLACE",
    )
    enter_edit_mode: BoolProperty(name="Enter Edit Mode", default=True)

    def _fail(self, context, code: str, message: str) -> set[str]:
        state = context.window_manager.alpha_material_separator_api
        state.last_status_code = code
        state.last_status_json = api_contract.dumps(api_contract.status_payload(code, message))
        self.report({"WARNING"}, message)
        return {"CANCELLED"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        if self.api_major != api_contract.API_VERSION[0]:
            return self._fail(context, "API_INCOMPATIBLE", "Unsupported API major")
        report = runtime.report(self.expected_analysis_id)
        if report is None:
            return self._fail(
                context, "ANALYSIS_ID_MISMATCH", "The reviewed analysis is unavailable"
            )
        restore_edit_mode = context.object is not None and context.object.mode == "EDIT"
        if restore_edit_mode:
            bpy.ops.object.mode_set(mode="OBJECT")
        if runtime.dirty_reason() == "SETTINGS_CHANGED":
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return self._fail(
                context,
                "STALE_ANALYSIS",
                "Analysis settings changed; run analysis again",
            )
        valid, reason = validate_report(report)
        if not valid:
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return self._fail(
                context,
                "STALE_ANALYSIS",
                f"Analysis inputs changed ({reason}); run analysis again",
            )
        runtime.clear_dirty()

        objects = [
            result.object
            for result in report.object_results.values()
            if not result.skipped_reason
        ]
        if not objects:
            return self._fail(context, "NO_PREVIEW_OBJECTS", "No safe analyzed object")
        selected_count = 0
        for result in report.object_results.values():
            if result.skipped_reason:
                continue
            mesh = result.object.data
            for polygon in mesh.polygons:
                face = result.faces.get(polygon.index)
                target = face is not None and face.result.classification.value in self.classes
                if self.selection_mode == "REPLACE":
                    polygon.select = target
                elif self.selection_mode == "ADD" and target:
                    polygon.select = True
                elif self.selection_mode == "SUBTRACT" and target:
                    polygon.select = False
                if target:
                    selected_count += 1
            mesh.update()
            result.object.select_set(True)

        context.view_layer.objects.active = objects[0]
        if self.enter_edit_mode:
            context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.object.mode_set(mode="EDIT")

        state = context.window_manager.alpha_material_separator_api
        status = api_contract.status_payload(
            "PREVIEW_COMPLETE",
            "Face-selection preview completed",
            analysis_id=report.analysis_id,
            classes=sorted(self.classes),
            selected_face_count=selected_count,
        )
        state.last_status_code = status["code"]
        state.last_status_json = api_contract.dumps(status)
        return {"FINISHED"}
