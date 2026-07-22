# SPDX-License-Identifier: GPL-3.0-or-later
"""Clear transient checkpoint state."""

from __future__ import annotations

import bpy
from bpy.props import IntProperty

from .. import api_contract, runtime


class ALPHA_MATERIAL_SEPARATOR_OT_clear_results(bpy.types.Operator):
    """Clear extension reports and caches without touching Blender data."""

    bl_idname = "alpha_material_separator.clear_results"
    bl_label = "Clear Alpha Material Separator Results"
    bl_description = "Clear transient Alpha Material Separator results"
    bl_options = {"INTERNAL"}

    api_major: IntProperty(name="API Major", default=1, min=1)

    def execute(self, context: bpy.types.Context) -> set[str]:
        state = context.window_manager.alpha_material_separator_api
        if self.api_major != api_contract.API_VERSION[0]:
            status = api_contract.status_payload(
                "API_INCOMPATIBLE",
                "Requested API major is not supported",
                requested_api_major=self.api_major,
                supported_api_major=api_contract.API_VERSION[0],
            )
            state.last_status_code = status["code"]
            state.last_status_json = api_contract.dumps(status)
            return {"CANCELLED"}

        runtime.clear()
        state.analysis_id = ""
        state.report_json = "{}"
        state.last_status_code = "CLEARED"
        state.last_status_json = api_contract.dumps(
            api_contract.status_payload("CLEARED", "Transient results cleared")
        )
        return {"FINISHED"}
