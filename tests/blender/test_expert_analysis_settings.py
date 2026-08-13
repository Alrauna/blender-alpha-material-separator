# SPDX-License-Identifier: GPL-3.0-or-later
"""Expert Analysis Settings copy and reset behavior."""

from __future__ import annotations

from types import SimpleNamespace

import bpy

from addon import runtime
from addon.adapters import gpu_raster
from addon.panel import ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings
from addon.properties import ANALYSIS_SETTING_NAMES
from tests.blender.test_analysis_preview import (
    _clear_scene,
    _image,
    _material,
    _quad,
)
from tests.blender.test_ux_overrides import _RecordingLayout

GPU_TOGGLE = "disable_gpu_acceleration"
GPU_TOGGLE_DESCRIPTION = "Manual fallback to full CPU analysis"
GPU_MISSING_INSTRUCTIONS = (
    "This GPU does not support the necessary instructions for GPU acceleration "
    "with this extension"
)
GPU_UNKNOWN_FAILURE = (
    "This GPU does not support GPU acceleration with this extension for an "
    "unknown reason"
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


def _assert_minimum_affected_pixels_is_reachable() -> None:
    """0 and 1 were indistinguishable, so 0 is no longer offered.

    A face with no affected texels returns OPAQUE before the gate runs, so the
    gate can never see a value below 1. Offering 0 gave the setting two dead
    positions instead of one honest weakest filter.
    """
    settings = _settings()
    settings_min = settings.bl_rna.properties["min_affected_texels"].hard_min
    assert settings_min == 1, settings_min

    operator_rna = bpy.ops.alpha_material_separator.analyze.get_rna_type()
    operator_min = operator_rna.properties["min_affected_texels"].hard_min
    assert operator_min == 1, operator_min

    # Blender clamps rather than raising, which keeps older scripts working.
    settings.min_affected_texels = 0
    assert settings.min_affected_texels == 1, settings.min_affected_texels
    settings.property_unset("min_affected_texels")


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


def _draw_settings_panel() -> _RecordingLayout:
    layout = _RecordingLayout()
    ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings.draw(
        SimpleNamespace(layout=layout), bpy.context
    )
    return layout


def _drawn_text(layout: _RecordingLayout) -> str:
    """The panel's copy as one string, since long labels are drawn wrapped."""
    return " ".join(text for text, _icon in layout.labels)


def _assert_the_gpu_toggle_follows_the_hardware() -> None:
    """Off by default on a machine that can use the GPU, forced on where it cannot.

    The refusal lives in the property rather than in the panel row because the
    engine and any script read the property, not the row. It is deliberately
    outside ANALYSIS_SETTING_NAMES: both devices produce the same report, so
    neither toggling it nor a reset of the analysis settings should touch it.
    """
    settings = _settings()
    described = settings.bl_rna.properties[GPU_TOGGLE]
    assert described.name == "Disable GPU acceleration", described.name
    assert described.description == GPU_TOGGLE_DESCRIPTION, described.description
    assert GPU_TOGGLE not in ANALYSIS_SETTING_NAMES
    assert getattr(settings, GPU_TOGGLE) is not gpu_raster.available()

    original = gpu_raster.available
    gpu_raster.available = lambda: False
    try:
        assert getattr(settings, GPU_TOGGLE) is True
        setattr(settings, GPU_TOGGLE, False)
        assert getattr(settings, GPU_TOGGLE) is True, "the fallback was cleared"
    finally:
        gpu_raster.available = original


def _assert_an_unusable_gpu_says_why() -> None:
    """Two messages, and the reason picks between them.

    A missing instruction set is a fact about the hardware and is worth saying
    plainly. Anything else — a driver that miscompiles the kernel, a probe that
    raised — is not something the reader can act on, so it says so.
    """
    original_available, original_reason = gpu_raster.available, gpu_raster.reason
    gpu_raster.available = lambda: False
    try:
        gpu_raster.reason = lambda: "NO_FP64: this GPU computes double as single"
        drawn = _drawn_text(_draw_settings_panel())
        assert GPU_MISSING_INSTRUCTIONS in drawn, drawn

        gpu_raster.reason = lambda: "MISMATCH: the self-test did not reproduce"
        drawn = _drawn_text(_draw_settings_panel())
        assert GPU_UNKNOWN_FAILURE in drawn, drawn
    finally:
        gpu_raster.available, gpu_raster.reason = original_available, original_reason

    # A usable GPU explains nothing, because there is nothing to explain.
    if gpu_raster.available():
        drawn = _drawn_text(_draw_settings_panel())
        assert GPU_MISSING_INSTRUCTIONS not in drawn, drawn
        assert GPU_UNKNOWN_FAILURE not in drawn, drawn


def _assert_the_gpu_toggle_keeps_a_report() -> None:
    """Switching device does not make a completed report stale.

    The two paths are exact reproductions of each other, so the input signature
    does not carry the choice, and a reset of the analysis settings leaves it
    where the reader put it.
    """
    if not gpu_raster.available():
        return
    _clear_scene()
    image = _image("AMS_GPU_TOGGLE_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_GPU_TOGGLE_SOURCE", image)
    _quad("AMS_GPU_TOGGLE_OBJECT", material)
    settings = _settings()

    _analyze_clean_report()
    setattr(settings, GPU_TOGGLE, True)
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    assert getattr(settings, GPU_TOGGLE) is True, "a settings reset changed the device"

    # The CPU fallback has to produce the same report the GPU just produced.
    _analyze_clean_report()
    setattr(settings, GPU_TOGGLE, False)
    _clear_scene()


def _assert_public_setting_names_are_guarded() -> None:
    """Every guarded name must exist on the real analyze operator RNA."""

    from addon import api_contract
    from addon.properties import ANALYSIS_SETTING_NAMES as PANEL_NAMES

    assert api_contract.ANALYSIS_SETTING_NAMES == PANEL_NAMES, (
        api_contract.ANALYSIS_SETTING_NAMES,
        PANEL_NAMES,
    )
    properties = bpy.ops.alpha_material_separator.analyze.get_rna_type().properties
    missing = [
        name for name in api_contract.ANALYSIS_SETTING_NAMES if name not in properties
    ]
    assert not missing, missing


def run() -> None:
    _assert_public_setting_names_are_guarded()
    _assert_names_cover_the_panel()
    _assert_descriptions_are_artist_readable()
    _assert_minimum_affected_pixels_is_reachable()
    _assert_the_gpu_toggle_follows_the_hardware()
    _assert_an_unusable_gpu_says_why()
    _assert_the_gpu_toggle_keeps_a_report()
    _assert_reset_behavior()
    print("ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK")
