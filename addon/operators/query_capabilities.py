# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only public capability query."""

from __future__ import annotations

import bpy
from bpy.props import IntProperty

from .. import api_contract


class ALPHA_MATERIAL_SEPARATOR_OT_query_capabilities(bpy.types.Operator):
    """Publish the versioned integration capabilities."""

    bl_idname = "alpha_material_separator.query_capabilities"
    bl_label = "Query Alpha Material Separator Capabilities"
    bl_description = "Publish the extension API version and available capabilities"
    bl_options = {"INTERNAL"}

    requested_api_major: IntProperty(name="Requested API Major", default=1, min=1)

    def execute(self, context: bpy.types.Context) -> set[str]:
        state = context.window_manager.alpha_material_separator_api
        capabilities = api_contract.capability_payload()
        state.api_version = capabilities["api_version"]
        state.extension_version = capabilities["extension_version"]
        state.capabilities_json = api_contract.dumps(capabilities)

        if self.requested_api_major != api_contract.API_VERSION[0]:
            api_contract.publish_status(
                state,
                "API_INCOMPATIBLE",
                "Requested API major is not supported",
                requested_api_major=self.requested_api_major,
                supported_api_major=api_contract.API_VERSION[0],
            )
        else:
            api_contract.publish_status(
                state,
                "OK",
                "Capability query completed",
            )

        return {"FINISHED"}
