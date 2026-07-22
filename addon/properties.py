# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender RNA properties owned by the extension."""

from __future__ import annotations

import bpy
from bpy.props import StringProperty


class ALPHA_MATERIAL_SEPARATOR_PG_api_state(bpy.types.PropertyGroup):
    """Machine-readable capability and last-operation state."""

    api_version: StringProperty(name="API Version", default="")
    extension_version: StringProperty(name="Extension Version", default="")
    capabilities_json: StringProperty(name="Capabilities", default="{}")
    last_status_code: StringProperty(name="Status Code", default="NOT_QUERIED")
    last_status_json: StringProperty(name="Status", default="{}")
