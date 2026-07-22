# SPDX-License-Identifier: GPL-3.0-or-later
"""Transient reports, cache state, and conservative Blender invalidation hints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import bpy
from bpy.app.handlers import persistent

if TYPE_CHECKING:
    from .adapters.analysis import AnalysisReport

_STATE: dict[str, Any] = {}
_REPORT: "AnalysisReport | None" = None
_DIRTY_REASON = ""
_COVERAGE_CACHE: dict[str, Any] = {}


def _ui(window_manager=None):
    window_manager = window_manager or getattr(bpy.context, "window_manager", None)
    return getattr(window_manager, "alpha_material_separator_ui", None)


def tag_redraw() -> None:
    for window_manager in bpy.data.window_managers:
        for window in window_manager.windows:
            screen = window.screen
            if screen is None:
                continue
            for area in screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()


def clear_review(window_manager=None) -> None:
    ui = _ui(window_manager)
    if ui is not None:
        ui.reviewed_analysis_id = ""
        ui.reviewed_policy_signature = ""


def set_review(window_manager, analysis_id: str, policy_signature: str) -> None:
    ui = _ui(window_manager)
    if ui is not None:
        ui.reviewed_analysis_id = analysis_id
        ui.reviewed_policy_signature = policy_signature


def review_matches(window_manager, analysis_id: str, policy_signature: str) -> bool:
    ui = _ui(window_manager)
    return bool(
        ui is not None
        and ui.reviewed_analysis_id == analysis_id
        and ui.reviewed_policy_signature == policy_signature
    )


def begin_analysis(window_manager) -> bool:
    ui = _ui(window_manager)
    if ui is None or ui.is_analyzing:
        return False
    ui.is_analyzing = True
    ui.analysis_progress = 0.0
    ui.analysis_stage = "Preparing inputs"
    ui.cancel_requested = False
    clear_review(window_manager)
    tag_redraw()
    return True


def update_analysis(window_manager, completed: int, total: int, stage: str) -> None:
    ui = _ui(window_manager)
    if ui is None:
        return
    next_progress = min(1.0, max(ui.analysis_progress, completed / max(1, total)))
    ui.analysis_progress = next_progress
    ui.analysis_stage = stage
    tag_redraw()


def request_cancel(window_manager) -> None:
    ui = _ui(window_manager)
    if ui is not None and ui.is_analyzing:
        ui.cancel_requested = True
        ui.analysis_stage = "Canceling safely"
        tag_redraw()


def cancellation_requested(window_manager) -> bool:
    ui = _ui(window_manager)
    return bool(ui is not None and ui.cancel_requested)


def finish_analysis(window_manager) -> None:
    ui = _ui(window_manager)
    if ui is not None:
        ui.is_analyzing = False
        ui.analysis_progress = 0.0
        ui.analysis_stage = ""
        ui.cancel_requested = False
    tag_redraw()


def clear(*, preserve_completion: bool = False) -> None:
    """Drop every transient reference owned by the extension."""
    global _REPORT, _DIRTY_REASON
    _STATE.clear()
    _COVERAGE_CACHE.clear()
    _REPORT = None
    _DIRTY_REASON = ""
    for window_manager in bpy.data.window_managers:
        ui = _ui(window_manager)
        if ui is not None:
            ui.is_analyzing = False
            ui.analysis_progress = 0.0
            ui.analysis_stage = ""
            ui.cancel_requested = False
            clear_review(window_manager)
            if not preserve_completion:
                ui.last_completion_json = "{}"


def set_report(report: "AnalysisReport") -> None:
    global _REPORT, _DIRTY_REASON
    _REPORT = report
    _DIRTY_REASON = ""
    _STATE["analysis_id"] = report.analysis_id
    for window_manager in bpy.data.window_managers:
        clear_review(window_manager)
        ui = _ui(window_manager)
        if ui is not None:
            ui.last_completion_json = "{}"


def report(expected_analysis_id: str = "") -> "AnalysisReport | None":
    if _REPORT is None:
        return None
    if expected_analysis_id and _REPORT.analysis_id != expected_analysis_id:
        return None
    return _REPORT


def mark_dirty(reason: str) -> None:
    global _DIRTY_REASON
    if _REPORT is not None:
        _DIRTY_REASON = reason
        for window_manager in bpy.data.window_managers:
            clear_review(window_manager)
        tag_redraw()


def dirty_reason() -> str:
    return _DIRTY_REASON


def clear_dirty() -> None:
    global _DIRTY_REASON
    _DIRTY_REASON = ""


def coverage_get(key: str):
    return _COVERAGE_CACHE.get(key)


def coverage_set(key: str, coverage) -> None:
    _COVERAGE_CACHE[key] = coverage


def clear_coverage_cache() -> None:
    _COVERAGE_CACHE.clear()


def snapshot() -> dict[str, Any]:
    """Return a shallow copy for lifecycle tests."""
    result = dict(_STATE)
    result["dirty_reason"] = _DIRTY_REASON
    ui = _ui()
    if ui is not None:
        result["is_analyzing"] = ui.is_analyzing
        result["analysis_progress"] = ui.analysis_progress
        result["reviewed_analysis_id"] = ui.reviewed_analysis_id
    return result


@persistent
def _clear_on_file_state_change(_unused=None) -> None:
    clear()
    for window_manager in bpy.data.window_managers:
        state = getattr(window_manager, "alpha_material_separator_api", None)
        if state is not None:
            state.analysis_id = ""
            state.report_json = "{}"


@persistent
def _depsgraph_hint(_scene, depsgraph) -> None:
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Mesh):
            clear_coverage_cache()
            mark_dirty("MESH_UPDATED")
            return
        if isinstance(update.id, (bpy.types.Image, bpy.types.Material)):
            mark_dirty(f"{update.id.bl_rna.identifier.upper()}_UPDATED")
            return


_CLEAR_HANDLERS = (
    bpy.app.handlers.load_post,
    bpy.app.handlers.undo_post,
    bpy.app.handlers.redo_post,
)


def register_handlers() -> None:
    for handlers in _CLEAR_HANDLERS:
        if _clear_on_file_state_change not in handlers:
            handlers.append(_clear_on_file_state_change)
    if _depsgraph_hint not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_hint)


def unregister_handlers() -> None:
    for handlers in _CLEAR_HANDLERS:
        if _clear_on_file_state_change in handlers:
            handlers.remove(_clear_on_file_state_change)
    if _depsgraph_hint in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_hint)
