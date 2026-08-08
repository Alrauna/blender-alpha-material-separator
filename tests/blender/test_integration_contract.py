# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for the published integration contract."""

from __future__ import annotations

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

    assert captured.get("result") == {"CANCELLED"}, captured
    assert captured.get("engine_after") is None
    assert observed == ["ANALYSIS_CANCELLED"], observed
    assert state.last_status_code == "ANALYSIS_CANCELLED", state.last_status_code


def run() -> None:
    _assert_legacy_arguments_do_not_persist()
    _assert_cancel_publishes_before_teardown()
    print("ALPHA_MATERIAL_SEPARATOR_INTEGRATION_CONTRACT_TESTS_OK")
