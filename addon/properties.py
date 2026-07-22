# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender RNA properties owned by the extension."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


def _settings_changed(_self, _context) -> None:
    from . import runtime

    runtime.mark_dirty("SETTINGS_CHANGED")


class ALPHA_MATERIAL_SEPARATOR_PG_api_state(bpy.types.PropertyGroup):
    """Machine-readable capability and last-operation state."""

    api_version: StringProperty(name="API Version", default="")
    extension_version: StringProperty(name="Extension Version", default="")
    capabilities_json: StringProperty(name="Capabilities", default="{}")
    last_status_code: StringProperty(name="Status Code", default="NOT_QUERIED")
    last_status_json: StringProperty(name="Status", default="{}")
    analysis_id: StringProperty(name="Analysis ID", default="")
    report_json: StringProperty(name="Analysis Report", default="{}")


class ALPHA_MATERIAL_SEPARATOR_PG_settings(bpy.types.PropertyGroup):
    alpha_threshold: FloatProperty(
        name="Alpha Threshold",
        default=0.999,
        min=0.0,
        max=1.0,
        precision=4,
        update=_settings_changed,
    )
    min_affected_texels: IntProperty(
        name="Minimum Affected Texels", default=1, min=0, update=_settings_changed
    )
    min_affected_fraction: FloatProperty(
        name="Minimum Affected Fraction",
        default=0.0,
        min=0.0,
        max=1.0,
        precision=4,
        update=_settings_changed,
    )
    margin_texels: IntProperty(
        name="Texel Margin", default=0, min=0, update=_settings_changed
    )
    max_scanlines: IntProperty(
        name="Maximum Scanlines", default=1_000_000, min=1, update=_settings_changed
    )
    max_run_emissions: IntProperty(
        name="Maximum Run Emissions",
        default=2_000_000,
        min=1,
        update=_settings_changed,
    )
    image_override: PointerProperty(
        name="Analysis Image", type=bpy.types.Image, update=_settings_changed
    )
    uv_map_name: StringProperty(
        name="UV Map Override", default="", update=_settings_changed
    )
    image_channel: EnumProperty(
        name="Image Channel",
        items=(
            ("ALPHA", "Alpha", "Use stored image alpha"),
            ("RED", "Red", "Use red as the analysis mask"),
            ("GREEN", "Green", "Use green as the analysis mask"),
            ("BLUE", "Blue", "Use blue as the analysis mask"),
            ("LUMINANCE", "Luminance", "Use linear RGB luminance as the mask"),
        ),
        default="ALPHA",
        update=_settings_changed,
    )
    address_mode: EnumProperty(
        name="Address Mode",
        items=(
            ("AUTO", "Automatic", "Use the resolved Image Texture setting"),
            ("REPEAT", "Repeat", "Repeat the image"),
            ("EXTEND", "Extend", "Extend edge texels"),
            ("CLIP", "Clip", "Treat outside-image cells as transparent"),
            ("MIRROR", "Mirror", "Repeat with mirrored tiles"),
        ),
        default="AUTO",
        update=_settings_changed,
    )
    preview_classes: EnumProperty(
        name="Preview Classes",
        items=(
            ("OPAQUE", "Opaque", "No below-threshold texels", 1),
            ("ALPHA_AFFECTED", "Alpha-affected", "All covered texels are affected", 2),
            ("MIXED", "Mixed", "Affected and opaque texels coexist", 4),
            ("SUPPRESSED", "Suppressed", "Evidence is below significance gates", 8),
            ("UNSUPPORTED", "Unsupported", "No trustworthy result", 16),
        ),
        options={"ENUM_FLAG"},
        default={"ALPHA_AFFECTED", "MIXED"},
    )
    enter_edit_mode: BoolProperty(name="Enter Edit Mode", default=True)
    mixed_policy: EnumProperty(
        name="Mixed Faces",
        items=(
            ("TO_ALPHA", "Move to Alpha", "Conservative transparent result"),
            ("KEEP_SOURCE", "Keep Source", "Leave mixed faces opaque"),
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Skip this material group"),
        ),
        default="TO_ALPHA",
    )
    suppressed_policy: EnumProperty(
        name="Suppressed Evidence",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Conservative default"),
            ("TO_ALPHA", "Move to Alpha", "Move after review"),
            ("KEEP_SOURCE", "Keep Source", "Leave after review"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
    unsupported_policy: EnumProperty(
        name="Unsupported Faces",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Conservative default"),
            ("KEEP_SOURCE", "Keep Source", "Leave unsupported faces unchanged"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
    derived_conflict_policy: EnumProperty(
        name="Derived Conflicts",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Block Source", "Preserve conflicting data"),
            ("REUSE_EXISTING", "Reuse Existing", "Explicitly reuse the old variant"),
            ("CREATE_NEW_VARIANT", "Create New", "Preserve the old variant"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
    )
