# SPDX-License-Identifier: GPL-3.0-or-later
"""The published workflow surface must equal what the panel draws."""

from __future__ import annotations

import json

import bpy

from addon import api_contract, runtime, workflow
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad


class _Update:
    def __init__(self, datablock) -> None:
        self.id = datablock


class _Depsgraph:
    def __init__(self, *datablocks) -> None:
        self.updates = tuple(_Update(datablock) for datablock in datablocks)


def _hint(*datablocks) -> None:
    runtime._depsgraph_hint(None, _Depsgraph(*datablocks))


def _published() -> dict:
    state = bpy.context.window_manager.alpha_material_separator_api
    return json.loads(state.workflow_json)


def _assert_published_matches_live_snapshot(label: str) -> dict:
    """The drawn state and the published state come from one computation."""
    published = _published()
    live = api_contract.workflow_payload(workflow.snapshot(bpy.context))
    assert published == live, (label, published, live)
    assert set(published) == set(api_contract.WORKFLOW_FIELDS) | {"api_version"}, published
    assert published["api_version"] == "1.3", published
    assert published["state"] in api_contract.WORKFLOW_STATES, published
    return published


def _assert_idle_offers_nothing_without_a_selection() -> None:
    bpy.ops.object.select_all(action="DESELECT")
    published = _assert_published_matches_live_snapshot("idle")
    assert published["state"] == "IDLE", published
    assert published["can_analyze"] is False, published
    assert published["eligible_object_count"] == 0, published
    assert published["expected_review_signature"] == "", published


def _assert_analysis_publishes_an_actionable_plan(object_) -> dict:
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_
    analyzed = bpy.ops.alpha_material_separator.analyze()
    assert analyzed == {"FINISHED"}, analyzed
    published = _assert_published_matches_live_snapshot("analyzed")
    assert published["state"] == "READY_TO_REVIEW", published
    assert published["actionable"] is True, published
    assert published["can_preview"] is True, published
    assert published["can_apply"] is True, published
    assert published["reviewed"] is False, published
    assert published["stale"] is False, published
    assert published["validation_state"] == "CLEAN", published
    assert published["expected_review_signature"], published
    return published


def _assert_recheck_pending_keeps_the_buttons_enabled(image) -> None:
    """A depsgraph hint is not proof of staleness.

    Widening runtime's publish guard to RECHECK_PENDING, or gating the
    published booleans on validation_state instead of dirty_reason, would hide
    Preview and Apply on a harmless selection or mode change. This test fails
    if that ever happens.
    """
    _hint(image)
    assert runtime.validation_state() == "RECHECK_PENDING", runtime.snapshot()
    published = _assert_published_matches_live_snapshot("recheck_pending")
    assert published["validation_state"] == "RECHECK_PENDING", published
    assert published["stale"] is False, published
    assert published["can_preview"] is True, published
    assert published["can_apply"] is True, published


def _assert_preview_publishes_reviewed() -> None:
    state = bpy.context.window_manager.alpha_material_separator_api
    settings = bpy.context.window_manager.alpha_material_separator_settings
    preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        preview_assignment_plan=True,
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        derived_conflict_policy=settings.derived_conflict_policy,
        selection_mode="REPLACE",
        enter_edit_mode=False,
    )
    assert preview == {"FINISHED"}, state.last_status_json
    published = _assert_published_matches_live_snapshot("previewed")
    assert published["reviewed"] is True, published
    assert published["state"] == "REVIEWED", published


def _assert_published_signature_applies_without_review_changed() -> None:
    """A consumer's Apply must behave exactly like the panel's Apply."""
    state = bpy.context.window_manager.alpha_material_separator_api
    settings = bpy.context.window_manager.alpha_material_separator_settings
    published = _published()
    assigned = bpy.ops.alpha_material_separator.assign_materials(
        expected_analysis_id=published["analysis_id"],
        expected_review_signature=published["expected_review_signature"],
        mixed_policy=settings.mixed_policy,
        suppressed_policy=settings.suppressed_policy,
        unsupported_policy=settings.unsupported_policy,
        derived_conflict_policy=settings.derived_conflict_policy,
    )
    assert assigned == {"FINISHED"}, state.last_status_json
    assert state.last_status_code != "REVIEW_CHANGED", state.last_status_json


def _assert_stale_publishes_no_action() -> None:
    """mark_dirty only invalidates an active report; give it one to invalidate.

    The prior step Applied, which clears the report (runtime.clear keeps only
    the completion banner). mark_dirty is a deliberate no-op without a report
    (nothing to invalidate), so this models the real STALE trigger: re-analyze,
    then change a setting before reviewing again.
    """
    analyzed = bpy.ops.alpha_material_separator.analyze()
    assert analyzed == {"FINISHED"}, analyzed
    runtime.mark_dirty("SETTINGS_CHANGED")
    published = _assert_published_matches_live_snapshot("stale")
    assert published["state"] == "STALE", published
    assert published["stale"] is True, published
    assert published["can_preview"] is False, published
    assert published["can_apply"] is False, published


def _assert_reading_is_free_of_side_effects() -> None:
    """Publication must never validate, rasterize, or read image pixels."""
    before = runtime.snapshot()
    for _ in range(5):
        _published()
    after = runtime.snapshot()
    assert before == after, (before, after)


def _assert_a_broken_snapshot_offers_nothing() -> None:
    original = workflow.snapshot

    def _raise(_context):
        raise RuntimeError("simulated snapshot failure")

    workflow.snapshot = _raise
    try:
        published = _published()
    finally:
        workflow.snapshot = original
    assert published == api_contract.degraded_workflow_payload(), published
    assert published["stale"] is True, published
    assert published["can_analyze"] is False, published


def run() -> None:
    # Earlier modules in run_all.py leave an analysis report referencing their
    # own (by-now-deleted) objects; reset transient state before asserting the
    # IDLE baseline so this module does not depend on run_all.py's ordering.
    bpy.ops.alpha_material_separator.clear_results(api_major=1)
    _clear_scene()
    image = _image("AMS_WORKFLOW_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_WORKFLOW_MATERIAL", image)
    object_ = _quad("AMS_WORKFLOW_QUAD", material)
    _assert_idle_offers_nothing_without_a_selection()
    _assert_analysis_publishes_an_actionable_plan(object_)
    _assert_reading_is_free_of_side_effects()
    _assert_recheck_pending_keeps_the_buttons_enabled(image)
    _assert_preview_publishes_reviewed()
    _assert_published_signature_applies_without_review_changed()
    _assert_a_broken_snapshot_offers_nothing()
    _assert_stale_publishes_no_action()
    _clear_scene()
    print("ALPHA_MATERIAL_SEPARATOR_PUBLISHED_WORKFLOW_TESTS_OK")
