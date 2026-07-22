# SPDX-License-Identifier: GPL-3.0-or-later
"""Checkpoint user interface."""

from __future__ import annotations

import bpy


class ALPHA_MATERIAL_SEPARATOR_PT_main(bpy.types.Panel):
    """Display development status without advertising unfinished operations."""

    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_main"
    bl_label = "Alpha Material Separator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Alpha Material"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Material support checkpoint", icon="INFO")
        layout.label(text="Analysis is not implemented yet")
        layout.operator(
            "alpha_material_separator.query_capabilities",
            text="Refresh Capabilities",
            icon="FILE_REFRESH",
        )

        state = context.window_manager.alpha_material_separator_api
        status = layout.box()
        status.label(text=f"API: {state.api_version or 'not queried'}")
        status.label(text=f"Status: {state.last_status_code}")
