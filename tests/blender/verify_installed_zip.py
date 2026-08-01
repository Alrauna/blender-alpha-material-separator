# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the built ZIP from an isolated Blender user configuration."""

from __future__ import annotations

import json

import bpy


def _operator_exists() -> bool:
    try:
        bpy.ops.alpha_material_separator.query_capabilities.get_rna_type()
        return True
    except (AttributeError, KeyError, RuntimeError):
        return False


def run() -> None:
    modules = [
        module
        for module in bpy.context.preferences.addons.keys()
        if module.endswith("alpha_material_separator")
    ]
    assert len(modules) == 1, modules
    module = modules[0]
    assert _operator_exists()
    result = bpy.ops.alpha_material_separator.query_capabilities(
        requested_api_major=1
    )
    assert result == {"FINISHED"}, result
    payload = json.loads(
        bpy.context.window_manager.alpha_material_separator_api.capabilities_json
    )
    assert payload["capabilities"]["analysis"] is True
    assert payload["capabilities"]["material_assignment"] is True

    disabled = bpy.ops.preferences.addon_disable(module=module)
    assert disabled == {"FINISHED"}, disabled
    assert not hasattr(bpy.types.WindowManager, "alpha_material_separator_api")
    assert not _operator_exists()

    enabled = bpy.ops.preferences.addon_enable(module=module)
    assert enabled == {"FINISHED"}, enabled
    assert hasattr(bpy.types.WindowManager, "alpha_material_separator_api")
    assert _operator_exists()
    assert bpy.ops.alpha_material_separator.query_capabilities() == {"FINISHED"}
    print("ALPHA_MATERIAL_SEPARATOR_INSTALLED_ZIP_TEST_OK")


if __name__ == "__main__":
    run()
