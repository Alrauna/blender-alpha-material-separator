# SPDX-License-Identifier: GPL-3.0-or-later
"""Synchronous and modal alpha analysis operator."""

from __future__ import annotations

import json

import bpy
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty

from .. import api_contract, runtime
from ..adapters.analysis import AnalysisConfig, AnalysisEngine
from ..core import AnalysisSettings


def _mesh_objects(context: bpy.types.Context) -> tuple[bpy.types.Object, ...]:
    return tuple(obj for obj in context.selected_objects if obj.type == "MESH")


class ALPHA_MATERIAL_SEPARATOR_OT_analyze(bpy.types.Operator):
    """Analyze selected base-mesh polygons without persistent data changes."""

    bl_idname = "alpha_material_separator.analyze"
    bl_label = "Analyze Alpha Materials"
    bl_description = "Classify selected mesh faces from UV-covered image alpha"
    bl_options = {"REGISTER"}

    api_major: IntProperty(name="API Major", default=1, min=1)
    image_name: StringProperty(name="Image Override", default="")
    uv_map_name: StringProperty(name="UV Map Override", default="")
    image_channel: EnumProperty(
        name="Image Channel",
        items=(
            ("ALPHA", "Alpha", "Use stored alpha"),
            ("RED", "Red", "Use red"),
            ("GREEN", "Green", "Use green"),
            ("BLUE", "Blue", "Use blue"),
            ("LUMINANCE", "Luminance", "Use RGB luminance"),
        ),
        default="ALPHA",
    )
    address_mode: EnumProperty(
        name="Address Mode",
        items=(
            ("AUTO", "Automatic", "Use the Image Texture setting"),
            ("REPEAT", "Repeat", "Repeat"),
            ("EXTEND", "Extend", "Extend"),
            ("CLIP", "Clip", "Transparent outside image"),
            ("MIRROR", "Mirror", "Mirrored repeat"),
        ),
        default="AUTO",
    )
    alpha_threshold: FloatProperty(
        name="Alpha Threshold", default=0.999, min=0.0, max=1.0, precision=4
    )
    min_affected_texels: IntProperty(
        name="Minimum Affected Texels", default=1, min=0
    )
    min_affected_fraction: FloatProperty(
        name="Minimum Affected Fraction", default=0.0, min=0.0, max=1.0
    )
    margin_texels: IntProperty(name="Texel Margin", default=0, min=0)
    max_scanlines: IntProperty(name="Maximum Scanlines", default=1_000_000, min=1)
    max_run_emissions: IntProperty(
        name="Maximum Run Emissions", default=2_000_000, min=1
    )

    _engine = None
    _timer = None

    def _status(self, context, code: str, message: str, **details) -> None:
        state = context.window_manager.alpha_material_separator_api
        payload = api_contract.status_payload(code, message, **details)
        state.last_status_code = code
        state.last_status_json = api_contract.dumps(payload)

    def _config(self) -> AnalysisConfig:
        return AnalysisConfig(
            image_name=self.image_name,
            uv_map_name=self.uv_map_name,
            image_channel=self.image_channel,
            address_mode=self.address_mode,
            settings=AnalysisSettings(
                alpha_threshold=self.alpha_threshold,
                min_affected_texels=self.min_affected_texels,
                min_affected_fraction=self.min_affected_fraction,
                margin_texels=self.margin_texels,
                max_scanlines=self.max_scanlines,
                max_run_emissions=self.max_run_emissions,
            ),
        )

    def _start(self, context, *, defer_images: bool) -> bool:
        if self.api_major != api_contract.API_VERSION[0]:
            self._status(
                context,
                "API_INCOMPATIBLE",
                "Requested API major is not supported",
                requested_api_major=self.api_major,
                supported_api_major=api_contract.API_VERSION[0],
            )
            return False
        objects = _mesh_objects(context)
        if not objects:
            self._status(context, "NO_ELIGIBLE_OBJECTS", "Select at least one mesh object")
            return False
        try:
            self._engine = AnalysisEngine(
                objects, self._config(), defer_images=defer_images
            )
        except Exception as error:
            self._status(context, "ANALYSIS_PREPARE_FAILED", str(error))
            return False
        context.window_manager.progress_begin(0, max(1, self._engine.total))
        return True

    def _publish(self, context) -> set[str]:
        report = self._engine.finish()
        runtime.set_report(report)
        payload = report.public_payload()
        state = context.window_manager.alpha_material_separator_api
        state.analysis_id = report.analysis_id
        state.report_json = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        self._status(
            context,
            "ANALYSIS_COMPLETE",
            "Analysis completed; review the report before preview or assignment",
            report=payload,
        )
        return {"FINISHED"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        if not self._start(context, defer_images=False):
            return {"CANCELLED"}
        try:
            while not self._engine.step(256):
                context.window_manager.progress_update(self._engine.completed)
            context.window_manager.progress_update(self._engine.total)
            return self._publish(context)
        finally:
            context.window_manager.progress_end()
            self._engine = None

    def invoke(self, context: bpy.types.Context, _event) -> set[str]:
        if not self._start(context, defer_images=True):
            return {"CANCELLED"}
        self._timer = context.window_manager.event_timer_add(0.02, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event) -> set[str]:
        if event.type == "ESC":
            self._engine.cancel()
            self._finish_modal(context)
            self._status(
                context,
                "ANALYSIS_CANCELLED",
                "Analysis cancelled; no partial result was retained",
            )
            return {"CANCELLED"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        try:
            complete = self._engine.step(64)
            context.window_manager.progress_update(self._engine.completed)
            if not complete:
                return {"RUNNING_MODAL"}
            result = self._publish(context)
        except Exception as error:
            self._status(context, "ANALYSIS_FAILED", str(error))
            result = {"CANCELLED"}
        self._finish_modal(context)
        return result

    def _finish_modal(self, context) -> None:
        context.window_manager.progress_end()
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        self._engine = None
