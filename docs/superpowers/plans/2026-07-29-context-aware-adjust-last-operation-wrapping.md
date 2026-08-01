# Context-Aware Adjust Last Operation Wrapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Blender's narrow Adjust Last Operation HUD from ellipsizing the assignment summary while preserving the existing adaptive Apply confirmation dialog.

**Architecture:** Keep sentence generation and word wrapping unchanged. In the assignment operator's existing `draw(context)` method, select the current HUD region width when Blender is drawing the native `HUD`; otherwise retain the saved 420–560 pixel confirmation width. Extend the existing recording-layout integration test rather than adding a new module or presentation abstraction.

**Tech Stack:** Python 3.11, Blender 5.2 RNA/UI layouts, existing `ui_text_lines()` helper, `unittest`, existing headless Blender test runner.

## Global Constraints

- Preserve extension version `0.1.0`, API `1.2`, operator IDs, classifications, policies, assignment behavior, public payloads, and user-facing sentences.
- Change presentation only; do not change analysis, preview, plans, cache state, materials, meshes, or undo behavior.
- Use Blender's exact region identifier `HUD`.
- Use `context.region.width` only when the region type is `HUD` and the width is positive.
- Continue using `_confirmation_draw_width` in confirmation, non-HUD, and missing-context draws.
- Use a private 220-pixel fallback only for a `HUD` region with a missing or zero width.
- Reuse `ui_text_lines()`; do not create another wrapper, font-measurement system, custom HUD, new RNA property, dependency, or alternate completion copy.
- Keep the separator before the final safety and undo sentence.
- Do not stage or commit the unrelated existing `AGENTS.md` modification.
- This presentation-only change does not require the private before/after `.blend` smoke.
- Rebuild and validate the ignored ZIP because installed UI behavior changes.

---

### Task 1: Make Assignment Drawing Aware of Blender's HUD Width

**Files:**
- Modify: `addon/operators/assign_materials.py:23-28,224-232`
- Test: `tests/blender/test_assignment_policies.py:299-311`

**Interfaces:**
- Consumes: `ui_text_lines(text: str, available_width: int) -> tuple[str, ...]`
- Consumes: `context.region.type: str` and `context.region.width: int`
- Produces: private constant `_ADJUST_LAST_OPERATION_FALLBACK_WIDTH = 220`
- Preserves: `_confirmation_draw_width`, `_confirmation_dialog_width()`, confirmation copy, and `_DialogRecordingLayout`

- [x] **Step 1: Replace the old manual narrow-width test with failing host-aware regressions**

In `tests/blender/test_assignment_policies.py`, replace lines 299–311 with:

```python
    confirmation_lines = assignment_confirmation_lines(public_plan)

    dialog_draw = _DialogRecordingLayout()
    operator.layout = dialog_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        operator,
        SimpleNamespace(region=SimpleNamespace(type="WINDOW", width=180)),
    )
    assert dialog_draw.labels[0][0] == confirmation_lines[0]
    assert dialog_draw.separators == 1

    hud_draw = _DialogRecordingLayout()
    operator.layout = hud_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        operator,
        SimpleNamespace(region=SimpleNamespace(type="HUD", width=220)),
    )
    expected_hud_text = [
        wrapped
        for sentence in confirmation_lines
        for wrapped in ui_text_lines(sentence, 220)
    ]
    assert [text for text, _icon in hud_draw.labels] == expected_hud_text
    assert len(hud_draw.labels) > len(dialog_draw.labels)
    assert hud_draw.separators == 1

    fallback_draw = _DialogRecordingLayout()
    operator.layout = fallback_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        operator,
        SimpleNamespace(region=SimpleNamespace(type="HUD", width=0)),
    )
    expected_fallback_text = [
        wrapped
        for sentence in confirmation_lines
        for wrapped in ui_text_lines(sentence, 220)
    ]
    assert [text for text, _icon in fallback_draw.labels] == expected_fallback_text

    missing_context_draw = _DialogRecordingLayout()
    operator.layout = missing_context_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(operator, None)
    assert missing_context_draw.labels == dialog_draw.labels
```

Also add `ui_text_lines` to the existing import from `addon.presentation`:

```python
from addon.presentation import (
    already_separated_tooltip,
    assignment_confirmation_lines,
    review_signature,
    ui_text_lines,
)
```

This test intentionally uses a narrow `WINDOW` width to prove that non-HUD
draws remain governed by the retained 560-pixel confirmation width, not by the
current region width.

- [x] **Step 2: Run the headless Blender suite and verify RED**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: `tests/blender/test_assignment_policies.py` fails because the current
`draw()` ignores the `HUD` region width, so `hud_draw.labels` still matches the
wide dialog layout. Confirm no earlier unrelated failure hides this expected
regression.

- [x] **Step 3: Implement the smallest context-aware width selection**

In `addon/operators/assign_materials.py`, add beside the existing confirmation
constants:

```python
_ADJUST_LAST_OPERATION_FALLBACK_WIDTH = 220
```

Replace `draw()` with:

```python
    def draw(self, context) -> None:
        plan = json.loads(self._confirmation_plan_json)
        lines = assignment_confirmation_lines(plan)
        draw_width = self._confirmation_draw_width
        region = getattr(context, "region", None)
        if getattr(region, "type", "") == "HUD":
            region_width = int(getattr(region, "width", 0) or 0)
            draw_width = (
                region_width
                if region_width > 0
                else _ADJUST_LAST_OPERATION_FALLBACK_WIDTH
            )
        for line in lines[:-1]:
            for wrapped in ui_text_lines(line, draw_width):
                self.layout.label(text=wrapped)
        self.layout.separator()
        for wrapped in ui_text_lines(lines[-1], draw_width):
            self.layout.label(text=wrapped)
```

Do not set `layout.ui_units_x`: Blender owns the HUD width, and using the actual
region width keeps the text correct if the user resizes that native region.

- [x] **Step 4: Run the headless Blender suite and verify GREEN**

Run the Step 2 command again.

Expected: the complete headless suite passes. The generated HUD case uses more
labels without ellipsizing source text, the confirmation retains its 560-pixel
layout, and missing context remains backward-compatible.

- [x] **Step 5: Run the ordinary unit suite and source validation**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Expected: all unit tests pass, source validation succeeds, and
`git diff --check` reports no whitespace errors beyond any already-known
working-copy line-ending warning for unstaged `AGENTS.md`.

- [x] **Step 6: Commit the tested presentation correction**

Review the focused diff, then run:

```powershell
git add addon/operators/assign_materials.py `
  tests/blender/test_assignment_policies.py
git diff --cached --check
git commit -m "fix: wrap assignment summary for Blender HUD"
```

Expected: the commit contains only the operator change and its generated
Blender regression. `AGENTS.md` remains unstaged.

---

### Task 2: Validate the Installed UI and Refresh the Package

**Files:**
- Modify: `docs/HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-07-29-context-aware-adjust-last-operation-wrapping.md`
- Generated and ignored: `.packaged-releases/alpha_material_separator-0.1.0.zip`

**Interfaces:**
- Consumes: the context-aware `draw(context)` behavior from Task 1
- Produces: a validated local ZIP and an exact continuation record
- Preserves: all private `.local-references/` files and the unstaged `AGENTS.md` change

- [x] **Step 1: Rebuild and validate the ignored extension ZIP**

Run:

```powershell
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases

$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path

& $Blender52 --factory-startup --command extension validate $Archive
Get-Item -LiteralPath $Archive | Select-Object FullName,Length
Get-FileHash -Algorithm SHA256 $Archive
```

Expected: build and archive validation succeed. Record the exact byte size and
SHA-256 in `docs/HANDOFF.md`; never stage the ZIP.

- [x] **Step 2: Perform a focused Blender 5.2 visual acceptance**

Partially complete: the installed ZIP passed Analyze → Preview → Apply, the
adaptive confirmation, normal-width HUD readability without ellipses,
sidebar/HUD fact equivalence, and undo. Blender did not respond to the attempted
native-HUD resize, so steps 6 and 7 remain unverified.

The user subsequently accepted the resulting UI as the desired version. The
unverified native-HUD resize interaction is not a milestone blocker.

Using the rebuilt ZIP in an isolated Blender 5.2 configuration:

1. Run Analyze → Preview → Apply on a generated or lawful local file that
   produces the warning confirmation.
2. Confirm the Apply confirmation still uses its adaptive width and readable
   word wrapping.
3. Apply the reviewed operation.
4. Open the bottom-left `Assign Alpha Materials` HUD.
5. Confirm every extension sentence is fully readable without ellipses at its
   normal width.
6. Narrow the HUD and confirm sentences wrap at word boundaries.
7. Widen the HUD and confirm wrapping decreases.
8. Confirm the sidebar completion facts match the HUD facts.
9. Press `Ctrl+Z` and confirm the assignment remains undoable.

Expected: confirmation and HUD are both readable, resizing affects wrapping
only, the same facts are shown, and undo succeeds. Do not save a private
reference file after this interaction.

- [x] **Step 3: Update the handoff and plan with exact evidence**

In `docs/HANDOFF.md`:

- record commit `8f960d5` as the approved design boundary;
- record the Task 1 test commands and exact results;
- record source and archive validation results;
- record the rebuilt archive size and SHA-256;
- record every completed or unverified visual acceptance item;
- remove the HUD truncation issue if the visual check passed;
- retain unrelated open release requirements;
- set the single recommended next action to the highest-priority remaining
  unverified item.

In this plan, mark only steps backed by the exact command or interaction as
complete. Do not modify `AGENTS.md`.

- [x] **Step 4: Commit the validation record**

Run:

```powershell
git add docs/HANDOFF.md `
  docs/superpowers/plans/2026-07-29-context-aware-adjust-last-operation-wrapping.md
git diff --cached --check
git commit -m "docs: record Blender HUD wrapping validation"
```

Expected: only the handoff and this tracked plan are committed. Private files,
the ZIP, test output, and `AGENTS.md` remain uncommitted or ignored.

- [x] **Step 5: Report the final local state**

Run:

```powershell
git status --short --branch
git log -5 --oneline
```

Expected: report every remaining uncommitted file accurately, state the archive
path and validation status, and confirm nothing was pushed.
