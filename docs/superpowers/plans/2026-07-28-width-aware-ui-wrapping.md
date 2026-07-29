# Width-Aware UI Wrapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed character wrapping with responsive panel text and an adaptive 420–560 pixel Apply confirmation dialog.

**Architecture:** Keep sentence generation in `addon/presentation.py` and add one pure width-to-lines helper there. The panel supplies its current region width; the Apply operator computes and retains a bounded dialog width from the confirmation copy and window width. Existing Blender recording layouts verify the wiring without adding dependencies or changing workflow behavior.

**Tech Stack:** Python 3.11, standard-library `textwrap`, Blender 5.2 RNA/UI layouts, `unittest`, existing headless Blender test runner.

## Global Constraints

- Preserve extension version `0.1.0`, API `1.2`, operator IDs, classifications, policies, confirmation rules, and public payloads.
- Do not change analysis, preview, assignment plans, material data, generated sentences, or user-facing copy.
- Use no new dependency and no pixel-perfect font-measurement subsystem.
- Wrap only between words; never split long words.
- Use the actual sidebar region width when available and a deterministic fallback only for non-region test contexts.
- Request an Apply dialog width normally clamped to 420–560 pixels; permit a smaller width only when the usable Blender window is narrower.
- Keep icons on the first rendered line only.
- Test production behavior before editing production code.
- Do not run the private `.blend` smoke because this presentation-only change does not alter assignment-plan data.
- Do not stage or commit the existing unrelated `AGENTS.md` work.

---

### Task 1: Pure Width-Aware Line Layout

**Files:**
- Modify: `addon/presentation.py`
- Test: `tests/unit/test_presentation.py`

**Interfaces:**
- Produces: `ui_text_lines(text: str, available_width: int) -> tuple[str, ...]`
- Produces: private constants `_UI_AVERAGE_CHARACTER_WIDTH`, `_UI_HORIZONTAL_PADDING`, and `_UI_MIN_LINE_CHARACTERS`
- Consumes: standard-library `textwrap.wrap`

- [x] **Step 1: Add a failing generated regression**

Add the import and test below to `tests/unit/test_presentation.py`:

```python
from addon.presentation import ui_text_lines


def test_width_aware_ui_text_keeps_and_wraps_sentences(self) -> None:
    sentence = "Open Material Details below to review it."

    wide = ui_text_lines(sentence, 560)
    ordinary = ui_text_lines(sentence, 420)
    narrow = ui_text_lines(sentence, 180)

    self.assertEqual(wide, (sentence,))
    self.assertEqual(ordinary, (sentence,))
    self.assertGreater(len(narrow), 1)
    self.assertEqual(" ".join(narrow), sentence)
    self.assertGreaterEqual(len(narrow), len(ordinary))
    self.assertGreaterEqual(len(ordinary), len(wide))
    self.assertEqual(ui_text_lines("", 180), ("",))

    long_word = "AlphaMaterialSeparatorIdentifier"
    self.assertEqual(ui_text_lines(long_word, 80), (long_word,))
```

- [x] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_presentation.PresentationTests.test_width_aware_ui_text_keeps_and_wraps_sentences `
  -v
```

Expected: `ERROR` because `ui_text_lines` cannot yet be imported.

- [x] **Step 3: Add the minimal pure implementation**

In `addon/presentation.py`, import `textwrap` and add:

```python
_UI_AVERAGE_CHARACTER_WIDTH = 7
_UI_HORIZONTAL_PADDING = 32
_UI_MIN_LINE_CHARACTERS = 12


def ui_text_lines(text: str, available_width: int) -> tuple[str, ...]:
    """Wrap UI copy conservatively for the available Blender layout width."""

    usable_width = max(1, int(available_width) - _UI_HORIZONTAL_PADDING)
    line_characters = max(
        _UI_MIN_LINE_CHARACTERS,
        usable_width // _UI_AVERAGE_CHARACTER_WIDTH,
    )
    return tuple(
        textwrap.wrap(
            str(text),
            width=line_characters,
            break_long_words=False,
            break_on_hyphens=False,
        )
    ) or ("",)
```

Do not add configurable font metrics, glyph measurement, or a new module.

- [x] **Step 4: Run the focused test and verify GREEN**

Run the Step 2 command again.

Expected: one test passes.

- [x] **Step 5: Run the complete ordinary unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all unit tests pass; the existing confirmation sentences remain byte-for-byte unchanged.

- [x] **Step 6: Commit the pure behavior boundary**

```powershell
git add addon/presentation.py tests/unit/test_presentation.py
git commit -m "feat: add width-aware UI text wrapping"
```

Expected: the commit contains only the helper and its pure regression.

---

### Task 2: Wire the Sidebar and Adaptive Apply Dialog

**Files:**
- Modify: `addon/panel.py`
- Modify: `addon/operators/assign_materials.py`
- Test: `tests/blender/test_ux_overrides.py`
- Test: `tests/blender/test_assignment_policies.py`

**Interfaces:**
- Consumes: `ui_text_lines(text: str, available_width: int) -> tuple[str, ...]`
- Produces: `_confirmation_dialog_width(lines: tuple[str, ...], window_width: int) -> int`
- Produces: operator instance field `_confirmation_draw_width: int`
- Preserves: `_CONFIRMATION_TITLE == "Apply Material Separation"` and `_CONFIRMATION_TEXT == "Apply"`

- [x] **Step 1: Add failing panel layout regressions**

Import `_label_lines` in `tests/blender/test_ux_overrides.py`, then add near the start of `run()`:

```python
    sentence = "Open Material Details below to review it."

    wide_layout = _RecordingLayout()
    _label_lines(wide_layout, sentence, icon="INFO", available_width=560)
    assert wide_layout.labels == [(sentence, "INFO")]

    narrow_layout = _RecordingLayout()
    _label_lines(narrow_layout, sentence, icon="INFO", available_width=180)
    assert len(narrow_layout.labels) > 1, narrow_layout.labels
    assert " ".join(text for text, _icon in narrow_layout.labels) == sentence
    assert narrow_layout.labels[0][1] == "INFO"
    assert all(icon == "NONE" for _text, icon in narrow_layout.labels[1:])
```

- [x] **Step 2: Add failing adaptive-dialog regressions**

In `tests/blender/test_assignment_policies.py`:

1. Replace the `_CONFIRMATION_WIDTH` import with `_confirmation_dialog_width`.
2. Add this recording layout:

```python
class _DialogRecordingLayout:
    def __init__(self):
        self.labels = []
        self.separators = 0

    def label(self, *, text="", icon="NONE"):
        self.labels.append((text, icon))

    def separator(self):
        self.separators += 1
```

3. Replace `assert _CONFIRMATION_WIDTH == 420` with:

```python
    short_lines = ("Move 2 reviewed faces to alpha materials.",)
    long_lines = (
        "Only material slots and face assignments change—no topology "
        "or source shader changes. Ctrl+Z to undo.",
    )
    assert _confirmation_dialog_width(short_lines, 1920) == 420
    assert _confirmation_dialog_width(long_lines, 1920) == 560
    assert _confirmation_dialog_width(long_lines, 500) == 436
```

4. Give the fake invoke context a `window=SimpleNamespace(width=1920)`.
5. Change the recorded dialog assertion to expect width `560` for the existing partial-support confirmation.
6. Assert `operator._confirmation_draw_width == 560`.
7. Exercise `draw()` at wide and narrow retained widths:

```python
    wide_draw = _DialogRecordingLayout()
    operator.layout = wide_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(operator, None)
    confirmation_lines = assignment_confirmation_lines(public_plan)
    assert wide_draw.labels[0][0] == confirmation_lines[0]
    assert wide_draw.separators == 1

    narrow_draw = _DialogRecordingLayout()
    operator.layout = narrow_draw
    operator._confirmation_draw_width = 260
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(operator, None)
    assert len(narrow_draw.labels) > len(confirmation_lines)
    assert wide_draw.labels != narrow_draw.labels
```

- [x] **Step 3: Run both headless regressions and verify RED**

Run the real harness (the individual modules define `run()` but do not execute
or register the extension when launched directly):

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: the suite fails while importing the missing adaptive dialog helper.

- [x] **Step 4: Route all shared panel text through the current region width**

In `addon/panel.py`:

1. Remove the `textwrap` import.
2. Import `ui_text_lines` from `.presentation`.
3. Change the helper to:

```python
def _label_lines(
    layout,
    text: str,
    *,
    icon: str = "NONE",
    available_width: int,
) -> None:
    """Draw readable copy for the available Blender sidebar width."""

    for index, line in enumerate(ui_text_lines(text, available_width)):
        layout.label(text=line, icon=icon if index == 0 else "NONE")
```

4. At the start of `ALPHA_MATERIAL_SEPARATOR_PT_main.draw()`, calculate:

```python
region = getattr(context, "region", None)
available_width = int(getattr(region, "width", 320) or 320)
```

5. Add `available_width` parameters to `_draw_completion()` and
   `_draw_status_problem()`.
6. Pass `available_width=available_width` to every `_label_lines()` call,
   including selection help, status/remedy text, completion text, object
   warnings, the Material Details advisory, unsupported material details, and
   Apply remediation.
7. Pass the same value when `draw()` calls `_draw_completion()` and
   `_draw_status_problem()`.
8. Update the direct `_draw_completion()` call in
   `tests/blender/test_ux_overrides.py` with `available_width=420`.

Do not special-case the Material Details sentence; fixing the shared helper is
the root-cause correction.

- [x] **Step 5: Add adaptive confirmation width and retain it for drawing**

In `addon/operators/assign_materials.py`:

1. Remove the `textwrap` import.
2. Import `ui_text_lines` and `_UI_AVERAGE_CHARACTER_WIDTH` from
   `addon.presentation`.
3. Replace `_CONFIRMATION_WIDTH` with:

```python
_CONFIRMATION_MIN_WIDTH = 420
_CONFIRMATION_MAX_WIDTH = 560
_CONFIRMATION_WINDOW_MARGIN = 64
_CONFIRMATION_TEXT_PADDING = 32
```

4. Add:

```python
def _confirmation_dialog_width(
    lines: tuple[str, ...],
    window_width: int,
) -> int:
    longest = max((len(line) for line in lines), default=0)
    preferred = max(
        _CONFIRMATION_MIN_WIDTH,
        min(
            _CONFIRMATION_MAX_WIDTH,
            longest * _UI_AVERAGE_CHARACTER_WIDTH
            + _CONFIRMATION_TEXT_PADDING,
        ),
    )
    usable_window = max(1, int(window_width) - _CONFIRMATION_WINDOW_MARGIN)
    return min(preferred, usable_window)
```

5. Add `_confirmation_draw_width = _CONFIRMATION_MIN_WIDTH` beside the
   operator's existing confirmation state.
6. In `invoke()`, immediately after creating `lines` from the saved plan:

```python
lines = assignment_confirmation_lines(plan_payload)
self._confirmation_draw_width = _confirmation_dialog_width(
    lines,
    context.window.width,
)
```

7. Pass `self._confirmation_draw_width` to `invoke_props_dialog(width=...)`.
8. In `draw()`, replace both fixed `textwrap.wrap(..., width=52)` loops with
   `ui_text_lines(line, self._confirmation_draw_width)`. Retain the existing
   separator before the final safety sentence.

- [x] **Step 6: Run the focused Blender regressions and verify GREEN**

Run the Step 3 command again.

Expected: both scripts pass. Wide Material Details copy remains one label,
narrow copy wraps with one icon, dialog invocation records its adaptive width,
and `draw()` uses the retained width.

- [x] **Step 7: Run the complete headless Blender suite**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: the complete suite passes with no workflow, plan, mutation, or public
API regression.

- [x] **Step 8: Commit the Blender integration boundary**

```powershell
git add addon/panel.py addon/operators/assign_materials.py `
  tests/blender/test_ux_overrides.py tests/blender/test_assignment_policies.py
git commit -m "fix: adapt UI text to available width"
```

Expected: the commit contains only UI wiring and generated Blender regressions.

---

### Task 3: Validate and Package the Installable Extension

**Files:**
- Modify: `docs/HANDOFF.md`
- Generated and ignored: `.packaged-releases/alpha_material_separator-0.1.0.zip`

**Interfaces:**
- Consumes: completed width-aware panel and Apply dialog behavior
- Produces: validated local extension archive and accurate continuation record

- [x] **Step 1: Run the full ordinary and source validation gates**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v

& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py

& $Blender52 --factory-startup --command extension validate addon

git diff --check
```

Expected: all unit and headless Blender tests pass, source validation succeeds,
and `git diff --check` reports no whitespace errors.

- [x] **Step 2: Rebuild and validate the ignored ZIP**

Run:

```powershell
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases

$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path

& $Blender52 --factory-startup --command extension validate $Archive
Get-FileHash -Algorithm SHA256 $Archive
```

Expected: build and archive validation succeed; record the exact size and
SHA-256 without staging the ZIP.

- [ ] **Step 3: Perform focused installed-ZIP visual acceptance**

Partial evidence: the rebuilt ZIP was installed and enabled in an ignored
isolated Blender profile. Source-registered factory-startup sessions passed the
100% narrow/wide and 150% standard-width interaction checks. Keep this checkbox
open until the isolated installed-ZIP session itself completes every width and
scale combination below.

In a clean Blender 5.2 configuration:

1. Install the rebuilt ZIP.
2. At 100% UI scale, resize the `Alpha Material` sidebar narrowly and widely.
3. Confirm Material Details guidance wraps only when it does not fit.
4. Open a warning-only Apply confirmation and confirm it expands up to 560
   pixels on a wide display.
5. Narrow the Blender window and confirm the dialog shrinks and wraps at word
   boundaries without clipped action buttons.
6. Repeat the narrow/wide checks at 150% UI scale.
7. Cancel the confirmation and verify zero mutation.

Expected: short sentences stay intact when space permits; narrow text remains
readable; Cancel performs no assignment.

- [x] **Step 4: Update the handoff with exact evidence**

In `docs/HANDOFF.md`:

- mark width-aware wrapping implemented;
- record exact test counts and command results;
- record archive size and SHA-256;
- record which visual combinations passed or remain unverified;
- remove the fixed-wrapping task from immediate attention;
- leave unrelated release requirements unchanged;
- identify the single next action.

Do not add temporary progress to `AGENTS.md`.

- [x] **Step 5: Commit the validated documentation boundary**

Review `git status --short` and `git diff`. Stage only the intended handoff and
approved tracked plan:

```powershell
git add docs/HANDOFF.md `
  docs/superpowers/plans/2026-07-28-width-aware-ui-wrapping.md
git commit -m "docs: record responsive UI validation"
```

Expected: `AGENTS.md`, the ZIP, private references, and test output are not in
the commit. The visual-acceptance checkbox remains open until it is performed.

- [ ] **Step 6: Report the completed local state**

Run:

```powershell
git status --short
git log -4 --oneline
```

Expected: report every remaining uncommitted file accurately and state that
nothing was pushed.
