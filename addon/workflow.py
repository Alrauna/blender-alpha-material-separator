# SPDX-License-Identifier: GPL-3.0-or-later
"""The single guided-workflow computation the panel draws and the API publishes.

The panel and `workflow_json` share this snapshot so the drawn state and the
published state cannot drift. Everything here is derived; nothing is stored.
"""

from __future__ import annotations

from . import runtime
from .adapters.assignment import build_assignment_plan
from .presentation import (
    already_separated_tooltip,
    json_object,
    review_signature,
    workflow_view,
)


def build_plan(report, settings):
    """Build the assignment plan the current settings imply."""
    if report is None:
        return None
    return build_assignment_plan(
        report,
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        conflict_policy=settings.derived_conflict_policy,
    )


def policy_signature(state, settings, plan_payload=None) -> str:
    """Fingerprint the exact operation a Preview would review."""
    return review_signature(
        state.analysis_id,
        settings.mixed_policy,
        settings.suppressed_policy,
        settings.unsupported_policy,
        settings.derived_conflict_policy,
        plan_payload,
    )


def snapshot(context) -> dict:
    """Compute the current workflow state from authoritative Blender state.

    Returns every field in `api_contract.WORKFLOW_FIELDS` plus the live objects
    the panel draws from. Two of the inputs — the selected objects and the four
    policy enums — change with no extension operator running, which is exactly
    when Preview and Apply flip, so this is computed on demand rather than
    refreshed at status transitions.
    """
    # ponytail: one plan build per call, no memo. The panel already builds a
    # plan per redraw and a consumer read makes it two. Add a memo keyed on
    # (analysis_id, runtime hint generation, policies, selection) only if the
    # redraw benchmark in docs/testing.md measures a real cost.
    window_manager = context.window_manager
    state = window_manager.alpha_material_separator_api
    settings = window_manager.alpha_material_separator_settings
    ui = window_manager.alpha_material_separator_ui

    eligible = tuple(obj for obj in context.selected_objects if obj.type == "MESH")
    report = runtime.report(state.analysis_id)
    stale = bool(runtime.dirty_reason())
    try:
        plan = build_plan(report, settings) if report is not None and not stale else None
    except (AttributeError, KeyError, ReferenceError, RuntimeError):
        # An input datablock disappeared under us; treat the report as stale
        # rather than drawing or publishing a plan built from missing data.
        plan = None
        stale = True
    plan_payload = plan.public_payload() if plan else {}
    # Only meaningful once a report exists to review; the panel likewise never
    # draws or assigns this signature outside its "if current_report:" block.
    signature = policy_signature(state, settings, plan_payload) if report is not None else ""
    actionable = bool(plan and plan.actionable)
    no_change_tooltip = already_separated_tooltip(
        already_derived=bool(plan and plan.already_derived),
        actionable=actionable,
    )
    reviewed = runtime.review_matches(window_manager, state.analysis_id, signature)
    completed = bool(
        json_object(ui.last_completion_json)
        or (
            state.last_status_code.startswith("ASSIGNMENT_")
            and json_object(state.last_status_json)
        )
    )
    view = workflow_view(
        eligible_objects=len(eligible),
        running=ui.is_analyzing,
        has_report=bool(report),
        stale=stale,
        reviewed=reviewed,
        actionable=actionable,
        completed=completed,
    )
    return {
        **view,
        "running": bool(ui.is_analyzing),
        "stale": stale,
        "reviewed": reviewed,
        "actionable": actionable,
        "already_separated": bool(no_change_tooltip),
        "eligible_object_count": len(eligible),
        "analysis_id": state.analysis_id,
        "validation_state": runtime.validation_state(),
        "expected_review_signature": signature,
        # Live objects for the panel. Never published; see WORKFLOW_FIELDS.
        "eligible_objects": eligible,
        "report": report,
        "plan": plan,
        "plan_payload": plan_payload,
        "no_change_tooltip": no_change_tooltip,
    }
