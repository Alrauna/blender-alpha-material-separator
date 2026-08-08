# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for the published integration contract."""

from __future__ import annotations

import json

import bpy

LEGACY_PER_CALL_ARGUMENTS = ("image_name", "uv_map_name", "image_channel")


def _assert_legacy_arguments_do_not_persist() -> None:
    """A stale value from a previous invocation must not silently apply."""

    properties = bpy.ops.alpha_material_separator.analyze.get_rna_type().properties
    for name in LEGACY_PER_CALL_ARGUMENTS:
        definition = properties[name]
        assert definition.is_skip_save, (name, definition.is_skip_save)


def _assert_cancel_publishes_before_teardown() -> None:
    """A redraw triggered by teardown must not see the previous status.

    Blender's Operator subclasses cannot be instantiated directly from
    Python (``bpy_struct.__new__`` refuses it), and background mode has no
    event loop to drive a real modal handler, so ``execute()`` is
    temporarily replaced to capture the live, RNA-backed instance Blender
    creates for the call and drive ``modal()`` on it directly, matching
    what the real cancel path exercises.
    """

    from addon import runtime
    from addon.operators.analyze import ALPHA_MATERIAL_SEPARATOR_OT_analyze

    state = bpy.context.window_manager.alpha_material_separator_api
    original_status_code = state.last_status_code
    state.last_status_code = "ANALYSIS_COMPLETE"
    observed: list[str] = []
    captured: dict[str, object] = {}

    class _StubEngine:
        cancelled = False

        def cancel(self):
            self.cancelled = True

        def close(self):
            pass

    original_finish = runtime.finish_analysis
    original_execute = ALPHA_MATERIAL_SEPARATOR_OT_analyze.execute

    def _recording_finish(window_manager):
        observed.append(state.last_status_code)
        original_finish(window_manager)

    def _replacement_execute(self, context):
        self._engine = _StubEngine()
        self._timer = None
        runtime.finish_analysis = _recording_finish
        try:
            captured["result"] = self.modal(
                context, type("_Event", (), {"type": "ESC"})()
            )
        finally:
            runtime.finish_analysis = original_finish
        captured["engine_after"] = self._engine
        return {"FINISHED"}

    ALPHA_MATERIAL_SEPARATOR_OT_analyze.execute = _replacement_execute
    try:
        # 'INVOKE_DEFAULT' is safe here only because --background has no
        # event loop, so Blender dispatches through execute() (patched
        # above) rather than the real invoke()/modal() path. If that
        # dispatch assumption is ever wrong, the `captured` check below
        # catches it and the cleanup in `finally` resets any real
        # analysis state before the assertion fails loudly.
        bpy.ops.alpha_material_separator.analyze(
            "INVOKE_DEFAULT",
            api_major=1,
            alpha_threshold=0.999,
            min_affected_texels=1,
            min_affected_fraction=0.0,
            margin_texels=0,
        )
    finally:
        ALPHA_MATERIAL_SEPARATOR_OT_analyze.execute = original_execute
        if not captured and runtime.snapshot().get("is_analyzing"):
            # The real invoke() ran instead of the patched execute(): it
            # started a real analysis, timer, and modal handler that
            # nothing will ever tick or tear down in this process. Reset
            # the shared analysis-state flags so later suites are not
            # left thinking an analysis is still running.
            runtime.finish_analysis(bpy.context.window_manager)

    assert captured, "analyze() did not dispatch through execute() in background mode"
    assert captured.get("result") == {"CANCELLED"}, captured
    assert captured.get("engine_after") is None
    assert observed == ["ANALYSIS_CANCELLED"], observed
    assert state.last_status_code == "ANALYSIS_CANCELLED", state.last_status_code
    state.last_status_code = original_status_code


def _assert_stale_result_publishes_a_status() -> None:
    """A stale report must not leave a success code as the last status."""

    from addon import runtime
    from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad

    _clear_scene()
    image = _image("AMS_CONTRACT_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_CONTRACT_MATERIAL", image)
    quad = _quad("AMS_CONTRACT_QUAD", material)
    bpy.ops.object.select_all(action="DESELECT")
    quad.select_set(True)
    bpy.context.view_layer.objects.active = quad

    assert bpy.ops.alpha_material_separator.analyze(api_major=1) == {"FINISHED"}
    state = bpy.context.window_manager.alpha_material_separator_api
    assert state.last_status_code == "ANALYSIS_COMPLETE", state.last_status_code
    assert state.validation_state == runtime.VALIDATION_CLEAN, state.validation_state
    analysis_id = state.analysis_id

    settings = bpy.context.window_manager.alpha_material_separator_settings
    settings.alpha_threshold = 0.5

    assert state.validation_state == runtime.VALIDATION_STALE, state.validation_state
    assert state.last_status_code == "RESULT_STALE", state.last_status_code
    payload = json.loads(state.last_status_json)
    assert payload["code"] == "RESULT_STALE", payload
    assert payload["analysis_id"] == analysis_id, payload
    assert payload["dirty_reason"] == "SETTINGS_CHANGED", payload

    settings.property_unset("alpha_threshold")


def _assert_a_clean_result_keeps_its_success_status() -> None:
    """The stale status must not fire for a harmless transition."""

    from addon import runtime

    assert bpy.ops.alpha_material_separator.analyze(api_major=1) == {"FINISHED"}
    state = bpy.context.window_manager.alpha_material_separator_api
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = bpy.context.view_layer.objects[0]
    bpy.context.view_layer.objects[0].select_set(True)
    assert state.validation_state != runtime.VALIDATION_STALE, state.validation_state
    assert state.last_status_code == "ANALYSIS_COMPLETE", state.last_status_code


def run() -> None:
    _assert_legacy_arguments_do_not_persist()
    _assert_cancel_publishes_before_teardown()
    _assert_stale_result_publishes_a_status()
    _assert_a_clean_result_keeps_its_success_status()
    print("ALPHA_MATERIAL_SEPARATOR_INTEGRATION_CONTRACT_TESTS_OK")
