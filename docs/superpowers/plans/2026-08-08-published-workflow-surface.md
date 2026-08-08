# Published workflow surface implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. `AGENTS.md` makes `executing-plans` the
> default for this repository; `subagent-driven-development` requires an
> explicit user request. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the workflow state the extension's own panel computes, so an
external panel can mirror Analyze/Preview/Apply gating without importing
extension internals or reimplementing a private severity table.

**Architecture:** `addon/api_contract.py` gains the published workflow payload
shape and a status severity table — both pure and unit-testable without `bpy`. A
new `addon/workflow.py` computes one live snapshot from Blender state; the panel
draws from it and a read-only `workflow_json` RNA getter serializes it, so drawn
and published state cannot drift.

**Tech Stack:** Blender 5.2 LTS Python API (`bpy.props.StringProperty(get=...)`,
`bpy.types.PropertyGroup`), standard-library `json` and `unittest`.

**Source spec:** `docs/superpowers/specs/2026-08-08-published-workflow-surface-design.md`

## Global Constraints

- Target Blender 5.2 LTS; manifest minimum is `5.2.0`.
- `GPL-3.0-or-later` SPDX header on every new source and test file.
- Public identity is `alpha_material_separator`; never `alpha_face_separator`.
- No new dependency, network access, telemetry, or external Python package.
- Analyze must not persistently change mesh, material, or image data, face
  selection, or topology. **Reading `workflow_json` must change nothing at all.**
- `main` is protected. Work stays on `fix/stale-analysis-privacy` and lands
  through a pull request. Do not push, tag, or merge without explicit approval.
- Never commit `.local-references/` contents or `.packaged-releases/` archives.
- Every production behavior change gets a failing generated test first.

## Deviations from the spec (accepted, recorded here for review)

1. **Four commits, not two.** The spec says "one branch, two commits." The
   scope is unchanged, but the contract shape (Task 1) is a pure, `bpy`-free
   change a reviewer can accept or reject independently of the Blender wiring
   (Task 2), and documentation lands once both halves exist (Task 4). Same
   branch, same objective, same `API_VERSION` bump.
2. **The published payload shape lives in `api_contract.py`, not `workflow.py`.**
   The spec puts `snapshot()` in `workflow.py`, which is correct, but
   `workflow.py` imports `bpy` transitively through `runtime`, so nothing in it
   is reachable from `tests/unit/`. `WORKFLOW_FIELDS`, `workflow_payload()`, and
   `degraded_workflow_payload()` are the *contract*, so `api_contract.py` is
   their proper home and makes spec testing layer 1 possible.
3. **`workflow.py` exposes four names, not one.** `snapshot(context)` is the
   public entry point. `build_plan` and `policy_signature` move there from
   `panel.py` (rather than being duplicated) because `workflow.py` cannot import
   `panel.py` without a cycle; `panel.py` imports them back. The Expert policy
   panel keeps working through the same two functions.
4. **The guidance-coupling test asserts a different invariant than the spec's
   wording.** The spec says "every key in `STATUS_SEVERITIES` returns real
   guidance." That is wrong on inspection: `OK`, `CLEARED`, `ANALYSIS_COMPLETE`,
   `PREVIEW_COMPLETE`, `ASSIGNMENT_COMPLETE`, `ASSIGNMENT_NO_CHANGES`, and
   `NOT_QUERIED` are success codes that deliberately have no remedy copy, and
   inventing entries for them would be noise. The invariant that actually closes
   the maintenance trap is the inverse: **no `OK`-severity code may carry
   `_GUIDANCE` copy.** Writing a user-facing remedy for a code you also mark as
   "nothing to see" is exactly the drift that hid the missing `RESULT_STALE`
   entry. `RESULT_STALE` itself is asserted directly.

---

### Task 1: Published workflow payload shape and API 1.3

The published field set, its degraded form, and the version bump. Pure Python,
no `bpy`, so `tests/unit/` can cover it.

**Files:**
- Modify: `addon/api_contract.py:12` (version), `:68-100` (capabilities), new
  module constants and two functions after `capability_payload()`
- Test: `tests/unit/test_api_contract.py`
- Modify: `tests/blender/run_all.py:62` (asserts the api version string)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces:
  - `api_contract.API_VERSION == (1, 3)`
  - `api_contract.WORKFLOW_FIELDS: tuple[str, ...]`
  - `api_contract.WORKFLOW_STATES: tuple[str, ...]`
  - `api_contract.workflow_payload(view: dict) -> dict[str, Any]`
  - `api_contract.degraded_workflow_payload() -> dict[str, Any]`
  - `capability_payload()["capabilities"]["published_workflow_state"] is True`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_api_contract.py`, inside `ApiContractTests`:

```python
    def test_workflow_payload_publishes_the_documented_field_set(self) -> None:
        view = {
            "state": "READY_TO_REVIEW",
            "can_analyze": True,
            "can_preview": True,
            "can_apply": True,
            "running": False,
            "stale": False,
            "reviewed": False,
            "actionable": True,
            "already_separated": False,
            "eligible_object_count": 2,
            "analysis_id": "abc123",
            "validation_state": "CLEAN",
            "expected_review_signature": "deadbeef",
            # Live objects the panel needs are never published.
            "plan": object(),
            "report": object(),
        }
        payload = api_contract.workflow_payload(view)
        self.assertEqual(
            set(payload),
            set(api_contract.WORKFLOW_FIELDS) | {"api_version"},
        )
        self.assertEqual(payload["api_version"], "1.3")
        self.assertEqual(payload["state"], "READY_TO_REVIEW")
        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["eligible_object_count"], 2)
        # Must survive the documented serializer.
        self.assertEqual(json.loads(api_contract.dumps(payload)), payload)

    def test_degraded_workflow_payload_offers_nothing(self) -> None:
        degraded = api_contract.degraded_workflow_payload()
        self.assertEqual(set(degraded), set(api_contract.WORKFLOW_FIELDS) | {"api_version"})
        self.assertTrue(degraded["stale"])
        self.assertFalse(degraded["can_analyze"])
        self.assertFalse(degraded["can_preview"])
        self.assertFalse(degraded["can_apply"])
        self.assertIn(degraded["state"], api_contract.WORKFLOW_STATES)

    def test_published_workflow_states_match_the_presentation_states(self) -> None:
        from addon.presentation import workflow_view

        produced = set()
        for arguments in (
            dict(eligible_objects=0),
            dict(eligible_objects=1),
            dict(eligible_objects=1, has_report=True, actionable=True),
            dict(eligible_objects=1, has_report=True, actionable=True, reviewed=True),
            dict(eligible_objects=1, has_report=True, actionable=False),
            dict(eligible_objects=1, has_report=True, stale=True),
            dict(eligible_objects=1, running=True),
            dict(eligible_objects=1, completed=True),
        ):
            defaults = dict(
                eligible_objects=0,
                running=False,
                has_report=False,
                stale=False,
                reviewed=False,
                actionable=False,
                completed=False,
            )
            produced.add(workflow_view(**(defaults | arguments))["state"])
        self.assertEqual(produced, set(api_contract.WORKFLOW_STATES))
```

Change the two existing version assertions in the same file:

```python
        self.assertEqual(payload["api_version"], "1.3")
```
```python
    def test_public_operator_ids_remain_api_1_compatible(self) -> None:
        self.assertEqual(api_contract.API_VERSION, (1, 3))
```

Rename that test as shown — it guards major-1 compatibility, not the 1.2 minor,
and leaving `1_2` in the name would misdate it at every future bump.

- [ ] **Step 2: Run the tests and verify they fail**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe' -m unittest tests.unit.test_api_contract -v
```

Expected: FAIL — `AttributeError: module 'addon.api_contract' has no attribute
'WORKFLOW_FIELDS'`, plus the two version assertions failing on `1.2 != 1.3`.

- [ ] **Step 3: Bump the version and add the contract**

In `addon/api_contract.py`, change line 12:

```python
API_VERSION = (1, 3)
```

Add after `VALIDATION_STATES` (line 50):

```python
# The published guided-workflow surface. WORKFLOW_FIELDS is the exact key set of
# `WindowManager.alpha_material_separator_api.workflow_json` minus api_version,
# so a consumer can validate a payload without version-sniffing.
WORKFLOW_STATES = (
    "IDLE",
    "READY_TO_ANALYZE",
    "READY_TO_REVIEW",
    "REVIEWED",
    "NO_CHANGE",
    "STALE",
    "RUNNING",
    "COMPLETED",
)
WORKFLOW_FIELDS = (
    "state",
    "can_analyze",
    "can_preview",
    "can_apply",
    "running",
    "stale",
    "reviewed",
    "actionable",
    "already_separated",
    "eligible_object_count",
    "analysis_id",
    "validation_state",
    "expected_review_signature",
)
```

Add after `capability_payload()` (line 100):

```python
def workflow_payload(view: dict[str, Any]) -> dict[str, Any]:
    """Project a live workflow snapshot onto the published field set.

    The snapshot the panel draws from also carries live Blender objects. Only
    the JSON-compatible fields listed in WORKFLOW_FIELDS are published.
    """
    payload: dict[str, Any] = {"api_version": dotted(API_VERSION)}
    payload.update({name: view[name] for name in WORKFLOW_FIELDS})
    return payload


def degraded_workflow_payload() -> dict[str, Any]:
    """Offer no operation when the live snapshot could not be computed.

    A get= callback runs during panel draw and must never raise, so an
    unexpected failure publishes a payload that gates every action off rather
    than an optimistic or absent one.
    """
    return workflow_payload(
        {
            "state": "STALE",
            "can_analyze": False,
            "can_preview": False,
            "can_apply": False,
            "running": False,
            "stale": True,
            "reviewed": False,
            "actionable": False,
            "already_separated": False,
            "eligible_object_count": 0,
            "analysis_id": "",
            "validation_state": "STALE",
            "expected_review_signature": "",
        }
    )
```

Add one line inside the `capabilities` dict in `capability_payload()`,
immediately after `"plan_derived_preview": True,`:

```python
            "published_workflow_state": True,
```

- [ ] **Step 4: Run the tests and verify they pass**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe' -m unittest discover -s tests/unit -t . -v
```

Expected: PASS. `tests/unit/test_presentation.py` must still pass untouched.

- [ ] **Step 5: Update the headless capability assertion**

`tests/blender/run_all.py:62`:

```python
    assert capabilities["api_version"] == "1.3", capabilities
```

Add below the `plan_derived_preview` assertion in the same function:

```python
    assert capabilities["capabilities"]["published_workflow_state"] is True
```

- [ ] **Step 6: Run the headless suite**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [ ] **Step 7: Commit**

```bash
git add addon/api_contract.py tests/unit/test_api_contract.py tests/blender/run_all.py && git commit -F - <<'EOF'
feat: publish the workflow payload shape at API 1.3

WORKFLOW_FIELDS is the exact published key set, workflow_payload projects a
live snapshot onto it, and degraded_workflow_payload gates every action off
when that snapshot cannot be computed. Both are pure so tests/unit covers
them. capability_payload gains published_workflow_state so a consumer can
feature-detect instead of parsing versions.

The minor bumps because the published surface gained a field.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Shared snapshot module, panel refactor, and `workflow_json`

One computation, two consumers. The panel keeps drawing exactly what it draws
today; the RNA getter serializes the same values.

**Files:**
- Create: `addon/workflow.py`
- Create: `tests/blender/test_published_workflow.py`
- Modify: `addon/panel.py:14-24` (imports), `:27-32` (`_json` removal),
  `:87-107` (`_policy_signature`/`_plan` removal), `:275-323` (draw block),
  `:582-584` (signature reuse), `:721` (Expert policy panel)
- Modify: `addon/presentation.py` (add `json_object`)
- Modify: `addon/properties.py:34-49` (the api state group)
- Modify: `addon/runtime.py:44-48` (comment correction)
- Modify: `tests/blender/run_all.py` (register the new test module)

**Interfaces:**
- Consumes: `api_contract.workflow_payload`, `api_contract.degraded_workflow_payload`,
  `api_contract.dumps` from Task 1.
- Produces:
  - `presentation.json_object(value: str) -> dict`
  - `workflow.build_plan(report, settings) -> AssignmentPlan | None`
  - `workflow.policy_signature(state, settings, plan_payload: dict | None = None) -> str`
  - `workflow.snapshot(context) -> dict` — every key in
    `api_contract.WORKFLOW_FIELDS`, plus the live keys `eligible_objects`
    (`tuple[bpy.types.Object, ...]`), `report` (`AnalysisReport | None`),
    `plan` (`AssignmentPlan | None`), `plan_payload` (`dict`), and
    `no_change_tooltip` (`str`).
  - `WindowManager.alpha_material_separator_api.workflow_json` — read-only JSON
    string.

- [ ] **Step 1: Write the failing headless test**

Create `tests/blender/test_published_workflow.py`:

```python
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
    _clear_scene()
    image = _image()
    object_ = _quad(_material(image))
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
```

Register it in `tests/blender/run_all.py` — add the import beside the others:

```python
from tests.blender.test_published_workflow import (  # noqa: E402
    run as run_published_workflow_tests,
)
```

and the call inside `if iteration == 0:`, after `run_integration_contract_tests()`:

```python
            run_published_workflow_tests()
```

**Note for the implementer:** `_image`, `_material`, `_quad`, and `_clear_scene`
are the existing fixture helpers in `tests/blender/test_analysis_preview.py`.
Confirm `_quad`'s signature before running — if it takes no material argument,
build the object the way `test_analysis_preview.py` does in its own `run()` and
keep the rest of this test unchanged.

- [ ] **Step 2: Run the headless suite and verify it fails**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL — `ModuleNotFoundError: No module named 'addon.workflow'`.

- [ ] **Step 3: Add the shared JSON parser to `presentation.py`**

`addon/panel.py`'s private `_json` is needed by `workflow.py`, which cannot
import `panel.py` without a cycle. Move it to the pure module.

Add to `addon/presentation.py`, after the imports:

```python
def json_object(value: str) -> dict:
    """Parse a published JSON string, treating anything unusable as empty."""
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}
```

- [ ] **Step 4: Create `addon/workflow.py`**

```python
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
    signature = policy_signature(state, settings, plan_payload)
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
```

- [ ] **Step 5: Add the read-only `workflow_json` property**

In `addon/properties.py`, add above the property group:

```python
def _workflow_json(_self) -> str:
    # Imported lazily inside the getter, matching _settings_changed above: the
    # workflow module reaches adapters.assignment, which must not be imported
    # while this module is being defined.
    from . import api_contract, workflow

    try:
        payload = api_contract.workflow_payload(workflow.snapshot(bpy.context))
    except Exception:  # noqa: BLE001
        # A get= callback runs during panel draw. Raising here would break the
        # panel that reads it, so an unexpected failure offers no operation.
        payload = api_contract.degraded_workflow_payload()
    return api_contract.dumps(payload)
```

and add the property to `ALPHA_MATERIAL_SEPARATOR_PG_api_state`, after
`pending_scopes_json`:

```python
    workflow_json: StringProperty(
        name="Workflow State",
        description="Read-only published Analyze, Preview, and Apply gating",
        get=_workflow_json,
    )
```

- [ ] **Step 6: Refactor `panel.py` to draw from the snapshot**

Replace the import block at `addon/panel.py:10-24`:

```python
from . import runtime, workflow
from .manifest import issues_url, maintainer_name, version_tuple
from .overrides import dumps_material_overrides
from .presentation import (
    CLASS_COPY,
    alpha_source_advisory,
    classes_to_move,
    guidance_for,
    json_object,
    review_material_cards,
    ui_text_lines,
)
```

`import json` at the top of the file becomes unused once `_json` is gone —
delete it. `already_separated_tooltip`, `review_signature`, `workflow_view`, and
`build_assignment_plan` are no longer imported here either; they are reached
through `workflow.py`.

Delete `_json` (lines 27-32), `_policy_signature` (87-95), and `_plan` (98-107).
Replace every remaining `_json(` call in the file with `json_object(`, and both
`_plan(` call sites with `workflow.build_plan(`.

Replace the computation block at the top of
`ALPHA_MATERIAL_SEPARATOR_PT_main.draw` (lines 283-323) with:

```python
        view = workflow.snapshot(context)
        eligible = view["eligible_objects"]
        material_overrides_json, invalid_overrides = _override_payload(settings)
        current_report = view["report"]
        report_payload = json_object(state.report_json) if current_report else {}
        stale = view["stale"]
        current_plan = view["plan"]
        plan_payload = view["plan_payload"]
        reviewed = view["reviewed"]
        actionable = view["actionable"]
        no_change_tooltip = view["no_change_tooltip"]
        already_separated = view["already_separated"]
```

Everything below that line is unchanged except line 582-584, which reuses the
signature the snapshot already computed:

```python
            assign.expected_review_signature = view["expected_review_signature"]
```

`ALPHA_MATERIAL_SEPARATOR_PT_policies` (line 721) becomes:

```python
        current_plan = workflow.build_plan(runtime.report(state.analysis_id), settings)
```

- [ ] **Step 7: Correct the overclaiming comment in `runtime.py`**

`addon/runtime.py:45-47` currently claims more than the guard delivers. Replace
the comment body with:

```python
            # Published here, not at each call site, so every current and
            # future confirmed-stale transition carries a status. RECHECK_PENDING
            # deliberately publishes nothing: a depsgraph hint is not proof of
            # staleness, and the panel gates on dirty_reason() for the same
            # reason. A consumer reads workflow_json or both last_status_code
            # and validation_state; neither field alone is sufficient.
```

- [ ] **Step 8: Run the headless suite and verify it passes**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: `ALPHA_MATERIAL_SEPARATOR_PUBLISHED_WORKFLOW_TESTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [ ] **Step 9: Run the unit suite and validate the source**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe' -m unittest discover -s tests/unit -t . -v
```

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --command extension validate addon
```

Expected: both pass. `test_core_import_does_not_require_bpy` must still pass —
if it fails, something imported `addon.workflow` from a pure module.

- [ ] **Step 10: Commit**

```bash
git add addon/workflow.py addon/panel.py addon/presentation.py addon/properties.py addon/runtime.py tests/blender/test_published_workflow.py tests/blender/run_all.py && git commit -F - <<'EOF'
feat: publish the workflow state the panel draws

The panel computed Analyze/Preview/Apply gating inline and discarded it after
drawing, so an external panel had to guess. addon/workflow.py now holds that
one computation; the panel draws from it and a read-only workflow_json RNA
getter publishes it, so the two cannot drift.

The getter is total: an unexpected failure publishes the degraded payload
rather than raising during draw.

A permanent regression asserts that RECHECK_PENDING keeps can_preview and
can_apply true, so the runtime publish guard cannot be widened without
failing a test, and that repeated reads leave runtime.snapshot() identical.

Corrects the comment on that guard, which claimed more than it delivers.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Status severity and the missing `RESULT_STALE` guidance

`_draw_status_problem`'s private `normal` set is a severity table that consumers
reimplement by hand and already diverge from. Publish it.

**Files:**
- Modify: `addon/api_contract.py` (severity table, `severity_for`, `status_payload`)
- Modify: `addon/panel.py:175-188` (`_draw_status_problem`)
- Modify: `addon/presentation.py` (`_GUIDANCE` gains `RESULT_STALE`)
- Test: `tests/unit/test_api_contract.py`, `tests/unit/test_presentation.py`

**Interfaces:**
- Consumes: `api_contract.API_VERSION == (1, 3)` from Task 1.
- Produces:
  - `api_contract.STATUS_SEVERITIES: dict[str, str]`
  - `api_contract.severity_for(code: str) -> str` — `"OK"`, `"INFO"`, or `"ERROR"`
  - every `status_payload()` result carries `"severity"`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_api_contract.py`:

```python
    def test_severity_is_published_and_closed_world(self) -> None:
        self.assertEqual(api_contract.severity_for("ANALYSIS_COMPLETE"), "OK")
        self.assertEqual(api_contract.severity_for("RESULT_STALE"), "INFO")
        self.assertEqual(
            api_contract.severity_for("ASSIGNMENT_COMPLETE_WITH_SKIPS"), "INFO"
        )
        # An unlisted code is an error, reproducing the panel's previous
        # closed-world `normal` set exactly.
        self.assertEqual(api_contract.severity_for("STALE_ANALYSIS"), "ERROR")
        self.assertEqual(api_contract.severity_for("ASSIGNMENT_BLOCKED"), "ERROR")
        self.assertEqual(api_contract.severity_for("A_CODE_ADDED_LATER"), "ERROR")

    def test_the_severity_table_reproduces_the_panels_previous_normal_set(self) -> None:
        """These nine codes rendered no alert box before severity existed."""
        previously_normal = {
            "NOT_QUERIED",
            "OK",
            "ANALYSIS_COMPLETE",
            "PREVIEW_COMPLETE",
            "ASSIGNMENT_COMPLETE",
            "ASSIGNMENT_COMPLETE_WITH_SKIPS",
            "ASSIGNMENT_NO_CHANGES",
            "CLEARED",
            "RESULT_STALE",
        }
        self.assertEqual(set(api_contract.STATUS_SEVERITIES), previously_normal)
        for code in previously_normal:
            with self.subTest(code=code):
                self.assertIn(api_contract.severity_for(code), {"OK", "INFO"})

    def test_every_status_payload_carries_its_severity(self) -> None:
        self.assertEqual(api_contract.status_payload("OK", "done")["severity"], "OK")
        self.assertEqual(
            api_contract.status_payload("ASSIGNMENT_BLOCKED", "no")["severity"],
            "ERROR",
        )
```

Change the serialization assertion in `test_status_json_uses_stable_sorting`:

```python
        self.assertEqual(
            encoded,
            '{"a_value":2,"api_version":"1.3","code":"OK","message":"done",'
            '"severity":"OK","z_value":1}',
        )
```

Add to `tests/unit/test_presentation.py` (import `guidance_for` and
`KNOWN_GUIDANCE_CODES` from `addon.presentation` and `api_contract` at the top
of the file if they are not already imported):

```python
    def test_stale_results_have_real_guidance(self) -> None:
        title, remedy = guidance_for("RESULT_STALE")
        self.assertEqual(title, "Inputs Changed — Analyze Again")
        self.assertNotEqual(title, guidance_for("A_CODE_WITH_NO_ENTRY")[0])
        self.assertTrue(remedy)

    def test_no_silent_status_code_carries_user_facing_guidance(self) -> None:
        """A code with remedy copy must never be classified as nothing to see.

        Marking a code OK suppresses its alert box entirely. Writing guidance
        for such a code is the drift that hid the missing RESULT_STALE entry,
        so the two tables are coupled here.
        """
        from addon.api_contract import STATUS_SEVERITIES, severity_for

        silent = {code for code in STATUS_SEVERITIES if severity_for(code) == "OK"}
        self.assertEqual(silent & KNOWN_GUIDANCE_CODES, set())
```

- [ ] **Step 2: Run the tests and verify they fail**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe' -m unittest tests.unit.test_api_contract tests.unit.test_presentation -v
```

Expected: FAIL — no `severity_for`, and `guidance_for("RESULT_STALE")` returns
the unknown-code default `"This input needs review"`.

- [ ] **Step 3: Add the severity table**

In `addon/api_contract.py`, after `VALIDATION_STATES`:

```python
# Published so a consumer does not reimplement the panel's private set by hand.
# Only non-error codes are listed; an unlisted code is an error, which keeps the
# world closed exactly as the panel's previous `normal` set did. There is no
# WARNING level because no current code needs one.
STATUS_SEVERITIES = {
    "NOT_QUERIED": "OK",
    "OK": "OK",
    "ANALYSIS_COMPLETE": "OK",
    "PREVIEW_COMPLETE": "OK",
    "ASSIGNMENT_COMPLETE": "OK",
    "ASSIGNMENT_NO_CHANGES": "OK",
    "CLEARED": "OK",
    "ASSIGNMENT_COMPLETE_WITH_SKIPS": "INFO",
    "RESULT_STALE": "INFO",
}
DEFAULT_STATUS_SEVERITY = "ERROR"


def severity_for(code: str) -> str:
    """Classify a public status code. Unknown codes are errors."""
    return STATUS_SEVERITIES.get(code, DEFAULT_STATUS_SEVERITY)
```

`severity_for` is defined before `status_payload` uses it; place the block above
`def dotted(...)` or keep the constants there and the function immediately after
`dotted`. Either ordering works — the module has no import-time evaluation of it.

Then in `status_payload`:

```python
    payload: dict[str, Any] = {
        "api_version": dotted(API_VERSION),
        "code": code,
        "message": message,
        "severity": severity_for(code),
    }
```

- [ ] **Step 4: Add the `RESULT_STALE` guidance entry**

In `addon/presentation.py`, add to `_GUIDANCE` beside `STALE_ANALYSIS`:

```python
    "RESULT_STALE": (
        "Inputs Changed — Analyze Again",
        "Analyze again before previewing or applying.",
    ),
```

The title deliberately repeats the panel's own Review-box wording so the
machine-facing copy and the user-facing copy cannot disagree.

- [ ] **Step 5: Rewire the panel to the published table**

`addon/panel.py`, replace lines 175-188:

```python
def _draw_status_problem(layout, state, *, available_width: int) -> None:
    if severity_for(state.last_status_code) in {"OK", "INFO"}:
        return
    payload = json_object(state.last_status_json)
```

`panel.py` does not import `api_contract` today, so add the import beside the
other relative imports:

```python
from .api_contract import severity_for
```

- [ ] **Step 6: Run the tests and verify they pass**

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe' -m unittest discover -s tests/unit -t . -v
```

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: both pass. The headless suite exercises many status codes; a failure
here means a code that previously rendered nothing now renders an alert box.

- [ ] **Step 7: Commit**

```bash
git add addon/api_contract.py addon/panel.py addon/presentation.py tests/unit/test_api_contract.py tests/unit/test_presentation.py && git commit -F - <<'EOF'
feat: publish status severity and fix stale-result guidance

_draw_status_problem's private `normal` set was a severity table consumers
reimplemented by hand and already diverged from. STATUS_SEVERITIES publishes
it, every status payload carries its severity, and the panel reads the same
table, so rendering is unchanged for every existing code.

RESULT_STALE had no _GUIDANCE entry and fell back to the unknown-code
default. That was invisible only because the panel returned early for it. It
now reuses the Review box's own wording, and a unit test asserts no
OK-severity code carries user-facing guidance, coupling the two tables.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

---

### Task 4: Documentation, performance check, and branch completion

**Files:**
- Modify: `docs/integration-api.md`
- Modify: `docs/testing.md:30`
- Modify: `docs/HANDOFF.md`
- Delete: `docs/superpowers/specs/2026-08-08-published-workflow-surface-design.md`
- Delete: `docs/superpowers/plans/2026-08-08-published-workflow-surface.md`

**Interfaces:** consumes everything above; produces no code.

- [ ] **Step 1: Update `docs/integration-api.md`**

Change the header (lines 3-6):

```markdown
- API version: `1.3`
- Extension version: see `version` in `addon/blender_manifest.toml`

API 1.3 is additive over 1.2. Existing API 1.0/1.1/1.2 callers keep the same
operator IDs, existing arguments, scripted defaults, and classifications.
```

Add a `## Versioning` section immediately after that paragraph:

```markdown
## Versioning

The API minor bumps whenever the published surface gains a field, property,
status code, or operator. `extension_version`, published both as
`capability_payload()["extension_version"]` and as
`WindowManager.alpha_material_separator_api.extension_version`, distinguishes
builds within one minor and is derived from `addon/blender_manifest.toml`.

Under this policy the `RESULT_STALE` status code added in 1.2.0 should have
bumped the minor and did not. A consumer that must distinguish 1.2.0 from an
earlier 1.2 build compares `extension_version` tuples after running
`query_capabilities`:

```python
bpy.ops.alpha_material_separator.query_capabilities(requested_api_major=1)
state = bpy.context.window_manager.alpha_material_separator_api
capabilities = json.loads(state.capabilities_json)
version = tuple(int(part) for part in capabilities["extension_version"].split("."))
supported = version >= (1, 2, 0)
```

Prefer a capability flag over a version comparison where one exists.
`published_workflow_state` covers the workflow surface below.
```

Add a `## Workflow state` section after "Status and report data":

```markdown
## Workflow state

`workflow_json` is a read-only computed property. Each read recomputes from
current Blender state, because two of its inputs — the selected objects and the
four policy enums — change with no extension operator running, which is exactly
when Preview and Apply become available or unavailable. It carries:

| Field | Meaning |
| --- | --- |
| `state` | `IDLE`, `READY_TO_ANALYZE`, `READY_TO_REVIEW`, `REVIEWED`, `NO_CHANGE`, `STALE`, `RUNNING`, or `COMPLETED`. |
| `can_analyze`, `can_preview`, `can_apply` | Exactly what the extension's own buttons enable. |
| `running` | An analysis is in progress. |
| `stale` | Confirmed stale. `RECHECK_PENDING` is not stale and leaves the gating booleans true. |
| `reviewed` | The current exact plan has been previewed. |
| `actionable` | The plan would change at least one face or metadata record. |
| `already_separated` | Nothing left to move; report "no change needed" rather than only greying buttons. |
| `eligible_object_count` | Disambiguates the two causes of `can_analyze: false`. |
| `analysis_id`, `validation_state` | Match the same-named properties. |
| `expected_review_signature` | Pass unchanged to `assign_materials`. |

Passing `expected_review_signature` is what gives an external Apply the same
`REVIEW_CHANGED` protection and not-previewed confirmation the guided panel
gets. Omitting it, or passing an empty string, reads as *already previewed* and
silently drops both.

If the snapshot cannot be computed, the property publishes `stale: true` with
every `can_*` false rather than raising, because the getter runs during panel
draw.
```

Add to the "Status and report data" bullet list:

```markdown
- `workflow_json`
```

Add a `severity` paragraph after the assignment status table:

```markdown
Every payload in `last_status_json` carries `severity`: `OK`, `INFO`, or
`ERROR`. The extension's own panel renders an alert box for `ERROR` only. A code
absent from the published table is an `ERROR`, so a consumer written against
this document stays correct when a later release adds one.
```

- [ ] **Step 2: Update `docs/testing.md`**

Line 30 reads `coverage/classification and API 1.2 capability JSON`. That
paragraph is prose, not a list. Change the version and name the new coverage in
the same sentence flow:

```markdown
coverage/classification and API 1.3 capability JSON, registration/unregistration,
Simple and Expert workflow state, the published workflow surface and its
RECHECK_PENDING gating, per-material overrides, analysis progress and
```

Leave the rest of the paragraph untouched.

- [ ] **Step 3: Measure the redraw path**

The snapshot adds one plan build per consumer read. Measure before claiming it
is free:

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --python-exit-code 1 --python tests/blender/run_benchmarks.py -- --output .test-output/benchmarks/workflow-surface.json
```

Run one discarded warm-up and five measured runs on this branch, then the same
on `main` in the same session on the same machine. Block an unexplained
regression over 25 percent. No baseline persists between sessions, so do not
claim a cross-session comparison. If the redraw path regresses, implement the
memo described in the `ponytail:` comment in `addon/workflow.py` rather than
weakening a test.

- [ ] **Step 4: Rebuild and validate the archive**

Installable behavior changed — a new RNA property is registered — so the archive
gate applies:

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
```

Clear `.packaged-releases` first; ordinary validation must discover exactly one
AMS ZIP. Then validate the archive by its discovered path, never by a filename
derived from a version number.

- [ ] **Step 5: Review the whole branch diff**

```bash
git diff main...HEAD --stat && git diff --check
```

Check for accidental scope expansion. The `default_planned_action` defect,
manual alpha source usability, and the two missing PEP 8 blank lines in
`runtime.py` are explicitly out of scope and must not appear.

- [ ] **Step 6: Update `docs/HANDOFF.md` and remove the in-flight documents**

Record the branch's purpose, the four-of-six investigation verdict, what shipped,
the validation actually performed, and what remains user-gated: installed-ZIP
interactive acceptance of an external panel gating against a real build. Move
the "In flight" section to completed.

`AGENTS.md` requires deleting the spec and this plan from `main` once the
milestone is complete and committed; git history keeps the approved wording
recoverable.

```bash
git rm docs/superpowers/specs/2026-08-08-published-workflow-surface-design.md docs/superpowers/plans/2026-08-08-published-workflow-surface.md
```

- [ ] **Step 7: Commit**

```bash
git add docs/integration-api.md docs/testing.md docs/HANDOFF.md && git commit -F - <<'EOF'
docs: document the API 1.3 workflow surface and version policy

States the minor-bump policy, records plainly that 1.2.0's RESULT_STALE
should have bumped the minor and did not, and gives the extension_version
comparison a consumer needs for builds already released.

Documents workflow_json field by field, why it is computed on each read, and
that passing expected_review_signature is what gives an external Apply the
same REVIEW_CHANGED protection the guided panel has.

Removes the completed spec and plan; git history retains them.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
```

- [ ] **Step 8: Report the branch as ready for review**

State which gates ran and their results, and name the unconfirmed interactive
item explicitly rather than implying it passed. Do not push, open a pull
request, tag, or merge without explicit user approval.

---

## Validation summary

Every task's gate, in the order the change gate requires:

| Layer | Command |
| --- | --- |
| Unit | `& $Python52 -m unittest discover -s tests/unit -t . -v` |
| Headless Blender | `& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py` |
| Source validation | `& $Blender52 --factory-startup --command extension validate addon` |
| Archive | build into a cleared `.packaged-releases`, then validate the discovered ZIP |
| Performance | `tests/blender/run_benchmarks.py`, before/after in one session |
| Whitespace | `git diff --check` |

Not run, and not claimable: installed-ZIP interactive acceptance in a clean
Blender 5.2 configuration, and the `.local-references/` before/after smoke. The
private smoke is not required here — this change does not alter material
resolution, rasterization, classification, cache validity, preview plans,
assignment plans, or mutation safety. It publishes state those paths already
compute.
