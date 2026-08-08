# Integration Contract Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct six verified defects in the public integration surface so an
integrator that trusts the published contract cannot be misled by it.

**Architecture:** Five of the six are corrections inside existing modules, not
new components. The published address-mode list stops contradicting its own
documentation, the seven analysis setting names move to the module `api_major`
guards, three legacy operator properties gain `SKIP_SAVE` so the panel stops
resetting them per draw, the modal cancel path publishes before it tags a
redraw, and every stale transition publishes a `RESULT_STALE` status so no
consumer has to read two fields to learn one fact. The sixth is a missing test:
panel-built overrides are asserted through classification counts rather than by
inspecting the panel.

**Tech Stack:** Blender 5.2 LTS `bpy`, Python 3.13 standard library, `unittest`
for pure tests, plain assertion modules for headless Blender tests.

## Global Constraints

- `API_VERSION` stays `(1, 2)`. Correcting `address_modes` restores documented
  1.2 behavior; it is not an additive 1.3 feature. Approved by the user.
- `addon/api_contract.py` and `addon/core/` stay free of `bpy` imports.
  `tests/unit/test_api_contract.py::test_core_import_does_not_require_bpy`
  enforces this and must keep passing.
- `addon/blender_manifest.toml` is not touched. This branch ships no release.
- `alpha_material_separator.reset_analysis_settings` stays `INTERNAL` and stays
  out of `PUBLIC_OPERATOR_IDS`. Promoting it would create a contract obligation
  that does not exist today.
- Every new file carries `# SPDX-License-Identifier: GPL-3.0-or-later`.
- No new dependency, no network, no telemetry.
- Public identity is `alpha_material_separator`.

## File Structure

| File | Responsibility after this plan |
| --- | --- |
| `addon/api_contract.py` | Publishes the accepted address-mode set unfiltered; owns `ANALYSIS_SETTING_NAMES` as the guarded public surface. |
| `addon/properties.py` | Re-exports `ANALYSIS_SETTING_NAMES` from `api_contract` so existing importers keep working. |
| `addon/operators/analyze.py` | Legacy per-call fields carry `SKIP_SAVE`; the modal cancel path publishes its status before tearing down. |
| `addon/panel.py` | Stops resetting the three legacy fields on every draw. |
| `addon/runtime.py` | Publishes `RESULT_STALE` from the single place every stale transition already funnels through. |
| `docs/integration-api.md` | Documents the corrected address-mode list, `RESULT_STALE`, and the guarded setting names. |
| `tests/unit/test_api_contract.py` | Pins the corrected payload and proves every published mode is parser-accepted. |
| `tests/blender/test_expert_analysis_settings.py` | Guards the seven names against the real operator RNA. |
| `tests/blender/test_integration_contract.py` | **New.** `SKIP_SAVE` options, cancel-path ordering, and `RESULT_STALE` transitions. |
| `tests/blender/test_ux_overrides.py` | Adds the panel-built override count assertions. |
| `tests/blender/run_all.py` | Registers the new module and its marker. |

---

### Task 1: Publish the address modes the parser actually accepts

Fixes review item 2. `addon/api_contract.py:32` strips `AUTO`, but
`parse_material_overrides_json` accepts it, `docs/integration-api.md:34`
documents it, and it is the `MaterialOverride.address_mode` default every
override starts at. An integrator validating against the published list would
reject its own defaults.

**Files:**
- Modify: `addon/api_contract.py:32`
- Modify: `docs/integration-api.md`
- Test: `tests/unit/test_api_contract.py:56-59`

**Interfaces:**
- Consumes: `addon.overrides.ADDRESS_MODES`, already imported as
  `OVERRIDE_ADDRESS_MODES`.
- Produces: `api_contract.ADDRESS_MODES == overrides.ADDRESS_MODES`, a 5-tuple
  including `"AUTO"`. `capability_payload()["address_modes"]` is its list form.

- [ ] **Step 1: Replace the pinned assertion with the corrected contract**

In `tests/unit/test_api_contract.py`, replace the existing block at lines 56-59:

```python
        self.assertEqual(
            payload["address_modes"],
            [mode for mode in OVERRIDE_ADDRESS_MODES if mode != "AUTO"],
        )
```

with:

```python
        self.assertEqual(payload["address_modes"], list(OVERRIDE_ADDRESS_MODES))
        self.assertIn("AUTO", payload["address_modes"])
```

- [ ] **Step 2: Add a test proving every published mode is accepted**

Add this method to `ApiContractTests` in `tests/unit/test_api_contract.py`:

```python
    def test_every_published_address_mode_is_accepted_by_the_parser(self) -> None:
        published = api_contract.capability_payload()["address_modes"]
        for mode in published:
            with self.subTest(mode=mode):
                parsed = parse_material_overrides_json(
                    json.dumps(
                        [{"material_name": "Body", "address_mode": mode}]
                    )
                )
                self.assertEqual(parsed[0].address_mode, mode)

    def test_the_override_default_is_published_as_valid(self) -> None:
        default = MaterialOverride(material_name="Body").address_mode
        self.assertIn(default, api_contract.capability_payload()["address_modes"])
```

Extend the import at line 13 so both names are available:

```python
from addon.overrides import (
    ADDRESS_MODES as OVERRIDE_ADDRESS_MODES,
    MaterialOverride,
    parse_material_overrides_json,
)
```

- [ ] **Step 3: Run the tests to verify they fail**

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_api_contract -v
```

Expected: `test_capability_payload_is_deterministic_and_conservative` fails on
the address-mode list, and `test_the_override_default_is_published_as_valid`
fails with `'AUTO' not found in ['REPEAT', 'EXTEND', 'CLIP', 'MIRROR']`.
`test_every_published_address_mode_is_accepted_by_the_parser` passes already —
it is a guard against the inverse regression, so record that it passed at RED
rather than treating it as proof.

- [ ] **Step 4: Correct the published list**

In `addon/api_contract.py`, replace line 32:

```python
ADDRESS_MODES = tuple(mode for mode in OVERRIDE_ADDRESS_MODES if mode != "AUTO")
```

with:

```python
# Published unfiltered: AUTO is parser-accepted, documented since API 1.2, and
# the default every override starts at. A resolved report never reports AUTO.
ADDRESS_MODES = OVERRIDE_ADDRESS_MODES
```

- [ ] **Step 5: Run the tests to verify they pass**

```powershell
& $Python52 -m unittest tests.unit.test_api_contract -v
```

Expected: PASS.

- [ ] **Step 6: Document the distinction**

In `docs/integration-api.md`, immediately after the paragraph ending
"Invalid, duplicate, or unused records are rejected instead of ignored."
(line 38), add:

```markdown
`capability_payload()["address_modes"]` publishes the addressing values
`material_overrides_json` accepts, including `AUTO`, which is the default every
override record starts at. A resolved `groups[].address_mode` in a report is
always a concrete mode: `AUTO` means "use the resolved Image Texture setting" on
input, and an explicit image override resolves it to `REPEAT`. Builds before this
correction published the list without `AUTO`, which contradicted this section.
```

- [ ] **Step 7: Commit**

```bash
git add addon/api_contract.py docs/integration-api.md tests/unit/test_api_contract.py
git commit -m "fix: publish the address modes the override parser accepts"
```

---

### Task 2: Guard the seven analysis setting names in api_contract

Fixes review item 6. The seven names are keyword arguments every scripted caller
of `analyze` passes, but the tuple lives in `addon/properties.py`, outside
anything `api_major` guards. Renaming one inside major 1 would break callers
silently.

**Files:**
- Modify: `addon/api_contract.py`
- Modify: `addon/properties.py:112-120`
- Test: `tests/blender/test_expert_analysis_settings.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `api_contract.ANALYSIS_SETTING_NAMES`, a 7-tuple of `str`:
  `("alpha_threshold", "min_affected_texels", "min_affected_fraction",
  "margin_texels", "max_scanlines", "max_run_emissions", "address_mode")`.
  `properties.ANALYSIS_SETTING_NAMES` remains importable as the same object, so
  `addon/operators/ui_actions.py` and existing tests need no edit.

**Note before starting:** read the current tuple in `addon/properties.py` and
copy its exact members and order. The order above is the expected content, but
the file is authoritative; if it differs, the file wins and the deviation goes in
the commit message.

- [ ] **Step 1: Write the failing test**

Add to `tests/blender/test_expert_analysis_settings.py`:

```python
def _assert_public_setting_names_are_guarded() -> None:
    """Every guarded name must exist on the real analyze operator RNA."""

    from addon import api_contract
    from addon.properties import ANALYSIS_SETTING_NAMES as PANEL_NAMES

    assert api_contract.ANALYSIS_SETTING_NAMES == PANEL_NAMES, (
        api_contract.ANALYSIS_SETTING_NAMES,
        PANEL_NAMES,
    )
    properties = bpy.ops.alpha_material_separator.analyze.get_rna_type().properties
    missing = [
        name for name in api_contract.ANALYSIS_SETTING_NAMES if name not in properties
    ]
    assert not missing, missing
```

Call it as the first statement inside the existing `run()` in that file.

- [ ] **Step 2: Run it to verify it fails**

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: FAIL with `AttributeError: module 'addon.api_contract' has no
attribute 'ANALYSIS_SETTING_NAMES'`.

- [ ] **Step 3: Move the tuple into api_contract**

In `addon/api_contract.py`, after the `CLASSIFICATIONS` tuple, add:

```python
# Public: these are analyze() keyword arguments. Renaming one inside API major 1
# breaks scripted callers silently, so the names are guarded here rather than in
# the panel module that happens to draw them.
ANALYSIS_SETTING_NAMES = (
    "alpha_threshold",
    "min_affected_texels",
    "min_affected_fraction",
    "margin_texels",
    "max_scanlines",
    "max_run_emissions",
    "address_mode",
)
```

- [ ] **Step 4: Re-export from properties**

In `addon/properties.py`, delete the local `ANALYSIS_SETTING_NAMES = (...)`
definition and add to the imports near line 17:

```python
from .api_contract import ANALYSIS_SETTING_NAMES  # re-exported for panel and operators
from .overrides import ADDRESS_MODE_ITEMS, CHANNEL_ITEMS
```

Importers are unaffected: `addon/operators/ui_actions.py:10` and
`tests/blender/test_expert_analysis_settings.py:9` both do
`from ..properties import ANALYSIS_SETTING_NAMES` and keep working through the
re-export, so neither file is edited. Confirm no import cycle: `api_contract`
imports only `manifest` and `overrides`, and neither imports `properties`.

- [ ] **Step 5: Run the suites to verify they pass**

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: both PASS. `tests/blender/test_expert_analysis_settings.py` still
imports the name from `addon.properties` and must keep working through the
re-export.

- [ ] **Step 6: Commit**

```bash
git add addon/api_contract.py addon/properties.py tests/blender/test_expert_analysis_settings.py
git commit -m "refactor: guard the public analysis setting names in api_contract"
```

---

### Task 3: Stop legacy analyze arguments leaking between invocations

Fixes review item 3. Blender persists operator properties between invocations,
so `image_name`, `uv_map_name`, and `image_channel` carry a previous run's values
into the next one. That is the only reason
`addon/panel.py:77-79` resets three fields on every draw. Fixing it in the
operator fixes the whole class for every integrator instead of each one
reimplementing the reset.

`SKIP_SAVE` does not affect explicitly passed keyword arguments, so no scripted
caller changes behavior.

**Files:**
- Create: `tests/blender/test_integration_contract.py`
- Modify: `addon/operators/analyze.py:38-56`
- Modify: `addon/panel.py:76-87`
- Modify: `tests/blender/run_all.py`

**Interfaces:**
- Consumes: nothing from Tasks 1-2.
- Produces: `tests/blender/test_integration_contract.py` exposing
  `run() -> None` and printing
  `ALPHA_MATERIAL_SEPARATOR_INTEGRATION_CONTRACT_TESTS_OK`. Tasks 4 and 5 add to
  this same file and the same `run()`.

- [ ] **Step 1: Write the failing test**

Create `tests/blender/test_integration_contract.py`:

```python
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


def run() -> None:
    _assert_legacy_arguments_do_not_persist()
    print("ALPHA_MATERIAL_SEPARATOR_INTEGRATION_CONTRACT_TESTS_OK")
```

Register it in `tests/blender/run_all.py`. Add the import beside the others:

```python
from tests.blender.test_integration_contract import (  # noqa: E402
    run as run_integration_contract_tests,
)
```

and add the call inside the `if iteration == 0:` block, after
`run_simplification_contracts()`:

```python
            run_integration_contract_tests()
```

- [ ] **Step 2: Run it to verify it fails**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: FAIL with an assertion tuple such as `('image_name', False)`. Record
the observed value; do not infer it from the declaration.

- [ ] **Step 3: Add SKIP_SAVE to the three legacy fields**

In `addon/operators/analyze.py`, replace the three declarations:

```python
    image_name: StringProperty(
        name="Image Override", default="", options={"SKIP_SAVE"}
    )
```

```python
    uv_map_name: StringProperty(
        name="UV Map Override", default="", options={"SKIP_SAVE"}
    )
```

```python
    image_channel: EnumProperty(
        name="Image Channel",
        items=(
            ("ALPHA", "Alpha", "Use stored alpha"),
            ("RED", "Red", "Use red"),
            ("GREEN", "Green", "Use green"),
            ("BLUE", "Blue", "Use blue"),
            ("LUMINANCE", "Luminance", "Use RGB luminance"),
        ),
        default="ALPHA",
        options={"SKIP_SAVE"},
    )
```

- [ ] **Step 4: Delete the panel's per-draw reset**

In `addon/panel.py`, remove the three now-redundant lines from
`_set_analysis_properties`:

```python
    operator.image_name = ""
    operator.uv_map_name = ""
    operator.image_channel = "ALPHA"
```

The function keeps every remaining assignment unchanged, so its first statement
becomes `operator.material_overrides_json = material_overrides_json`.

- [ ] **Step 5: Run the suites to verify they pass**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: both PASS, with the new marker present. `tests/blender/test_ux_overrides.py`
exercises the panel-built analyze call and will catch it if dropping the resets
regresses the guided path.

- [ ] **Step 6: Commit**

```bash
git add addon/operators/analyze.py addon/panel.py tests/blender/test_integration_contract.py tests/blender/run_all.py
git commit -m "fix: stop legacy analyze arguments persisting between invocations"
```

---

### Task 4: Publish the cancelled status before tearing down

Fixes review item 4. In `addon/operators/analyze.py:254-261` the cancel branch
calls `_finish_modal(context)`, which calls `runtime.finish_analysis` and
therefore `runtime.tag_redraw()` (`addon/runtime.py:152`), before `_status()`
writes `ANALYSIS_CANCELLED`. The success path at line 273 publishes first. A
redraw can therefore run against the previous status.

**Files:**
- Modify: `addon/operators/analyze.py:250-261`
- Test: `tests/blender/test_integration_contract.py`

**Interfaces:**
- Consumes: `run()` from Task 3's new module.
- Produces: nothing new for later tasks.

- [ ] **Step 1: Write the failing test**

Add to `tests/blender/test_integration_contract.py`:

```python
def _assert_cancel_publishes_before_teardown() -> None:
    """A redraw triggered by teardown must not see the previous status."""

    from addon import runtime
    from addon.operators.analyze import ALPHA_MATERIAL_SEPARATOR_OT_analyze

    state = bpy.context.window_manager.alpha_material_separator_api
    state.last_status_code = "ANALYSIS_COMPLETE"
    observed: list[str] = []

    class _StubEngine:
        cancelled = False

        def cancel(self):
            self.cancelled = True

        def close(self):
            pass

    original_finish = runtime.finish_analysis

    def _recording_finish(window_manager):
        observed.append(state.last_status_code)
        original_finish(window_manager)

    operator = ALPHA_MATERIAL_SEPARATOR_OT_analyze()
    operator._engine = _StubEngine()
    operator._timer = None
    runtime.finish_analysis = _recording_finish
    try:
        result = operator.modal(
            bpy.context, type("_Event", (), {"type": "ESC"})()
        )
    finally:
        runtime.finish_analysis = original_finish

    assert result == {"CANCELLED"}, result
    assert operator._engine is None
    assert observed == ["ANALYSIS_CANCELLED"], observed
    assert state.last_status_code == "ANALYSIS_CANCELLED", state.last_status_code
```

Call it from `run()` before the print, after
`_assert_legacy_arguments_do_not_persist()`.

- [ ] **Step 2: Run it to verify it fails**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: FAIL with `observed == ['ANALYSIS_COMPLETE']`.

**If the stub context proves impractical** — for example if `_finish_modal`
raises on `context.workspace.status_text_set` in background mode — do not weaken
the assertion and do not skip it. Record what failed, apply the production swap
below, verify the ordering by reading the two lines, and report the ordering as
covered only by inspection so it lands in `docs/HANDOFF.md` as an explicit
untested item.

- [ ] **Step 3: Swap the two statements**

In `addon/operators/analyze.py`, change the cancel branch so the status is
published before teardown:

```python
        if event.type == "ESC" or runtime.cancellation_requested(
            context.window_manager
        ):
            self._engine.cancel()
            self._status(
                context,
                "ANALYSIS_CANCELLED",
                "Analysis cancelled; no partial result was retained",
            )
            self._finish_modal(context)
            return {"CANCELLED"}
```

- [ ] **Step 4: Run it to verify it passes**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: PASS. `tests/blender/test_analysis_preview.py` covers modal
cancellation preserving the previous complete report and must stay green.

- [ ] **Step 5: Commit**

```bash
git add addon/operators/analyze.py tests/blender/test_integration_contract.py
git commit -m "fix: publish the cancelled analysis status before teardown"
```

---

### Task 5: Publish RESULT_STALE on every stale transition

Fixes review item 5, the origin of the reported CATS defect.
`validation_state` flips to `STALE` while `last_status_code` still reads
`ANALYSIS_COMPLETE`, so a consumer reading either field alone is wrong.

Two production paths reach `STALE`: `runtime.mark_dirty` for settings changes,
and the stale branch of `runtime.record_validation` for an authoritatively
confirmed input change. Both already funnel through
`_sync_public_validation_state`, so the status is published there once rather
than duplicated at each call site. Approved by the user.

**Files:**
- Modify: `addon/runtime.py:1-14` (import), `addon/runtime.py:30-42`
- Modify: `docs/integration-api.md`
- Test: `tests/blender/test_integration_contract.py`

**Interfaces:**
- Consumes: `run()` from Task 3's new module.
- Produces: the public status code `"RESULT_STALE"`.

- [ ] **Step 1: Write the failing test**

Add to `tests/blender/test_integration_contract.py`. It needs a real analysis, so
it reuses the existing fixture helpers:

```python
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
```

Add `import json` to the module imports, and call both functions from `run()`
before the print.

- [ ] **Step 2: Run them to verify the first fails**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: `_assert_stale_result_publishes_a_status` FAILS with
`ANALYSIS_COMPLETE` at the `RESULT_STALE` assertion.
`_assert_a_clean_result_keeps_its_success_status` passes already; it exists to
catch the fix over-firing, so record that it passed at RED.

- [ ] **Step 3: Publish the status from the single sync point**

In `addon/runtime.py`, add the import beside the existing ones:

```python
from . import api_contract
```

Then in `_sync_public_validation_state`, publish before the early `continue` that
skips window managers without a published report:

```python
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
```

Verify there is no import cycle: `api_contract` imports only `manifest` and
`overrides`, and neither imports `runtime`.

- [ ] **Step 4: Run the full headless suite to verify**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: PASS. Pay attention to `tests/blender/test_revalidation_matrix.py`,
`test_analysis_preview.py`, and `test_assignment_policies.py`: they drive stale
transitions and assignment's `STALE_ANALYSIS` status. Assignment publishes
`STALE_ANALYSIS` after its validation call, so it must still win over
`RESULT_STALE`. If any test now fails on a status code, do not edit the
expectation before deciding which of the three cases it is — wrong
implementation, wrong test, or a deliberate behavior change — and report the
finding with its output.

- [ ] **Step 5: Document the status**

In `docs/integration-api.md`, add a row to the status table in the
"Assignment return and status behavior" section:

| Situation | Operator return | `last_status_code` |
| --- | --- | --- |
| A completed report became stale | not applicable, no operator ran | `RESULT_STALE` |

And add this paragraph immediately after that table:

```markdown
`RESULT_STALE` is published whenever a completed report transitions to
`validation_state == "STALE"`, including a settings change and an
authoritatively confirmed input change. It carries `analysis_id` and
`dirty_reason`. Before this existed, `last_status_code` kept reading
`ANALYSIS_COMPLETE` while `validation_state` said `STALE`, so a consumer reading
one field alone could act on a stale report. Read both, and treat the previous
`report_json` as advisory once either says stale. A depsgraph hint alone does not
publish it; `RECHECK_PENDING` is not stale.
```

- [ ] **Step 6: Commit**

```bash
git add addon/runtime.py docs/integration-api.md tests/blender/test_integration_contract.py
git commit -m "fix: publish RESULT_STALE when a completed report goes stale"
```

---

### Task 6: Assert panel-built overrides through classification counts

Fixes review item 1. The reviewer's instruction is to test the panel by asserting
count changes rather than by inspecting the panel. This also captures the real
design gap found during 1.1.1 testing: an override that carries a material but no
image passes `explicit_image=None` and falls through to the automatic path that
already failed, so it is a silent no-op.

This task adds coverage only. It does not change that behavior — the usability
fix is a separate objective recorded in `docs/HANDOFF.md`.

**Files:**
- Modify: `tests/blender/test_ux_overrides.py`

**Interfaces:**
- Consumes: `addon.panel._override_payload(settings) -> tuple[str, bool]`,
  returning the JSON payload and an `invalid` flag; the existing fixture helpers
  `_clear_scene`, `_image`, `_material`, `_quad`, `_select_only`, and
  `_file_backed_image` in this module.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the failing test**

Add to `tests/blender/test_ux_overrides.py`, importing `_override_payload`
alongside the existing panel imports:

```python
from addon.panel import (
    ALPHA_MATERIAL_SEPARATOR_PT_main,
    _draw_completion,
    _label_lines,
    _override_payload,
)
```

```python
def _counts_for(override_json: str) -> dict[str, int]:
    result = bpy.ops.alpha_material_separator.analyze(
        api_major=1, material_overrides_json=override_json
    )
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    return json.loads(state.report_json)["counts"]


def _assert_panel_built_overrides_change_the_result(manual_material, override_image):
    """Prove the panel's payload reaches classification, by counts not by pixels."""

    settings = bpy.context.window_manager.alpha_material_separator_settings
    settings.material_overrides.clear()
    baseline = _counts_for("[]")

    item = settings.material_overrides.add()
    item.material = manual_material
    payload, invalid = _override_payload(settings)
    assert not invalid, payload
    assert json.loads(payload)[0]["image_name"] == "", payload
    # An override with no image resolves through the automatic path that already
    # failed, so the panel currently lets a user build a no-op. Counts prove it.
    assert _counts_for(payload) == baseline, payload

    item.image = override_image
    item.image_channel = "RED"
    payload, invalid = _override_payload(settings)
    assert not invalid, payload
    assert json.loads(payload)[0]["image_channel"] == "RED", payload
    changed = _counts_for(payload)
    assert changed != baseline, (changed, baseline)
    assert changed["UNSUPPORTED"] < baseline["UNSUPPORTED"], (changed, baseline)

    settings.material_overrides.clear()
```

Call it from `run()` immediately after the existing
`groups[manual_material.name]` assertions (around line 182) and **before** the
section that renames `manual_material`, passing the two fixtures already built
there:

```python
    _assert_panel_built_overrides_change_the_result(manual_material, override_image)
```

- [ ] **Step 2: Run it and record what it proves**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Expected: PASS. This is characterization coverage of existing behavior, not a
RED gate, so it passes on the first run by design. If the no-image assertion
fails instead, the no-op analysis in the review is wrong and the finding must be
re-reported before going further. If `UNSUPPORTED` is not the class the bare
material lands in, read the actual counts from the failure output and pin the
class it really uses rather than loosening the assertion to `!=` alone.

- [ ] **Step 3: Commit**

```bash
git add tests/blender/test_ux_overrides.py
git commit -m "test: assert panel-built overrides through classification counts"
```

---

### Task 7: Close the milestone

**Files:**
- Modify: `docs/HANDOFF.md`
- Delete: `docs/superpowers/plans/2026-08-07-integration-contract-fixes.md`

- [ ] **Step 1: Run the full change gate**

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Record each command and its actual result. The private
`.local-references/default-example/` smoke is **not** required: no change here
affects material resolution, rasterization, classification, cache validity,
preview plans, assignment plans, or mutation safety. Say so explicitly rather
than leaving it ambiguous.

- [ ] **Step 2: Update the handoff**

Replace the "Integration-contract defects" follow-up block in
`docs/HANDOFF.md` with what actually landed: the corrected `address_modes` and
the decision not to bump `API_VERSION`, the guarded `ANALYSIS_SETTING_NAMES`,
the three `SKIP_SAVE` fields and the deleted panel resets, the cancel-path
ordering, `RESULT_STALE`, and the override count coverage. Keep the
manual-alpha-source usability objective as unstarted follow-up work. Name any
item that ended up covered only by inspection.

- [ ] **Step 3: Delete this plan and commit**

```bash
git rm docs/superpowers/plans/2026-08-07-integration-contract-fixes.md
git add docs/HANDOFF.md
git commit -m "docs: close out the integration-contract fixes"
```

---

## Out of scope

- The manual-alpha-source usability fixes. Separate objective, separate branch,
  and the inline-editor option needs its own spec.
- Any `addon/blender_manifest.toml` version change.
- `addon/runtime.py:315-316` is missing the two blank lines PEP 8 wants between
  `tag_redraw()` and `def coverage_get`. Real but unrelated; leave it.
- Promoting `reset_analysis_settings` to the public operator list.
