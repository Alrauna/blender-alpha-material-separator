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
HIGH_PRECISION = "high_precision_gpu"
HIGH_PRECISION_DESCRIPTION = (
    "Analyze in double precision on the GPU, which reproduces CPU analysis "
    "exactly and is slower"
)
GPU_UNKNOWN_FAILURE = (
    "This GPU does not support GPU acceleration with this extension for an "
    "unknown reason"
)
NO_DOUBLE_PRECISION = (
    "This GPU does not compute in double precision. Analysis still runs on the "
    "GPU in single precision; disable GPU acceleration for exact results"
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
    gpu_raster.available = lambda **_: False
    try:
        assert getattr(settings, GPU_TOGGLE) is True
        setattr(settings, GPU_TOGGLE, False)
        assert getattr(settings, GPU_TOGGLE) is True, "the fallback was cleared"
    finally:
        gpu_raster.available = original


def _assert_high_precision_follows_the_hardware() -> None:
    """Off by default, and unreachable where the GPU cannot compute in double.

    A machine without fp64 keeps accelerating; the only thing it loses is this
    mode. The refusal lives in the property rather than in the panel row for the
    same reason the device fallback does: the engine and any script read the
    property, and a greyed-out row would only stop the row.
    """
    settings = _settings()
    described = settings.bl_rna.properties[HIGH_PRECISION]
    assert described.name == "High precision GPU acceleration", described.name
    assert described.description == HIGH_PRECISION_DESCRIPTION, described.description
    assert HIGH_PRECISION not in ANALYSIS_SETTING_NAMES

    original = gpu_raster.available
    gpu_raster.available = lambda **kwargs: not kwargs.get("high_precision")
    try:
        setattr(settings, HIGH_PRECISION, True)
        assert getattr(settings, HIGH_PRECISION) is False, (
            "high precision was offered on a GPU without double precision"
        )
    finally:
        gpu_raster.available = original

    if gpu_raster.available(high_precision=True):
        assert getattr(settings, HIGH_PRECISION) is True, (
            "the stored choice did not come back when the hardware allows it"
        )
        setattr(settings, HIGH_PRECISION, False)
        assert getattr(settings, HIGH_PRECISION) is False


def _assert_an_unusable_gpu_says_why() -> None:
    """Two situations, and the reader is told which one this machine is in.

    A GPU the kernel cannot run at all is not something the reader can act on,
    so the copy says only that. A GPU that merely lacks double precision is a
    different message entirely: acceleration is still on, and what the reader
    loses is the exact mode. Saying the first where the second is true would
    send someone hunting for a driver they do not need.
    """
    original_available, original_reason = gpu_raster.available, gpu_raster.reason
    try:
        gpu_raster.available = lambda **_: False
        gpu_raster.reason = lambda **_: "MISMATCH: the self-test did not reproduce"
        drawn = _drawn_text(_draw_settings_panel())
        assert GPU_UNKNOWN_FAILURE in drawn, drawn
        assert NO_DOUBLE_PRECISION not in drawn, drawn

        # The kernel runs; only double precision is missing.
        gpu_raster.available = lambda **kwargs: not kwargs.get("high_precision")
        gpu_raster.reason = lambda **_: "NO_FP64: this GPU computes double as single"
        drawn = _drawn_text(_draw_settings_panel())
        assert NO_DOUBLE_PRECISION in drawn, drawn
        assert GPU_UNKNOWN_FAILURE not in drawn, drawn
    finally:
        gpu_raster.available, gpu_raster.reason = original_available, original_reason

    # A wholly usable GPU explains nothing, because there is nothing to explain.
    if gpu_raster.available(high_precision=True):
        drawn = _drawn_text(_draw_settings_panel())
        assert NO_DOUBLE_PRECISION not in drawn, drawn
        assert GPU_UNKNOWN_FAILURE not in drawn, drawn


def _assert_the_gpu_toggles_track_precision() -> None:
    """A change of width invalidates a report; a change of device alone does not.

    The default kernel computes in single precision, so leaving it for the CPU
    changes what the numbers would be and the report no longer matches its
    inputs. Going from the CPU to high precision does not: those two reproduce
    each other exactly. A settings reset still leaves both toggles where the
    reader put them, because neither is an analysis parameter.
    """
    if not gpu_raster.available(high_precision=True):
        return
    _clear_scene()
    image = _image("AMS_GPU_TOGGLE_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_GPU_TOGGLE_SOURCE", image)
    _quad("AMS_GPU_TOGGLE_OBJECT", material)
    settings = _settings()

    # Single precision on the GPU, then the exact result: a different input.
    _analyze_clean_report()
    setattr(settings, GPU_TOGGLE, True)
    assert runtime.validation_state() == runtime.VALIDATION_STALE, (
        runtime.validation_state()
    )
    assert runtime.dirty_reason() == "SETTINGS_CHANGED", runtime.dirty_reason()
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    assert getattr(settings, GPU_TOGGLE) is True, "a settings reset changed the device"

    # The CPU report the reader now holds is exactly what high precision would
    # produce, so asking for it leaves that report standing.
    _analyze_clean_report()
    setattr(settings, HIGH_PRECISION, True)
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    assert getattr(settings, HIGH_PRECISION) is True, (
        "a settings reset changed the width"
    )

    # Back to the GPU at the same width is still that report; back to the
    # default width is not.
    setattr(settings, GPU_TOGGLE, False)
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )
    setattr(settings, HIGH_PRECISION, False)
    assert runtime.validation_state() == runtime.VALIDATION_STALE, (
        runtime.validation_state()
    )
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
    _assert_high_precision_follows_the_hardware()
    _assert_an_unusable_gpu_says_why()
    _assert_the_gpu_toggles_track_precision()
    _assert_reset_behavior()
    print("ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK")
