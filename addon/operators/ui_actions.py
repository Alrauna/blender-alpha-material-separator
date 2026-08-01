# SPDX-License-Identifier: GPL-3.0-or-later
"""Internal actions used by the guided Blender interface."""

from __future__ import annotations

import bpy
from bpy.props import IntProperty, StringProperty

from .. import runtime


class ALPHA_MATERIAL_SEPARATOR_OT_cancel_analysis(bpy.types.Operator):
    bl_idname = "alpha_material_separator.cancel_analysis"
    bl_label = "Cancel Analysis"
    bl_description = "Stop before publishing a partial result or changing Blender data"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        runtime.request_cancel(context.window_manager)
        return {"FINISHED"}


class ALPHA_MATERIAL_SEPARATOR_OT_add_override(bpy.types.Operator):
    bl_idname = "alpha_material_separator.add_material_override"
    bl_label = "Add Manual Alpha Source"
    bl_description = "Add a manual alpha-source record for one material"
    bl_options = {"INTERNAL"}

    material_name: StringProperty(default="", options={"HIDDEN"})

    def execute(self, context):
        settings = context.window_manager.alpha_material_separator_settings
        ui = context.window_manager.alpha_material_separator_ui
        material = bpy.data.materials.get(self.material_name) if self.material_name else None
        if material is not None:
            for index, item in enumerate(settings.material_overrides):
                if item.material == material:
                    ui.override_index = index
                    ui.mode = "EXPERT"
                    return {"FINISHED"}
        item = settings.material_overrides.add()
        item.material = material
        ui.override_index = len(settings.material_overrides) - 1
        ui.mode = "EXPERT"
        runtime.mark_dirty("SETTINGS_CHANGED")
        return {"FINISHED"}


class ALPHA_MATERIAL_SEPARATOR_OT_remove_override(bpy.types.Operator):
    bl_idname = "alpha_material_separator.remove_material_override"
    bl_label = "Remove Manual Alpha Source"
    bl_description = "Remove this material-specific alpha-source record"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=-1, options={"HIDDEN"})

    def execute(self, context):
        settings = context.window_manager.alpha_material_separator_settings
        ui = context.window_manager.alpha_material_separator_ui
        index = self.index if self.index >= 0 else ui.override_index
        if 0 <= index < len(settings.material_overrides):
            settings.material_overrides.remove(index)
            ui.override_index = max(0, min(index, len(settings.material_overrides) - 1))
            runtime.mark_dirty("SETTINGS_CHANGED")
        return {"FINISHED"}
