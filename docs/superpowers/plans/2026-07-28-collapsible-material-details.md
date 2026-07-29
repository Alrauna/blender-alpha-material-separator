# Collapsible Material Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the always-expanded material result cards with one automatically collapsed native disclosure and a concise alpha-source advisory.

**Architecture:** Keep the existing review report and card rendering authoritative. Add one transient `WindowManager` UI Boolean, derive a deduplicated card list and unsupported count from the existing report payload, and reset the Boolean only when a replacement analysis is successfully published.

**Tech Stack:** Python 3.11, Blender 5.2 RNA/UI API, `unittest`, headless Blender integration tests.

## Global Constraints

- Preserve extension version `0.1.0`, API `1.2`, operator IDs, report classifications, and assignment behavior.
- Use Blender's native Boolean disclosure row; add no operator, panel, dependency, search, filter, pagination, or persistent file state.
- Keep object-level safety warnings, totals, classifications, and Preview outside the disclosure.
- Deduplicate material cards exactly as the current panel does.
- Collapse after every successfully published analysis; canceled or failed replacement analysis preserves the previous report and disclosure state.
- Toggling the disclosure must not invalidate the analysis or guided review token.
- Private `.blend` files and their identifying output remain ignored and uncommitted.

---

### Task 1: Specify report presentation and disclosure state

**Files:**
- Modify: `tests/unit/test_presentation.py`
- Modify: `tests/blender/test_ux_overrides.py`
- Modify: `addon/presentation.py`
- Modify: `addon/properties.py`
- Modify: `addon/operators/analyze.py`

**Interfaces:**
- Produces: `review_material_cards(report_payload) -> tuple[dict, ...]`
- Produces: `alpha_source_advisory(material_cards) -> tuple[str, str] | None`
- Produces: `WindowManager.alpha_material_separator_ui.show_material_details: bool`

- [x] **Step 1: Write failing unit tests**

Add tests proving duplicate cards count once, one/two unsupported cards use singular/plural advisory copy, and all-supported cards return no advisory.

- [x] **Step 2: Run the focused unit tests and verify RED**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' -m unittest tests.unit.test_presentation -v
```

Expected: fail because the presentation helpers do not exist.

- [x] **Step 3: Write failing Blender state tests**

Add assertions that successful publication resets `show_material_details` to `False`, cancellation preserves it, and toggling it leaves the current analysis ID and review token unchanged.

- [x] **Step 4: Run the focused Blender test and verify RED**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/test_ux_overrides.py
```

Expected: fail because the transient RNA property does not exist.

- [x] **Step 5: Implement the smallest state and presentation change**

Add the two pure presentation helpers, the `SKIP_SAVE` Boolean property, and one successful-publication reset. Do not reset the property on cancellation or error paths.

- [x] **Step 6: Run focused tests and verify GREEN**

Run both focused commands from Steps 2 and 4. Expected: pass.

### Task 2: Render the native disclosure and advisory

**Files:**
- Modify: `addon/panel.py`
- Modify: `tests/unit/test_presentation.py`

**Interfaces:**
- Consumes: `review_material_cards` and `alpha_source_advisory`
- Produces: review UI label `Material Details (N)` and advisory copy from Task 1

- [x] **Step 1: Add failing source-contract assertions**

Assert the panel consumes the presentation helpers and binds the disclosure row to `show_material_details`.

- [x] **Step 2: Run the focused unit test and verify RED**

Run the Task 1 unit command. Expected: fail because the panel has not yet adopted the disclosure.

- [x] **Step 3: Move existing cards behind one native disclosure**

Render object skip warnings first. Render the advisory box when the helper returns copy. Render `Material Details (N)` with `TRIA_RIGHT`/`TRIA_DOWN`, and render the existing deduplicated cards only while expanded.

- [x] **Step 4: Run focused and full automated tests**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' -m unittest discover -s tests/unit -t . -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: all pass.

### Task 3: Documentation, private smoke, and package

**Files:**
- Modify: `README.md`
- Modify: `docs/testing.md`
- Modify: `docs/HANDOFF.md`
- Modify locally only: `.local-references/default-example/_diagnose_rerun_tooltip.py`

**Interfaces:**
- Documents: collapsed-by-default behavior, advisory meaning, and manual disclosure verification
- Produces locally: validated `.packaged-releases/alpha_material_separator-0.1.0.zip`

- [x] **Step 1: Update user and test documentation**

Document that `Material Details` is collapsed after every successful analysis, the advisory indicates manual-source candidates, and expanding it reveals existing per-material actions.

- [x] **Step 2: Run the private messy-material smoke**

Use `before.blend` and the ignored helper to assert the successful analysis leaves details collapsed and produces only anonymized aggregate card/advisory counts. Do not commit the helper or output.

- [x] **Step 3: Validate and rebuild**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --command extension validate addon
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --command extension validate .packaged-releases\alpha_material_separator-0.1.0.zip
```

Expected: source, build, and archive validation succeed.

- [x] **Step 4: Update the handoff and commit**

Record exact commands/results, remaining interactive narrow/wide-sidebar verification, package hash, and the next action in `docs/HANDOFF.md`; then create one focused local implementation commit. Do not push.
