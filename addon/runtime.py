# SPDX-License-Identifier: GPL-3.0-or-later
"""Transient reports, cache state, and conservative Blender invalidation hints."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import bpy
from bpy.app.handlers import persistent

from . import api_contract

if TYPE_CHECKING:
    from .adapters.analysis import AnalysisReport

_STATE: dict[str, Any] = {}
_REPORT: "AnalysisReport | None" = None
_DIRTY_REASON = ""
_VALIDATION_STATE = "CLEAN"
_PENDING_SCOPES: set[str] = set()
_COVERAGE_CACHE: dict[str, Any] = {}
_HINT_GENERATION = 0
_VALIDATED_GENERATION = 0
_VALIDATED_ANALYSIS_ID = ""

VALIDATION_CLEAN = "CLEAN"
VALIDATION_RECHECK_PENDING = "RECHECK_PENDING"
VALIDATION_STALE = "STALE"


def _sync_public_validation_state() -> None:
    """Mirror transient validity into the documented WindowManager surface."""

    pending_json = json.dumps(sorted(_PENDING_SCOPES), separators=(",", ":"))
    for window_manager in bpy.data.window_managers:
        state = getattr(window_manager, "alpha_material_separator_api", None)
        if state is None:
            continue
        if hasattr(state, "validation_state"):
            state.validation_state = _VALIDATION_STATE
        if hasattr(state, "pending_scopes_json"):
            state.pending_scopes_json = pending_json
        if _VALIDATION_STATE == VALIDATION_STALE and state.analysis_id:
            # Published here, not at each call site, so every current and future
            # stale transition carries a status. A consumer must never have to
            # read validation_state to discover that ANALYSIS_COMPLETE is false.
            api_contract.publish_status(
                state,
                "RESULT_STALE",
                "Analysis inputs changed; analyze again before preview or assignment",
                analysis_id=state.analysis_id,
                dirty_reason=_DIRTY_REASON,
            )
        if not state.analysis_id or state.report_json in {"", "{}"}:
            continue
        try:
            payload = json.loads(state.report_json)
        except (TypeError, ValueError):
            continue
        if payload.get("analysis_id") != state.analysis_id:
            continue
        payload["validation_state"] = _VALIDATION_STATE
        payload["pending_scopes"] = sorted(_PENDING_SCOPES)
        payload["dirty_reason"] = _DIRTY_REASON
        state.report_json = json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )


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
    ui.analysis_progress_visible = False
    ui.analysis_stage = "Preparing Inputs"
    ui.cancel_requested = False
    tag_redraw()
    return True


def update_analysis(
    window_manager,
    completed: int,
    total: int,
    stage: str,
    *,
    show_progress: bool = True,
) -> None:
    ui = _ui(window_manager)
    if ui is None:
        return
    if show_progress:
        ui.analysis_progress = min(
            1.0,
            max(ui.analysis_progress, completed / max(1, total)),
        )
    ui.analysis_progress_visible = show_progress
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
        ui.analysis_progress_visible = False
        ui.analysis_stage = ""
        ui.cancel_requested = False
    tag_redraw()


def clear(*, preserve_completion: bool = False) -> None:
    """Drop every transient reference owned by the extension."""
    global _REPORT, _DIRTY_REASON, _VALIDATION_STATE
    global _HINT_GENERATION, _VALIDATED_GENERATION, _VALIDATED_ANALYSIS_ID
    _STATE.clear()
    _COVERAGE_CACHE.clear()
    _PENDING_SCOPES.clear()
    _REPORT = None
    _DIRTY_REASON = ""
    _VALIDATION_STATE = VALIDATION_CLEAN
    _HINT_GENERATION = 0
    _VALIDATED_GENERATION = 0
    _VALIDATED_ANALYSIS_ID = ""
    _sync_public_validation_state()
    for window_manager in bpy.data.window_managers:
        ui = _ui(window_manager)
        if ui is not None:
            ui.is_analyzing = False
            ui.analysis_progress = 0.0
            ui.analysis_progress_visible = False
            ui.analysis_stage = ""
            ui.cancel_requested = False
            clear_review(window_manager)
            if not preserve_completion:
                ui.last_completion_json = "{}"


def set_report(report: "AnalysisReport") -> None:
    global _REPORT, _DIRTY_REASON, _VALIDATION_STATE
    global _HINT_GENERATION, _VALIDATED_GENERATION, _VALIDATED_ANALYSIS_ID
    _REPORT = report
    _DIRTY_REASON = ""
    _VALIDATION_STATE = VALIDATION_CLEAN
    _PENDING_SCOPES.clear()
    _STATE["analysis_id"] = report.analysis_id
    _HINT_GENERATION += 1
    _VALIDATED_GENERATION = _HINT_GENERATION
    _VALIDATED_ANALYSIS_ID = report.analysis_id
    _sync_public_validation_state()
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
    """Mark the active report authoritatively stale.

    Settings callbacks use this path because the changed property is itself an
    analysis input.  Dependency-graph notifications must use ``mark_recheck``:
    Blender also emits those notifications for harmless selection and mode
    transitions, so a notification alone is not proof that a report is stale.
    """

    global _DIRTY_REASON, _VALIDATION_STATE, _VALIDATED_ANALYSIS_ID
    if _REPORT is not None:
        _DIRTY_REASON = reason
        _VALIDATION_STATE = VALIDATION_STALE
        _PENDING_SCOPES.clear()
        _VALIDATED_ANALYSIS_ID = ""
        _sync_public_validation_state()
        for window_manager in bpy.data.window_managers:
            clear_review(window_manager)
        tag_redraw()


def mark_recheck(reason: str, scope: str) -> None:
    """Record a relevant Blender update hint without invalidating review."""

    mark_recheck_scopes(reason, (scope,))


def mark_recheck_scopes(reason: str, scopes) -> None:
    """Coalesce one dependency-graph update burst into one pending state."""

    global _VALIDATION_STATE, _HINT_GENERATION
    if _REPORT is None or _VALIDATION_STATE == VALIDATION_STALE:
        return
    for scope in scopes:
        normalized_scope = str(scope).strip().upper() or "UNKNOWN"
        _PENDING_SCOPES.add(normalized_scope)
    if not _PENDING_SCOPES:
        return
    _HINT_GENERATION += 1
    _STATE["last_recheck_hint"] = reason
    _VALIDATION_STATE = VALIDATION_RECHECK_PENDING
    _sync_public_validation_state()
    tag_redraw()


def dirty_reason() -> str:
    """Return only a confirmed stale reason, never a depsgraph hint."""

    return _DIRTY_REASON


def validation_state() -> str:
    return _VALIDATION_STATE


def pending_scopes() -> frozenset[str]:
    return frozenset(_PENDING_SCOPES)


def validation_is_current(analysis_id: str) -> bool:
    return bool(
        _VALIDATION_STATE == VALIDATION_CLEAN
        and _VALIDATED_ANALYSIS_ID == analysis_id
        and _VALIDATED_GENERATION == _HINT_GENERATION
    )


def record_validation(
    mode: str,
    valid: bool,
    reason: str,
    *,
    component_hash_calls: int = 0,
    image_digest_rows: int = 0,
    rasterized_polygons: int = 0,
    coverage_hits: int = 0,
    coverage_misses: int = 0,
    elapsed_seconds: float = 0.0,
) -> None:
    """Publish a synchronous validation result and update report validity."""

    global _DIRTY_REASON, _VALIDATION_STATE
    global _VALIDATED_GENERATION, _VALIDATED_ANALYSIS_ID
    _STATE["last_validation_mode"] = mode
    _STATE["last_validation_reason"] = reason
    _STATE["last_validation_component_hash_calls"] = int(component_hash_calls)
    _STATE["last_validation_image_digest_rows"] = int(image_digest_rows)
    _STATE["last_validation_rasterized_polygons"] = int(rasterized_polygons)
    _STATE["last_validation_coverage_hits"] = int(coverage_hits)
    _STATE["last_validation_coverage_misses"] = int(coverage_misses)
    _STATE["last_validation_elapsed_seconds"] = max(0.0, float(elapsed_seconds))
    if valid:
        _DIRTY_REASON = ""
        _PENDING_SCOPES.clear()
        _VALIDATION_STATE = VALIDATION_CLEAN
        _VALIDATED_GENERATION = _HINT_GENERATION
        _VALIDATED_ANALYSIS_ID = _REPORT.analysis_id if _REPORT is not None else ""
        _sync_public_validation_state()
        return
    _DIRTY_REASON = reason
    _PENDING_SCOPES.clear()
    _VALIDATION_STATE = VALIDATION_STALE
    _VALIDATED_ANALYSIS_ID = ""
    _sync_public_validation_state()
    for window_manager in bpy.data.window_managers:
        clear_review(window_manager)
    tag_redraw()
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
    result["validation_state"] = _VALIDATION_STATE
    result["pending_scopes"] = sorted(_PENDING_SCOPES)
    result["coverage_cache_entries"] = len(_COVERAGE_CACHE)
    result["hint_generation"] = _HINT_GENERATION
    result["validated_generation"] = _VALIDATED_GENERATION
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
    scopes: set[str] = set()
    reasons: set[str] = set()
    for update in depsgraph.updates:
        update_id = update.id
        scope = _relevant_update_scope(update_id)
        if scope:
            try:
                identifier = update_id.bl_rna.identifier.upper()
            except (AttributeError, ReferenceError, RuntimeError):
                identifier = "DATABLOCK"
            scopes.add(scope)
            reasons.add(f"{identifier}_UPDATED")
    if scopes:
        mark_recheck_scopes(",".join(sorted(reasons)), scopes)


def _same_datablock(left, right) -> bool:
    try:
        return left == right or left.as_pointer() == right.as_pointer()
    except (AttributeError, ReferenceError, RuntimeError):
        return False


def _node_tree_contains(root, target, visited: set[int] | None = None) -> bool:
    if root is None:
        return False
    visited = visited or set()
    try:
        pointer = root.as_pointer()
        if pointer in visited:
            return False
        visited.add(pointer)
        if _same_datablock(root, target):
            return True
        return any(
            _node_tree_contains(getattr(node, "node_tree", None), target, visited)
            for node in root.nodes
            if getattr(node, "node_tree", None) is not None
        )
    except (AttributeError, ReferenceError, RuntimeError):
        return False


def _relevant_update_scope(update_id) -> str:
    """Return the validation scope when an updated ID participates in the report."""

    report_ = _REPORT
    if report_ is None:
        return ""
    try:
        original = getattr(update_id, "original", None)
        if original is not None:
            update_id = original
        if isinstance(update_id, bpy.types.Object):
            return "OBJECT" if any(
                _same_datablock(update_id, object_) for object_ in report_.objects
            ) else ""
        if isinstance(update_id, bpy.types.Mesh):
            return "MESH" if any(
                _same_datablock(update_id, object_.data)
                for object_ in report_.objects
                if object_.type == "MESH"
            ) else ""
        if isinstance(update_id, bpy.types.Material):
            return "MATERIAL" if any(
                _same_datablock(update_id, group.material)
                for result in report_.object_results.values()
                for group in result.groups.values()
            ) else ""
        if isinstance(update_id, bpy.types.Image):
            return "IMAGE" if any(
                group.resolution.image is not None
                and _same_datablock(update_id, group.resolution.image)
                for result in report_.object_results.values()
                for group in result.groups.values()
            ) else ""
        if isinstance(update_id, bpy.types.NodeTree):
            return "MATERIAL" if any(
                _node_tree_contains(group.material.node_tree, update_id)
                for result in report_.object_results.values()
                for group in result.groups.values()
            ) else ""
    except (ReferenceError, RuntimeError):
        # A participating datablock disappearing is authoritative only after
        # synchronous validation; retain the conservative unknown hint here.
        return "UNKNOWN"
    return ""


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
