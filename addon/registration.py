# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit and reversible Blender registration."""

from __future__ import annotations

import bpy
from bpy.props import PointerProperty

from . import panel, properties, runtime
from .operators.analyze import ALPHA_MATERIAL_SEPARATOR_OT_analyze
from .operators.assign_materials import ALPHA_MATERIAL_SEPARATOR_OT_assign_materials
from .operators.clear_results import ALPHA_MATERIAL_SEPARATOR_OT_clear_results
from .operators.query_capabilities import ALPHA_MATERIAL_SEPARATOR_OT_query_capabilities
from .operators.select_faces import ALPHA_MATERIAL_SEPARATOR_OT_select_faces
from .operators.ui_actions import (
    ALPHA_MATERIAL_SEPARATOR_OT_add_override,
    ALPHA_MATERIAL_SEPARATOR_OT_cancel_analysis,
    ALPHA_MATERIAL_SEPARATOR_OT_remove_override,
    ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings,
)

_CLASSES = (
    properties.ALPHA_MATERIAL_SEPARATOR_PG_api_state,
    properties.ALPHA_MATERIAL_SEPARATOR_PG_material_override,
    properties.ALPHA_MATERIAL_SEPARATOR_PG_ui_state,
    properties.ALPHA_MATERIAL_SEPARATOR_PG_settings,
    ALPHA_MATERIAL_SEPARATOR_OT_query_capabilities,
    ALPHA_MATERIAL_SEPARATOR_OT_analyze,
    ALPHA_MATERIAL_SEPARATOR_OT_select_faces,
    ALPHA_MATERIAL_SEPARATOR_OT_cancel_analysis,
    ALPHA_MATERIAL_SEPARATOR_OT_add_override,
    ALPHA_MATERIAL_SEPARATOR_OT_remove_override,
    ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings,
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials,
    ALPHA_MATERIAL_SEPARATOR_OT_clear_results,
    panel.ALPHA_MATERIAL_SEPARATOR_UL_material_overrides,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_main,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_overrides,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_inspection,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_policies,
    panel.ALPHA_MATERIAL_SEPARATOR_PT_technical,
)


def register() -> None:
    """Register classes and WindowManager state in dependency order."""
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.alpha_material_separator_api = PointerProperty(
        type=properties.ALPHA_MATERIAL_SEPARATOR_PG_api_state
    )
    bpy.types.WindowManager.alpha_material_separator_settings = PointerProperty(
        type=properties.ALPHA_MATERIAL_SEPARATOR_PG_settings
    )
    bpy.types.WindowManager.alpha_material_separator_ui = PointerProperty(
        type=properties.ALPHA_MATERIAL_SEPARATOR_PG_ui_state
    )
    bpy.types.Material.alpha_material_separator_source = PointerProperty(
        name="Alpha Material Separator Source",
        type=bpy.types.Material,
    )
    runtime.register_handlers()


def unregister() -> None:
    """Remove all extension-owned state, properties, and classes."""
    runtime.unregister_handlers()
    runtime.clear()

    if hasattr(bpy.types.WindowManager, "alpha_material_separator_ui"):
        del bpy.types.WindowManager.alpha_material_separator_ui

    if hasattr(bpy.types.WindowManager, "alpha_material_separator_settings"):
        del bpy.types.WindowManager.alpha_material_separator_settings

    if hasattr(bpy.types.Material, "alpha_material_separator_source"):
        del bpy.types.Material.alpha_material_separator_source

    if hasattr(bpy.types.WindowManager, "alpha_material_separator_api"):
        del bpy.types.WindowManager.alpha_material_separator_api

    for cls in reversed(_CLASSES):
        if getattr(cls, "is_registered", False):
            bpy.utils.unregister_class(cls)
