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
from tests.blender.test_analysis_preview import run as run_analysis_preview_tests  # noqa: E402
from tests.blender.test_assignment import run as run_assignment_tests  # noqa: E402
from tests.blender.test_assignment_policies import (  # noqa: E402
    run as run_assignment_policy_tests,
)
from tests.blender.test_identity_transitions import (  # noqa: E402
    run as run_identity_transition_tests,
)
from tests.blender.test_fbx_export import run as run_fbx_export_tests  # noqa: E402
from tests.blender.test_preservation import run as run_preservation_tests  # noqa: E402
from tests.blender.test_ux_overrides import run as run_ux_override_tests  # noqa: E402
from tests.blender.test_revalidation_matrix import (  # noqa: E402
    run as run_revalidation_matrix_tests,
)
from tests.blender.test_simplification_contracts import (  # noqa: E402
    run as run_simplification_contracts,
)


def assert_operator_registered() -> None:
    result = bpy.ops.alpha_material_separator.query_capabilities(
        requested_api_major=1
    )
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    capabilities = json.loads(state.capabilities_json)
    status = json.loads(state.last_status_json)
    assert capabilities["api_version"] == "1.2", capabilities
    assert capabilities["capabilities"]["query_capabilities"] is True
    assert capabilities["capabilities"]["analysis"] is True
    assert capabilities["capabilities"]["face_selection_preview"] is True
    assert capabilities["capabilities"]["per_material_overrides"] is True
    assert capabilities["capabilities"]["partial_material_assignment"] is True
    assert capabilities["capabilities"]["component_revalidation"] is True
    assert state.validation_state in {"CLEAN", "RECHECK_PENDING", "STALE"}
    assert json.loads(state.pending_scopes_json) == []
    assert capabilities["capabilities"]["plan_derived_preview"] is True
    assert capabilities["capabilities"]["reason_scoped_unsupported"] is True
    assert status["code"] == "OK", status


def assert_unregistered() -> None:
    assert not hasattr(
        bpy.types.WindowManager, "alpha_material_separator_api"
    ), "WindowManager property leaked after unregister"
    assert not hasattr(
        bpy.types.WindowManager, "alpha_material_separator_settings"
    ), "WindowManager settings leaked after unregister"
    assert not hasattr(
        bpy.types.WindowManager, "alpha_material_separator_ui"
    ), "WindowManager UI state leaked after unregister"
    assert not hasattr(
        bpy.types, "ALPHA_MATERIAL_SEPARATOR_PT_main"
    ), "Panel leaked after unregister"
    assert not hasattr(
        bpy.types.Material, "alpha_material_separator_source"
    ), "Material source-pointer property leaked after unregister"


def run() -> None:
    for iteration in range(2):
        addon.register()
        assert hasattr(bpy.types.WindowManager, "alpha_material_separator_api")
        assert hasattr(bpy.types.WindowManager, "alpha_material_separator_settings")
        assert hasattr(bpy.types.WindowManager, "alpha_material_separator_ui")
        assert hasattr(bpy.types.Material, "alpha_material_separator_source")
        assert bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_main.bl_category == "AMS"
        assert (
            bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings.bl_category
            == "AMS"
        )
        assert_operator_registered()
        if iteration == 0:
            run_analysis_preview_tests()
            run_assignment_tests()
            run_assignment_policy_tests()
            run_simplification_contracts()
            run_identity_transition_tests()
            run_fbx_export_tests()
            run_preservation_tests()
            run_ux_override_tests()
            run_revalidation_matrix_tests()

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
