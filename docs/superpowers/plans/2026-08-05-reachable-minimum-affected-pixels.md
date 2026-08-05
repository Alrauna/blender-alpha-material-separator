# Reachable Minimum Affected Pixels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every value of Minimum Affected Pixels do something, by raising the property's hard minimum from 0 to 1.

**Architecture:** Classification is unchanged. A face with no affected texels returns `OPAQUE` before the gate runs, so `affected` is always at least 1 there; the gate additionally treats 0 as off. That makes both 0 and 1 no-ops. Raising the RNA minimum to 1 removes the redundant value and leaves `1` as the honest "include any face with transparency" setting, with 2 and above as the real filter. The pure core keeps accepting 0 because it is a separate API where 0 documents "gate off".

**Tech Stack:** Python 3.13, Blender 5.2 RNA/operators, existing headless Blender runner.

**Design approval:** Approved in conversation on 2026-08-05.

## Global Constraints

- Target Blender 5.2 LTS; manifest stays `1.1.0` and `API_VERSION` stays `(1, 2)`.
- Change no classification arithmetic, gate comparison, or default value.
- Do not change `min_affected_fraction`; its `> 0.0` guard is correct because a
  fraction is continuous.
- Do not change `AnalysisSettings` in `addon/core/model.py`. The pure core keeps
  accepting 0, and
  `tests/unit/test_alpha_classification.py:test_texel_minimums_of_zero_and_one_never_suppress`
  must keep passing unchanged.
- Keep the `# SPDX-License-Identifier: GPL-3.0-or-later` header on every file.
- Never commit `.local-references/`, `.packaged-releases/`, `.test-output/`, or `__pycache__/`.

Commands used throughout:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
```

---

### Task 1: Raise the hard minimum to 1

**Files:**
- Modify: `tests/blender/test_expert_analysis_settings.py`
- Modify: `addon/properties.py:143`
- Modify: `addon/operators/analyze.py:71-73`

**Interfaces:**
- Consumes: `bpy.context.window_manager.alpha_material_separator_settings`;
  `bpy.ops.alpha_material_separator.analyze.get_rna_type()`.
- Produces: no new interface.

- [ ] **Step 1: Write the failing test**

Append this helper to `tests/blender/test_expert_analysis_settings.py` and call
`_assert_minimum_affected_pixels_is_reachable()` in `run()` immediately after
`_assert_descriptions_are_artist_readable()`:

```python
def _assert_minimum_affected_pixels_is_reachable() -> None:
    """0 and 1 were indistinguishable, so 0 is no longer offered.

    A face with no affected texels returns OPAQUE before the gate runs, so the
    gate can never see a value below 1. Offering 0 gave the setting two dead
    positions instead of one honest weakest filter.
    """
    settings = _settings()
    assert settings.bl_rna.properties["min_affected_texels"].hard_min == 1

    operator_rna = bpy.ops.alpha_material_separator.analyze.get_rna_type()
    assert operator_rna.properties["min_affected_texels"].hard_min == 1

    # Blender clamps rather than raising, which keeps older scripts working.
    settings.min_affected_texels = 0
    assert settings.min_affected_texels == 1, settings.min_affected_texels
    settings.property_unset("min_affected_texels")
```

- [ ] **Step 2: Run the headless suite and confirm RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL on the first assertion, because `hard_min` is still 0.

- [ ] **Step 3: Raise the settings minimum**

In `addon/properties.py`, in the `min_affected_texels` property, change:

```python
        min=0,
```

to:

```python
        min=1,
```

Change nothing else in that property. `default=1` already matches the new
minimum.

- [ ] **Step 4: Raise the operator minimum**

In `addon/operators/analyze.py`, replace:

```python
    min_affected_texels: IntProperty(
        name="Minimum Affected Texels", default=1, min=0
    )
```

with:

```python
    min_affected_texels: IntProperty(
        name="Minimum Affected Texels", default=1, min=1
    )
```

- [ ] **Step 5: Run the headless suite and confirm GREEN**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: exit code 0 with every marker, including
`ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK`.

- [ ] **Step 6: Run the complete change gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$Archive = (Resolve-Path .\.packaged-releases\alpha_material_separator-1.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Expected: 95 unit tests pass, source and archive validate, no whitespace errors.

- [ ] **Step 7: Update the handoff and commit**

Record the change in `docs/HANDOFF.md`.

```bash
git add addon/properties.py addon/operators/analyze.py tests/blender/test_expert_analysis_settings.py docs/HANDOFF.md
git commit -m "fix: make every Minimum Affected Pixels value meaningful"
```

---

## Remaining acceptance, not covered by this plan

- [ ] In a real Blender 5.2 session, confirm the Minimum Affected Pixels field
      will not go below 1 and that 2 still filters as expected.
