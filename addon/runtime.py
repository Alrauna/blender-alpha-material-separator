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


def clear() -> None:
    """Drop every transient reference owned by the extension."""
    global _REPORT, _DIRTY_REASON
    _STATE.clear()
    _COVERAGE_CACHE.clear()
    _REPORT = None
    _DIRTY_REASON = ""


def set_report(report: "AnalysisReport") -> None:
    global _REPORT, _DIRTY_REASON
    _REPORT = report
    _DIRTY_REASON = ""
    _STATE["analysis_id"] = report.analysis_id


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
