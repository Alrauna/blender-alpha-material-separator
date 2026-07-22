# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless registration and capability-query smoke tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import addon  # noqa: E402
from tests.blender.test_material_characterization import (  # noqa: E402
    run as run_characterization_tests,
)


def assert_operator_registered() -> None:
    result = bpy.ops.alpha_material_separator.query_capabilities(
        requested_api_major=1
    )
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    capabilities = json.loads(state.capabilities_json)
    status = json.loads(state.last_status_json)
    assert capabilities["api_version"] == "1.0", capabilities
    assert capabilities["capabilities"]["query_capabilities"] is True
    assert capabilities["capabilities"]["analysis"] is False
    assert status["code"] == "OK", status


def assert_unregistered() -> None:
    assert not hasattr(
        bpy.types.WindowManager, "alpha_material_separator_api"
    ), "WindowManager property leaked after unregister"
    assert not hasattr(
        bpy.types, "ALPHA_MATERIAL_SEPARATOR_PT_main"
    ), "Panel leaked after unregister"


def run() -> None:
    for _ in range(2):
        addon.register()
        assert hasattr(bpy.types.WindowManager, "alpha_material_separator_api")
        assert_operator_registered()

        clear_result = bpy.ops.alpha_material_separator.clear_results(api_major=1)
        assert clear_result == {"FINISHED"}, clear_result
        assert (
            bpy.context.window_manager.alpha_material_separator_api.last_status_code
            == "CLEARED"
        )

        incompatible = bpy.ops.alpha_material_separator.query_capabilities(
            requested_api_major=99
        )
        assert incompatible == {"FINISHED"}, incompatible
        assert (
            bpy.context.window_manager.alpha_material_separator_api.last_status_code
            == "API_INCOMPATIBLE"
        )

        addon.unregister()
        assert_unregistered()

    run_characterization_tests()
    print("ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK")


if __name__ == "__main__":
    run()
