# Expert Analysis Settings Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the seven Expert Analysis Settings tooltips in language a 3D artist can act on, and add a Reset to Default Values button to that panel.

**Architecture:** Description strings change in place on the existing property definitions. The reset is one internal operator in `addon/operators/ui_actions.py` that calls Blender's native `property_unset()` for each analysis setting, so defaults are never duplicated, then marks the report dirty and clears review exactly as the `update=_settings_changed` callback does. A shared name tuple in `addon/properties.py` is the single source of truth for which settings the reset covers.

**Tech Stack:** Python 3.13, Blender 5.2 RNA/operators/UI, existing headless Blender runner.

**Design approval:** The tooltip copy and the scope were presented and approved in
conversation on 2026-08-05. The design is recorded inline here rather than in a
separate spec because the change is narrow and entirely described by this plan.

## Global Constraints

- Target Blender 5.2 LTS; manifest stays `1.1.0` and `API_VERSION` stays `(1, 2)`.
- Keep the `# SPDX-License-Identifier: GPL-3.0-or-later` header on every file.
- Keep user copy to one sentence per Blender label.
- Scope is the seven settings drawn by `ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings`:
  `alpha_threshold`, `min_affected_texels`, `min_affected_fraction`,
  `margin_texels`, `address_mode`, `max_scanlines`, `max_run_emissions`.
- Do not touch Apply policies, Inspect Classes, Manual Alpha Sources, or the
  shared `ADDRESS_MODE_ITEMS` item tooltips in `addon/overrides.py`.
- Do not change any default value, classification behavior, or analysis result.
- The reset must not silently leave a stale report looking valid.
- Add no dependency and no public operator; the reset is `INTERNAL`.
- Never commit `.local-references/`, `.packaged-releases/`, `.test-output/`, or `__pycache__/`.

Commands used throughout:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
```

---

### Task 1: Rewrite the seven tooltips

**Files:**
- Create: `tests/blender/test_expert_analysis_settings.py`
- Modify: `tests/blender/run_all.py`
- Modify: `addon/properties.py:113-165`

**Interfaces:**
- Consumes: `bpy.context.window_manager.alpha_material_separator_settings`.
- Produces: `ANALYSIS_SETTING_NAMES` in `addon/properties.py`, a tuple of the
  seven property names in panel order; `run()` in the new test module, imported
  by `run_all.py` as `run_expert_analysis_settings_tests`.

- [ ] **Step 1: Add the shared name tuple**

At module level in `addon/properties.py`, directly above
`class ALPHA_MATERIAL_SEPARATOR_PG_settings`, add:

```python
ANALYSIS_SETTING_NAMES = (
    "alpha_threshold",
    "min_affected_texels",
    "min_affected_fraction",
    "margin_texels",
    "address_mode",
    "max_scanlines",
    "max_run_emissions",
)
```

- [ ] **Step 2: Write the failing tooltip test**

Create `tests/blender/test_expert_analysis_settings.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""Expert Analysis Settings copy and reset behavior."""

from __future__ import annotations

import bpy

from addon import runtime
from addon.properties import ANALYSIS_SETTING_NAMES

EXPECTED_DESCRIPTIONS = {
    "alpha_threshold": (
        "How opaque a texture pixel must be to count as solid — pixels with "
        "alpha below this are treated as transparent"
    ),
    "min_affected_texels": (
        "How many transparent texture pixels a face must touch before it needs "
        "alpha; raise this to ignore faces that clip only a few stray pixels"
    ),
    "min_affected_fraction": (
        "What share of a face's texture area must be transparent before it "
        "needs alpha, from 0 to 1, where 0 turns this check off"
    ),
    "margin_texels": (
        "Also check this many texture pixels beyond each face's UV outline, "
        "which catches transparency that texture filtering and mipmaps pull in "
        "when rendering"
    ),
    "address_mode": (
        "How the texture behaves outside its 0–1 UV tile when a face's UVs run "
        "past the image edge"
    ),
    "max_scanlines": (
        "Safety cap on how many texture pixel rows one face may scan, so an "
        "extreme face is reported as unanalyzed instead of guessed at"
    ),
    "max_run_emissions": (
        "Safety cap on how many horizontal pixel spans one face may produce, "
        "so an extreme face is reported as unanalyzed instead of guessed at"
    ),
}


def _settings():
    return bpy.context.window_manager.alpha_material_separator_settings


def _assert_names_cover_the_panel() -> None:
    assert set(ANALYSIS_SETTING_NAMES) == set(EXPECTED_DESCRIPTIONS), (
        set(ANALYSIS_SETTING_NAMES) ^ set(EXPECTED_DESCRIPTIONS)
    )


def _assert_descriptions_are_artist_readable() -> None:
    properties = _settings().bl_rna.properties
    for name, expected in EXPECTED_DESCRIPTIONS.items():
        actual = properties[name].description
        assert actual == expected, f"{name}: {actual!r}"


def run() -> None:
    _assert_names_cover_the_panel()
    _assert_descriptions_are_artist_readable()
    print("ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK")
```

- [ ] **Step 3: Register the module in the headless runner**

In `tests/blender/run_all.py`, add beside the other test imports:

```python
from tests.blender.test_expert_analysis_settings import (  # noqa: E402
    run as run_expert_analysis_settings_tests,
)
```

Add this call inside the `if iteration == 0:` block, after
`run_significance_settings_tests()`:

```python
            run_expert_analysis_settings_tests()
```

- [ ] **Step 4: Run the headless suite and confirm RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL in `_assert_descriptions_are_artist_readable` on
`alpha_threshold`, reporting the current terse description.

- [ ] **Step 5: Rewrite the seven descriptions**

In `addon/properties.py`, replace only the `description=` value of each of the
seven properties with the matching string from `EXPECTED_DESCRIPTIONS` above.
Change nothing else: names, defaults, limits, precision, and `update=`
callbacks all stay exactly as they are.

- [ ] **Step 6: Run the headless suite and confirm GREEN**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: exit code 0 including
`ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK`.

- [ ] **Step 7: Run the unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: PASS, 95 tests.

- [ ] **Step 8: Commit**

```bash
git add addon/properties.py tests/blender/test_expert_analysis_settings.py tests/blender/run_all.py
git commit -m "docs: explain the Expert analysis settings in artist language"
```

---

### Task 2: Add the Reset to Default Values button

**Files:**
- Modify: `tests/blender/test_expert_analysis_settings.py`
- Modify: `addon/operators/ui_actions.py`
- Modify: `addon/registration.py:15-19,21-41`
- Modify: `addon/panel.py:557-569`

**Interfaces:**
- Consumes: `ANALYSIS_SETTING_NAMES` from `addon.properties`; `runtime.mark_dirty`, `runtime.clear_review`.
- Produces: `ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings` with
  `bl_idname = "alpha_material_separator.reset_analysis_settings"`.

- [ ] **Step 1: Write the failing reset test**

`runtime.mark_dirty` returns without effect when no report exists, so this test
must analyze a real fixture before it can prove anything about invalidation.
Add these imports to `tests/blender/test_expert_analysis_settings.py`:

```python
from tests.blender.test_analysis_preview import (
    _clear_scene,
    _image,
    _material,
    _quad,
)
```

Append the helpers below, and call `_assert_reset_behavior()` in `run()`
before the print:

```python
def _defaults():
    properties = _settings().bl_rna.properties
    return {name: properties[name].default for name in ANALYSIS_SETTING_NAMES}


def _analyze_clean_report() -> None:
    result = bpy.ops.alpha_material_separator.analyze()
    assert result == {"FINISHED"}, result
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )


def _assert_reset_behavior() -> None:
    _clear_scene()
    image = _image("AMS_RESET_IMAGE")
    material, _tree, _principled, _texture = _material("AMS_RESET_SOURCE", image)
    _quad("AMS_RESET_OBJECT", material)
    settings = _settings()
    defaults = _defaults()

    # A reset that changes nothing must not invalidate a valid report.
    _analyze_clean_report()
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    assert runtime.validation_state() == runtime.VALIDATION_CLEAN, (
        runtime.validation_state()
    )

    # A reset that restores changed values must mark the report stale.
    settings.alpha_threshold = 0.5
    settings.min_affected_texels = 7
    settings.min_affected_fraction = 0.25
    settings.margin_texels = 3
    settings.address_mode = "CLIP"
    settings.max_scanlines = 12
    settings.max_run_emissions = 34
    for name in ANALYSIS_SETTING_NAMES:
        assert getattr(settings, name) != defaults[name], name

    _analyze_clean_report()
    result = bpy.ops.alpha_material_separator.reset_analysis_settings()
    assert result == {"FINISHED"}, result
    for name in ANALYSIS_SETTING_NAMES:
        assert getattr(settings, name) == defaults[name], name
    assert runtime.validation_state() == runtime.VALIDATION_STALE, (
        runtime.validation_state()
    )
    assert runtime.dirty_reason() == "SETTINGS_CHANGED", runtime.dirty_reason()

    _clear_scene()
```

`runtime.VALIDATION_CLEAN` and `runtime.VALIDATION_STALE` are confirmed to
exist at `addon/runtime.py:25-27`, and `_material` is confirmed to return
`(material, tree, principled, texture)`.

- [ ] **Step 2: Run the headless suite and confirm RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL because
`bpy.ops.alpha_material_separator.reset_analysis_settings` does not exist.

- [ ] **Step 3: Add the operator**

In `addon/operators/ui_actions.py`, add the import beside the existing ones:

```python
from ..properties import ANALYSIS_SETTING_NAMES
```

Then append this class:

```python
class ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings(bpy.types.Operator):
    bl_idname = "alpha_material_separator.reset_analysis_settings"
    bl_label = "Reset to Default Values"
    bl_description = "Restore every Expert analysis setting to its default value"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        settings = context.window_manager.alpha_material_separator_settings
        before = tuple(getattr(settings, name) for name in ANALYSIS_SETTING_NAMES)
        for name in ANALYSIS_SETTING_NAMES:
            settings.property_unset(name)
        after = tuple(getattr(settings, name) for name in ANALYSIS_SETTING_NAMES)
        if before != after:
            runtime.mark_dirty("SETTINGS_CHANGED")
            runtime.clear_review(context.window_manager)
        return {"FINISHED"}
```

`property_unset()` restores the RNA default without duplicating any value here.
`mark_dirty` and `clear_review` are called explicitly because `property_unset()`
is not guaranteed to fire the `update=` callback, matching how
`ALPHA_MATERIAL_SEPARATOR_OT_add_override` already marks dirty by hand.

The before/after comparison keeps a reset that changes nothing from
invalidating a completed analysis, which would otherwise force a needless
re-analysis of a large mesh after an idle click.

- [ ] **Step 4: Register the operator**

In `addon/registration.py`, extend the `ui_actions` import:

```python
from .operators.ui_actions import (
    ALPHA_MATERIAL_SEPARATOR_OT_add_override,
    ALPHA_MATERIAL_SEPARATOR_OT_cancel_analysis,
    ALPHA_MATERIAL_SEPARATOR_OT_remove_override,
    ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings,
)
```

Then add to `_CLASSES`, after `ALPHA_MATERIAL_SEPARATOR_OT_remove_override`:

```python
    ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings,
```

- [ ] **Step 5: Add the panel button**

In `addon/panel.py`, in
`ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings.draw`, after
`limits.prop(settings, "max_run_emissions")`, append at the panel level:

```python
        layout.operator(
            "alpha_material_separator.reset_analysis_settings",
            text="Reset to Default Values",
            icon="LOOP_BACK",
        )
```

- [ ] **Step 6: Run the headless suite and confirm GREEN**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: exit code 0 with every marker. The `assert_unregistered()` check in
`run_all.py` must still pass, proving the new operator unregisters cleanly.

- [ ] **Step 7: Run the complete change gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$Archive = (Resolve-Path .\.packaged-releases\alpha_material_separator-1.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Expected: all pass.

- [ ] **Step 8: Update the handoff and commit**

Record the new operator, the rewritten copy, and the still-outstanding
interactive acceptance in `docs/HANDOFF.md`.

```bash
git add addon/operators/ui_actions.py addon/registration.py addon/panel.py tests/blender/test_expert_analysis_settings.py docs/HANDOFF.md
git commit -m "feat: reset Expert analysis settings to their defaults"
```

---

## Remaining acceptance, not covered by this plan

- [ ] Hover each of the seven settings in a real Blender 5.2 session and confirm
      the tooltip reads well at the panel's width.
- [ ] Press Reset to Default Values with an existing analysis and confirm the
      panel reports that inputs changed.
