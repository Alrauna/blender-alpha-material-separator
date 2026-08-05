# SPDX-License-Identifier: GPL-3.0-or-later
"""Undoable face-selection preview for a validated analysis report."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from .. import api_contract, runtime
from ..adapters.analysis import validate_report
from ..adapters.assignment import build_assignment_plan, preview_face_indices
from ..presentation import review_signature


class ALPHA_MATERIAL_SEPARATOR_OT_select_faces(bpy.types.Operator):
    """Select analyzed base-mesh polygons by classification."""

    bl_idname = "alpha_material_separator.select_faces"
    bl_label = "Preview Classified Faces"
    bl_description = "Select faces from the reviewed, still-valid analysis"
    bl_options = {"REGISTER", "UNDO"}

    api_major: IntProperty(name="API Major", default=1, min=1)
    expected_analysis_id: StringProperty(name="Expected Analysis ID", default="")
    ui_description: StringProperty(
        default="", options={"HIDDEN", "SKIP_SAVE"}
    )
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
    preview_assignment_plan: BoolProperty(
        name="Preview Assignment Plan",
        description="Select the exact faces the current assignment policies would move",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    mixed_policy: EnumProperty(
        name="Mixed Faces",
        items=(
            ("TO_ALPHA", "Move to Alpha", "Move mixed faces to alpha"),
            ("KEEP_SOURCE", "Keep Source", "Leave mixed faces on the source"),
            ("CANCEL_SOURCE_MATERIAL", "Skip Group", "Skip the material group"),
        ),
        default="TO_ALPHA",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    suppressed_policy: EnumProperty(
        name="Suppressed Evidence",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip Group", "Skip the material group"),
            ("TO_ALPHA", "Move to Alpha", "Move suppressed faces to alpha"),
            ("KEEP_SOURCE", "Keep Source", "Leave suppressed faces on the source"),
        ),
        default="KEEP_SOURCE",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    unsupported_policy: EnumProperty(
        name="Unsupported Faces",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip Group", "Skip a resolved group with uncertain faces"),
            ("KEEP_SOURCE", "Keep Source", "Leave face-local uncertainty on the source"),
            ("TO_ALPHA", "Move to Alpha", "Move face-local uncertainty to alpha"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    derived_conflict_policy: EnumProperty(
        name="Derived Conflict",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip Group", "Preserve conflicting data"),
            ("REUSE_EXISTING", "Reuse Existing", "Reuse the existing alpha material"),
            ("CREATE_NEW_VARIANT", "Create New", "Create a fresh alpha material"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    @classmethod
    def description(cls, _context, properties):
        return properties.ui_description or cls.bl_description

    def _fail(self, context, code: str, message: str) -> set[str]:
        runtime.clear_review(context.window_manager)
        state = context.window_manager.alpha_material_separator_api
        api_contract.publish_status(state, code, message)
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
        plan_targets = None
        plan_payload = None
        if self.preview_assignment_plan:
            plan = build_assignment_plan(
                report,
                mixed_policy=self.mixed_policy,
                suppressed_policy=self.suppressed_policy,
                unsupported_policy=self.unsupported_policy,
                conflict_policy=self.derived_conflict_policy,
            )
            plan_targets = preview_face_indices(plan)
            plan_payload = plan.public_payload()

        objects = [
            result.object
            for result in report.object_results.values()
            if not result.skipped_reason
            and (
                plan_targets is None
                or result.object.as_pointer() in plan_targets
            )
        ]
        if not objects:
            if restore_edit_mode and context.object is not None:
                bpy.ops.object.mode_set(mode="EDIT")
            return self._fail(context, "NO_PREVIEW_OBJECTS", "No safe analyzed object")
        target_pointers = {object_.as_pointer() for object_ in objects}
        for selected_object in tuple(context.selected_objects):
            if (
                selected_object.type == "MESH"
                and selected_object.as_pointer() not in target_pointers
            ):
                selected_object.select_set(False)
        selected_count = 0
        for result in report.object_results.values():
            if result.skipped_reason:
                continue
            mesh = result.object.data
            if (
                self.enter_edit_mode
                and result.object.as_pointer() in target_pointers
            ):
                for vertex in mesh.vertices:
                    vertex.select = False
                for edge in mesh.edges:
                    edge.select = False
            object_targets = (
                plan_targets.get(result.object.as_pointer(), frozenset())
                if plan_targets is not None
                else None
            )
            for polygon in mesh.polygons:
                face = result.faces.get(polygon.index)
                if object_targets is not None:
                    target = polygon.index in object_targets
                else:
                    target = (
                        face is not None
                        and face.result.classification.value in self.classes
                    )
                if self.selection_mode == "REPLACE":
                    polygon.select = target
                elif self.selection_mode == "ADD" and target:
                    polygon.select = True
                elif self.selection_mode == "SUBTRACT" and target:
                    polygon.select = False
                if target:
                    selected_count += 1
            mesh.update()
            if plan_targets is None or result.object.as_pointer() in plan_targets:
                result.object.select_set(True)
            else:
                result.object.select_set(False)

        context.view_layer.objects.active = objects[0]
        if self.enter_edit_mode:
            context.tool_settings.mesh_select_mode = (False, False, True)
            bpy.ops.object.mode_set(mode="EDIT")

        # Face selection itself can emit a generic Mesh depsgraph hint even
        # though selection is not part of the authoritative analysis signature.
        # Flush that hint before recording the reviewed-preview token.
        context.view_layer.update()
        pending = runtime.pending_scopes()
        if pending:
            if pending <= {"MESH", "OBJECT"}:
                runtime.record_validation(
                    "PREVIEW_SELECTION_ONLY",
                    True,
                    "SELECTION_ONLY",
                    component_hash_calls=0,
                    image_digest_rows=0,
                    rasterized_polygons=0,
                    coverage_hits=0,
                    coverage_misses=0,
                    elapsed_seconds=0.0,
                )
            else:
                return self._fail(
                    context,
                    "STALE_ANALYSIS",
                    "An analyzed material or image changed during preview; verify inputs again",
                )

        state = context.window_manager.alpha_material_separator_api
        api_contract.publish_status(
            state,
            "PREVIEW_COMPLETE",
            "Face-selection preview completed",
            analysis_id=report.analysis_id,
            classes=sorted(self.classes),
            preview_kind=(
                "ASSIGNMENT_PLAN" if self.preview_assignment_plan else "CLASSIFICATIONS"
            ),
            selected_face_count=selected_count,
        )
        exact_plan_preview = self.preview_assignment_plan and self.selection_mode == "REPLACE"
        if exact_plan_preview:
            signature = review_signature(
                report.analysis_id,
                self.mixed_policy,
                self.suppressed_policy,
                self.unsupported_policy,
                self.derived_conflict_policy,
                plan_payload,
            )
            runtime.set_review(
                context.window_manager, report.analysis_id, signature
            )
        else:
            runtime.clear_review(context.window_manager)
        runtime.tag_redraw()
        return {"FINISHED"}
