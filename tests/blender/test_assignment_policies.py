# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative SUPPRESSED and UNSUPPORTED assignment policy tests."""

from __future__ import annotations

import json

import bpy

from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad
from tests.blender.test_assignment import _analyze, _assign


def run() -> None:
    _clear_scene()
    image = _image("AMS_POLICY_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_POLICY_SOURCE", image)
    object_ = _quad("AMS_POLICY_OBJECT", material)

    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    report = json.loads(state.report_json)
    assert report["counts"]["SUPPRESSED"] == 1, report
    blocked, blocked_state = _assign(state.analysis_id)
    assert blocked == {"CANCELLED"}, blocked_state.last_status_json
    assert object_.data.polygons[0].material_index == 0

    analysis_id = _analyze(object_)
    # Re-run with suppression settings, since _analyze uses defaults.
    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}
    analysis_id = state.analysis_id
    informed, informed_state = _assign(
        analysis_id, suppressed_policy="TO_ALPHA"
    )
    assert informed == {"FINISHED"}, informed_state.last_status_json
    assert object_.data.polygons[0].material_index == 1

    _clear_scene()
    unsupported_material = bpy.data.materials.new("AMS_UNSUPPORTED_SOURCE")
    unsupported = _quad("AMS_UNSUPPORTED_OBJECT", unsupported_material)
    analysis_id = _analyze(unsupported)
    report = json.loads(state.report_json)
    assert report["counts"]["UNSUPPORTED"] == 1, report
    blocked, blocked_state = _assign(analysis_id)
    assert blocked == {"CANCELLED"}, blocked_state.last_status_json
    analysis_id = _analyze(unsupported)
    kept, kept_state = _assign(analysis_id, unsupported_policy="KEEP_SOURCE")
    assert kept == {"FINISHED"}, kept_state.last_status_json
    assert unsupported.data.polygons[0].material_index == 0
    print("ALPHA_MATERIAL_SEPARATOR_ASSIGNMENT_POLICY_TESTS_OK")
