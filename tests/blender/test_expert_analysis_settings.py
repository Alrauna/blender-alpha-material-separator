# SPDX-License-Identifier: GPL-3.0-or-later
"""Expert Analysis Settings copy and reset behavior."""

from __future__ import annotations

import bpy

from addon import runtime
from addon.properties import ANALYSIS_SETTING_NAMES

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


def run() -> None:
    _assert_names_cover_the_panel()
    _assert_descriptions_are_artist_readable()
    print("ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK")
