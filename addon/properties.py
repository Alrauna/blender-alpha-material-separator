# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender RNA properties owned by the extension."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from .overrides import ADDRESS_MODE_ITEMS, CHANNEL_ITEMS


def _settings_changed(_self, context) -> None:
    from . import runtime

    runtime.mark_dirty("SETTINGS_CHANGED")
    runtime.clear_review(context.window_manager if context else None)


def _policy_changed(_self, context) -> None:
    from . import runtime

    runtime.clear_review(context.window_manager if context else None)


class ALPHA_MATERIAL_SEPARATOR_PG_api_state(bpy.types.PropertyGroup):
    """Machine-readable capability and last-operation state."""

    api_version: StringProperty(name="API Version", default="")
    extension_version: StringProperty(name="Extension Version", default="")
    capabilities_json: StringProperty(name="Capabilities", default="{}")
    last_status_code: StringProperty(name="Status Code", default="NOT_QUERIED")
    last_status_json: StringProperty(name="Status", default="{}")
    analysis_id: StringProperty(name="Analysis ID", default="")
    report_json: StringProperty(name="Analysis Report", default="{}")
    validation_state: StringProperty(
        name="Validation State", default="CLEAN", options={"SKIP_SAVE"}
    )
    pending_scopes_json: StringProperty(
        name="Pending Validation Scopes", default="[]", options={"SKIP_SAVE"}
    )


class ALPHA_MATERIAL_SEPARATOR_PG_material_override(bpy.types.PropertyGroup):
    """One transient manual alpha source targeted at a Blender material."""

    material: PointerProperty(
        name="Target Material",
        description="Only this material uses the manual settings below",
        type=bpy.types.Material,
        update=_settings_changed,
    )
    image: PointerProperty(
        name="Alpha Image",
        description="Optional image containing the alpha or mask channel",
        type=bpy.types.Image,
        update=_settings_changed,
    )
    image_channel: EnumProperty(
        name="Image Channel",
        description="Channel to classify; available only with an explicit image",
        items=CHANNEL_ITEMS,
        default="ALPHA",
        update=_settings_changed,
    )
    uv_map_name: StringProperty(
        name="UV Map",
        description="Optional exact UV map name; blank uses the resolved active render UV",
        default="",
        update=_settings_changed,
    )
    address_mode: EnumProperty(
        name="Addressing",
        description="How UVs outside the image tile are interpreted",
        items=ADDRESS_MODE_ITEMS,
        default="AUTO",
        update=_settings_changed,
    )


class ALPHA_MATERIAL_SEPARATOR_PG_ui_state(bpy.types.PropertyGroup):
    """Private transient state for the guided panel."""

    mode: EnumProperty(
        name="Interface",
        description="Simple shows the guided workflow; Expert adds manual controls",
        items=(
            ("SIMPLE", "Simple", "Guided Analyze, Review, and Apply workflow"),
            ("EXPERT", "Expert", "Show advanced settings and diagnostics"),
        ),
        default="SIMPLE",
    )
    is_analyzing: BoolProperty(default=False, options={"SKIP_SAVE"})
    analysis_progress: FloatProperty(default=0.0, min=0.0, max=1.0, options={"SKIP_SAVE"})
    analysis_stage: StringProperty(default="", options={"SKIP_SAVE"})
    cancel_requested: BoolProperty(default=False, options={"SKIP_SAVE"})
    reviewed_analysis_id: StringProperty(default="", options={"SKIP_SAVE"})
    reviewed_policy_signature: StringProperty(default="", options={"SKIP_SAVE"})
    show_material_details: BoolProperty(default=False, options={"SKIP_SAVE"})
    last_completion_json: StringProperty(default="{}", options={"SKIP_SAVE"})
    override_index: IntProperty(default=0, min=0, options={"SKIP_SAVE"})


class ALPHA_MATERIAL_SEPARATOR_PG_settings(bpy.types.PropertyGroup):
    alpha_threshold: FloatProperty(
        name="Alpha Threshold",
        description="Pixels below this value count as alpha-affected",
        default=0.999,
        min=0.0,
        max=1.0,
        precision=4,
        update=_settings_changed,
    )
    min_affected_texels: IntProperty(
        name="Minimum Affected Pixels",
        description="Minimum affected covered pixels needed for a significant result",
        default=1,
        min=0,
        update=_settings_changed,
    )
    min_affected_fraction: FloatProperty(
        name="Minimum Affected Fraction",
        description="Minimum affected share needed for a significant result",
        default=0.0,
        min=0.0,
        max=1.0,
        precision=4,
        update=_settings_changed,
    )
    margin_texels: IntProperty(
        name="Pixel Margin",
        description="Expand UV coverage by this many image pixels after face coverage is combined",
        default=0,
        min=0,
        update=_settings_changed,
    )
    max_scanlines: IntProperty(
        name="Maximum Scanlines",
        description="Deterministic safety limit per polygon",
        default=1_000_000,
        min=1,
        update=_settings_changed,
    )
    max_run_emissions: IntProperty(
        name="Maximum Pixel Runs",
        description="Deterministic raster-run safety limit per polygon",
        default=2_000_000,
        min=1,
        update=_settings_changed,
    )

    # Legacy selection-wide properties remain for API compatibility but are no
    # longer shown in the end-user UI.
    image_override: PointerProperty(
        name="Legacy Analysis Image", type=bpy.types.Image, update=_settings_changed
    )
    uv_map_name: StringProperty(
        name="Legacy UV Map Override", default="", update=_settings_changed
    )
    image_channel: EnumProperty(
        name="Legacy Image Channel",
        items=CHANNEL_ITEMS,
        default="ALPHA",
        update=_settings_changed,
    )
    address_mode: EnumProperty(
        name="Default Addressing",
        description="Addressing used by automatic sources unless a material override replaces it",
        items=ADDRESS_MODE_ITEMS,
        default="AUTO",
        update=_settings_changed,
    )
    material_overrides: CollectionProperty(
        name="Manual Alpha Sources",
        type=ALPHA_MATERIAL_SEPARATOR_PG_material_override,
    )

    preview_classes: EnumProperty(
        name="Inspect Classes",
        description="Expert-only selection of result classes to inspect",
        items=(
            ("OPAQUE", "Stay opaque", "No below-threshold covered pixels", 1),
            ("ALPHA_AFFECTED", "Move to alpha", "Every covered pixel is affected", 2),
            ("MIXED", "Mixed", "Affected and opaque pixels coexist", 4),
            ("SUPPRESSED", "Below significance", "Alpha evidence is below the minimum", 8),
            ("UNSUPPORTED", "Could not analyze", "No trustworthy result", 16),
        ),
        options={"ENUM_FLAG"},
        default={"ALPHA_AFFECTED", "MIXED"},
    )
    enter_edit_mode: BoolProperty(
        name="Enter Edit Mode",
        description="Enter multi-object Edit Mode so the preview selection is visible",
        default=True,
    )
    mixed_policy: EnumProperty(
        name="Mixed Faces",
        items=(
            ("TO_ALPHA", "Move to alpha", "Conservative transparent result"),
            ("KEEP_SOURCE", "Keep on source", "Leave mixed faces on the opaque candidate"),
            ("CANCEL_SOURCE_MATERIAL", "Skip entire material group", "Do not change this material group"),
        ),
        default="TO_ALPHA",
        update=_policy_changed,
    )
    suppressed_policy: EnumProperty(
        name="Below-Significance Evidence",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip entire material group", "Conservative default"),
            ("TO_ALPHA", "Move to alpha", "Move after informed review"),
            ("KEEP_SOURCE", "Keep on source", "Leave after informed review"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
        update=_policy_changed,
    )
    unsupported_policy: EnumProperty(
        name="Could Not Analyze",
        items=(
            (
                "TO_ALPHA",
                "Move uncertain faces to alpha",
                "Conservatively preserve transparency for face-local UV or budget uncertainty",
            ),
            ("CANCEL_SOURCE_MATERIAL", "Skip entire material group", "Do not change a resolved material that contains uncertain faces"),
            ("KEEP_SOURCE", "Keep on source", "Leave unsupported faces unchanged"),
        ),
        default="TO_ALPHA",
        update=_policy_changed,
    )
    derived_conflict_policy: EnumProperty(
        name="Alpha-Material Conflicts",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip entire material group", "Preserve conflicting data"),
            ("REUSE_EXISTING", "Reuse existing", "Explicitly retain the existing variant"),
            ("CREATE_NEW_VARIANT", "Create a new variant", "Preserve the old variant"),
        ),
        default="CANCEL_SOURCE_MATERIAL",
        update=_policy_changed,
    )
