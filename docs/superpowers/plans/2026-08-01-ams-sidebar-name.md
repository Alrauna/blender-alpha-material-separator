# AMS Sidebar Name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the Blender 3D View sidebar tab from **Alpha Material** to
**AMS** and make current README location instructions match.

**Architecture:** Use Blender's existing native `Panel.bl_category` declarations;
no new state or abstraction is needed. Protect the registered UI category and
README wording with the existing Blender lifecycle and README contract tests.

**Tech Stack:** Blender 5.2 Python API, Python `unittest`, Blender extension CLI.

## Global Constraints

- Change only the standalone sidebar/tab name **Alpha Material** to **AMS**.
- Preserve **Blender Alpha Material Separator**, **Alpha Material Separator**,
  operator labels, extension ID, package name, API, panel behavior, and layout.
- Update current README sidebar references, including the screenshot alt text
  and 3D View location instruction.
- Do not rewrite historical implementation plans that record the previous UI
  name.
- Preserve the existing uncommitted `docs/HANDOFF.md` memory-audit update and
  keep it out of the implementation commit.
- Do not run the private before/after smoke; this is presentation-only and does
  not alter assignment-plan data.
- Do not push.

---

### Task 1: Rename the native sidebar category and current instructions

**Files:**
- Modify: `tests/unit/test_readme_contract.py`
- Modify: `tests/blender/run_all.py`
- Modify: `addon/panel.py:219`
- Modify: `addon/panel.py:543`
- Modify: `README.md:14`
- Modify: `README.md:23`

**Interfaces:**
- Consumes: Blender's native `bpy.types.Panel.bl_category` registration field.
- Produces: registered main and Expert child panels in the `AMS` sidebar tab;
  README instructions that direct users to that exact tab.

- [x] **Step 1: Write the failing README contract**

Replace the standalone `"Alpha Material"` location expectation in
`test_guided_workflow_labels_and_location_are_exact` with the exact current
instruction fragment:

```python
"open the **AMS** tab",
```

Keep the existing workflow-label expectations unchanged.

- [x] **Step 2: Run the README contract and verify RED**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_readme_contract.ReadmeContractTests.test_guided_workflow_labels_and_location_are_exact `
  -v
```

Expected: FAIL because the README still says
`open the **Alpha Material** tab`.

- [x] **Step 3: Write the failing registered-panel contract**

In `tests/blender/run_all.py`, immediately after the existing registration
assertion for `ALPHA_MATERIAL_SEPARATOR_PT_main`, add:

```python
assert (
    bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_main.bl_category == "AMS"
)
assert (
    bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_analysis_settings.bl_category
    == "AMS"
)
```

The main assertion checks the top-level panel declaration. The child assertion
checks that Expert panels inherit the same category.

- [x] **Step 4: Run the Blender lifecycle test and verify RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL because the registered category is still `Alpha Material`.

- [x] **Step 5: Make the minimal production and README changes**

In both category declarations in `addon/panel.py`, use:

```python
bl_category = "AMS"
```

In `README.md`, change only the two standalone sidebar references:

```markdown
![The Simple interface in Blender's AMS sidebar](docs/images/01-panel-simple.png)
```

```markdown
5. Return to a 3D View, press `N`, and open the **AMS** tab.
```

Do not change any occurrence of **Alpha Material Separator**.

- [x] **Step 6: Run focused GREEN checks**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_readme_contract.ReadmeContractTests.test_guided_workflow_labels_and_location_are_exact `
  -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: the focused README test passes and Blender prints
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [x] **Step 7: Run the complete change gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Expected: 51 unit tests pass, Blender prints
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, source and archive validation
succeed, and `git diff --check` reports no errors.

- [x] **Step 8: Review and commit the scoped implementation**

Inspect only the intended implementation paths:

```powershell
git diff -- `
  addon/panel.py `
  README.md `
  tests/unit/test_readme_contract.py `
  tests/blender/run_all.py
```

Stage and commit only those paths:

```powershell
git add -- `
  addon/panel.py `
  README.md `
  tests/unit/test_readme_contract.py `
  tests/blender/run_all.py
git diff --cached --check
git commit -m "ui: rename sidebar tab to AMS"
```

- [x] **Step 9: Update handoff status without mixing commit scopes**

Update `docs/HANDOFF.md` to record:

- the new local implementation commit;
- the focused RED/GREEN evidence;
- complete unit, Blender, source, and archive results;
- the rebuilt archive size and SHA-256;
- that the private smoke was intentionally not run because no assignment-plan
  data changed.

Keep this handoff update separate from the implementation commit so the
existing memory-audit material is not silently bundled into the UI change.
