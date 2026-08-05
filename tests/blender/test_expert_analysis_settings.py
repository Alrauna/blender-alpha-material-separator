# SPDX-License-Identifier: GPL-3.0-or-later
"""Expert Analysis Settings copy and reset behavior."""

from __future__ import annotations

import bpy

from addon import runtime
from addon.properties import ANALYSIS_SETTING_NAMES
from tests.blender.test_analysis_preview import (
    _clear_scene,
    _image,
    _material,
    _quad,
)

EXPECTED_DESCRIPTIONS = {
    "alpha_threshold": (
        "How opaque a texture pixel must be to count as solid — pixels with "
        "alpha below this are treated as transparent"
    ),
    "min_affected_texels": (
        "How many transparent texture pixels a face must touch before it needs "
        "alpha; raise this to ignore faces that clip only a few stray pixels"
    ),
    "min_affected_fraction": (
        "What share of a face's texture area must be transparent before it "
        "needs alpha, from 0 to 1, where 0 turns this check off"
    ),
    "margin_texels": (
        "Also check this many texture pixels beyond each face's UV outline, "
        "which catches transparency that texture filtering and mipmaps pull in "
        "when rendering"
    ),
    "address_mode": (
        "How the texture behaves outside its 0–1 UV tile when a face's UVs run "
        "past the image edge"
    ),
    "max_scanlines": (
        "Safety cap on how many texture pixel rows one face may scan, so an "
        "extreme face is reported as unanalyzed instead of guessed at"
    ),
    "max_run_emissions": (
        "Safety cap on how many horizontal pixel spans one face may produce, "
        "so an extreme face is reported as unanalyzed instead of guessed at"
    ),
}


def _settings():
    return bpy.context.window_manager.alpha_material_separator_settings


def _assert_names_cover_the_panel() -> None:
    assert set(ANALYSIS_SETTING_NAMES) == set(EXPECTED_DESCRIPTIONS), (
        set(ANALYSIS_SETTING_NAMES) ^ set(EXPECTED_DESCRIPTIONS)
    )


def _assert_descriptions_are_artist_readable() -> None:
    properties = _settings().bl_rna.properties
    for name, expected in EXPECTED_DESCRIPTIONS.items():
        actual = properties[name].description
        assert actual == expected, f"{name}: {actual!r}"


def _defaults():
    properties = _settings().bl_rna.properties
    return {name: properties[name].default for name in ANALYSIS_SETTING_NAMES}


def _analyze_clean_report() -> None:
    result = bpy.ops.alpha_material_separator.analyze()
    assert result == {"FINISHED"}, result
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )


def _assert_reset_behavior() -> None:
    _clear_scene()
    image = _image("AMS_RESET_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_RESET_SOURCE", image)
    _quad("AMS_RESET_OBJECT", material)
    settings = _settings()
    defaults = _defaults()

    # A reset that changes nothing must not invalidate a valid report.
    _analyze_clean_report()
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )

    # A reset that restores changed values must mark the report stale.
    settings.alpha_threshold = 0.5
    settings.min_affected_texels = 7
    settings.min_affected_fraction = 0.25
    settings.margin_texels = 3
    settings.address_mode = "CLIP"
    settings.max_scanlines = 12
    settings.max_run_emissions = 34
    for name in ANALYSIS_SETTING_NAMES:
        assert getattr(settings, name) != defaults[name], name

    _analyze_clean_report()
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    for name in ANALYSIS_SETTING_NAMES:
        assert getattr(settings, name) == defaults[name], name
    assert runtime.validation_state() == runtime.VALIDATION_STALE, (
        runtime.validation_state()
    )
    assert runtime.dirty_reason() == "SETTINGS_CHANGED", runtime.dirty_reason()

    _clear_scene()


def run() -> None:
    _assert_names_cover_the_panel()
    _assert_descriptions_are_artist_readable()
    _assert_reset_behavior()
    print("ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK")
