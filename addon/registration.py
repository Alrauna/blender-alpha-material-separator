# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit and reversible Blender registration."""

from __future__ import annotations

import bpy
from bpy.props import PointerProperty

from . import panel, properties, runtime
from .operators.clear_results import ALPHA_MATERIAL_SEPARATOR_OT_clear_results
from .operators.query_capabilities import ALPHA_MATERIAL_SEPARATOR_OT_query_capabilities

_CLASSES = (
    properties.ALPHA_MATERIAL_SEPARATOR_PG_api_state,
    ALPHA_MATERIAL_SEPARATOR_OT_query_capabilities,
    ALPHA_MATERIAL_SEPARATOR_OT_clear_results,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_main,
)


def register() -> None:
    """Register classes and WindowManager state in dependency order."""
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.alpha_material_separator_api = PointerProperty(
        type=properties.ALPHA_MATERIAL_SEPARATOR_PG_api_state
    )


def unregister() -> None:
    """Remove all extension-owned state, properties, and classes."""
    runtime.clear()

    if hasattr(bpy.types.WindowManager, "alpha_material_separator_api"):
        del bpy.types.WindowManager.alpha_material_separator_api

    for cls in reversed(_CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
