# Already-Separated Button Tooltips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the disabled Preview and Apply buttons an accurate hover message when selected meshes are already optimally assigned.

**Architecture:** Keep plan-state interpretation in the existing presentation layer and pass its contextual text through hidden, transient operator properties. Both existing operators use Blender's dynamic `description` hook and retain their current descriptions when no contextual text is supplied.

**Tech Stack:** Python 3.11, Blender 5.2 `bpy`, `unittest`.

## Global Constraints

- Use exactly: `All faces on the selected meshes are optimally assigned. No faces need to be moved.`
- Show that text only when the current plan is non-actionable because it contains already-derived AMS material groups.
- Do not change analysis, preview, assignment, persistent state, public operator IDs, API version, or classifications.
- Add no dependency, operator, panel, or property group.

---

### Task 1: State-aware Preview and Apply tooltips

**Files:**
- Modify: `addon/presentation.py`
- Modify: `addon/operators/select_faces.py`
- Modify: `addon/operators/assign_materials.py`
- Modify: `addon/panel.py`
- Test: `tests/unit/test_presentation.py`
- Test: `tests/blender/test_ux_overrides.py`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Produces: `already_separated_tooltip(*, already_derived: bool, actionable: bool, has_skips: bool) -> str`
- Consumes: hidden operator property `ui_description: str`

- [x] **Step 1: Add the failing presentation test**

Add assertions that only a non-actionable, already-derived plan without skips
returns the exact approved message. Missing derived groups, actionable changes,
or skips return an empty string.

- [x] **Step 2: Run the focused unit test and verify RED**

Run:

```powershell
python -m unittest tests.unit.test_presentation -v
```

Expected: import or attribute failure because `already_separated_tooltip` does
not exist.

- [x] **Step 3: Add the failing Blender operator-description test**

In `tests/blender/test_ux_overrides.py`, call each real operator class's
`description` method with a property object containing the approved contextual
message. Assert both return it, and assert an empty `ui_description` returns
each operator's existing `bl_description`.

- [x] **Step 4: Run the focused Blender operator-description test and verify RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: failure because the operators do not yet expose dynamic descriptions.

- [x] **Step 5: Implement the minimum production change**

Add the pure presentation helper and hidden `ui_description` string property to
both operators. Implement:

```python
@classmethod
def description(cls, _context, properties):
    return properties.ui_description or cls.bl_description
```

In the panel, compute the already-separated state once and assign the helper's
result to both button operators. Reuse the same state for the existing
“Already separated — no additional changes” card.

- [x] **Step 6: Run focused tests and verify GREEN**

Run the two commands from Steps 2 and 4. Expected: both pass.

- [x] **Step 7: Run regression verification**

```powershell
python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
git diff --check
```

Expected: all unit and Blender tests pass; no whitespace errors.

- [x] **Step 8: Update handoff and commit**

Record exact commands and results in `docs/HANDOFF.md`, remove the tooltip task
from immediate work, and commit the focused implementation without pushing.
