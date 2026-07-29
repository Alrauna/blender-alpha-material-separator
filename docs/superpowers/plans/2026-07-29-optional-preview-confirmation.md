# Optional Preview with Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Apply after any current actionable analysis while requiring the existing confirmation dialog when the exact assignment plan has not been previewed.

**Architecture:** Keep the review token as evidence that the exact current plan was visually previewed, but remove it from button availability. Reuse the existing confirmation builder and assignment operator: guided UI invocations with no matching token force confirmation, while authoritative report validation, plan fingerprint checks, transactional mutation, and direct scripted execution remain unchanged.

**Tech Stack:** Python 3.11, Blender 5.2 RNA/operators/UI, existing pure-Python presentation helpers, `unittest`, existing headless Blender runner.

## Global Constraints

- Preserve extension version `0.1.0`, API `1.2`, public operator IDs, arguments, classifications, policies, payloads, and mutation scope.
- Preview remains available and is recommended, but it is not required to enable Apply.
- An unpreviewed guided-UI plan always requires confirmation before mutation.
- A matching exact Preview retains the current warning-only confirmation behavior.
- Running, stale, and non-actionable states continue to disable Apply.
- Preserve authoritative validation, complete assignment-plan fingerprints, confirmation preflight checks, atomic undo, rollback, and idempotence.
- Direct scripted `execute()` remains compatible without a preview token.
- A scripted `invoke()` without the guided UI's expected review signature retains its current confirmation behavior.
- Add no public operator, preference, persistent setting, RNA property, dependency, or alternate dialog.
- Use the existing `runtime.review_matches()` token and `assignment_confirmation_lines()` presentation path.
- Keep user copy to one sentence per Blender label.
- Do not stage or commit the existing unrelated `AGENTS.md` modification.
- Run the private default-example smoke because this changes Preview/Apply workflow behavior; never commit its files, helper, names, or raw output.
- Rebuild and validate the ignored extension ZIP.

---

### Task 1: Enable Apply and Present the Unpreviewed Warning

**Files:**
- Modify: `addon/presentation.py:190-255,335-367`
- Modify: `addon/panel.py:501-526`
- Test: `tests/unit/test_presentation.py:251-312`

**Interfaces:**
- Changes: `assignment_confirmation_lines(plan_payload: dict, *, previewed: bool = True) -> tuple[str, ...]`
- Preserves: `workflow_view(...) -> dict[str, object]`
- Produces: `can_apply=True` for every current actionable report, independent of `reviewed`
- Produces: first confirmation sentence `Faces have not been previewed.` when `previewed=False`

- [ ] **Step 1: Add failing pure-Python workflow and copy regressions**

Extend `test_workflow_states()`:

```python
        ready_without_preview = workflow_view(
            eligible_objects=1,
            running=False,
            has_report=True,
            stale=False,
            reviewed=False,
            actionable=True,
            completed=False,
        )
        self.assertEqual(ready_without_preview["state"], "READY_TO_REVIEW")
        self.assertTrue(ready_without_preview["can_preview"])
        self.assertTrue(ready_without_preview["can_apply"])
```

Extend the existing compact confirmation test using its representative
`plan_payload`:

```python
        reviewed_lines = assignment_confirmation_lines(
            plan_payload,
            previewed=True,
        )
        unpreviewed_lines = assignment_confirmation_lines(
            plan_payload,
            previewed=False,
        )
        self.assertEqual(
            unpreviewed_lines,
            ("Faces have not been previewed.", *reviewed_lines),
        )
        self.assertEqual(
            assignment_confirmation_lines(plan_payload),
            reviewed_lines,
        )
```

The default-argument assertion protects all existing callers and public-facing
copy when Preview has already occurred.

- [ ] **Step 2: Run the focused unit tests and verify RED**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_presentation -v
```

Expected: fail because unreviewed actionable state currently has
`can_apply=False`, and `assignment_confirmation_lines()` does not accept the
`previewed` keyword.

- [ ] **Step 3: Implement the minimal presentation behavior**

Change the confirmation signature and initialize its lines:

```python
def assignment_confirmation_lines(
    plan_payload: dict,
    *,
    previewed: bool = True,
) -> tuple[str, ...]:
    """Describe only the aggregate consequences of an assignment plan."""

    # Existing count extraction remains unchanged.
    lines = [] if previewed else ["Faces have not been previewed."]
```

Change only the `can_apply` expression in `workflow_view()`:

```python
        "can_apply": has_report and actionable and not running and not stale,
```

In the Apply panel, replace the mandatory instruction:

```python
            if not reviewed and actionable and not stale:
                assignment.label(
                    text="Preview is optional; use it to inspect faces before applying.",
                    icon="INFO",
                )
```

Keep the existing `expected_review_signature` assignment on the operator. It is
needed to distinguish the exact current plan in Task 2.

- [ ] **Step 4: Run focused and complete unit tests and verify GREEN**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_presentation -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: presentation tests pass, then every discovered unit test passes.

- [ ] **Step 5: Commit the independently tested presentation boundary**

Run:

```powershell
git add addon/presentation.py addon/panel.py tests/unit/test_presentation.py
git diff --cached --check
git commit -m "feat: make face preview optional"
```

Expected: only presentation state, panel copy, and their unit regressions are
committed. `AGENTS.md` remains unstaged.

---

### Task 2: Force Confirmation for an Unpreviewed Guided Plan

**Files:**
- Modify: `addon/operators/assign_materials.py:102-242`
- Test: `tests/blender/test_assignment_policies.py:33-55,110-348`
- Test: `tests/blender/test_revalidation_matrix.py:115-186`

**Interfaces:**
- Consumes: `runtime.review_matches(window_manager, analysis_id, policy_signature) -> bool`
- Consumes: `assignment_confirmation_lines(plan_payload, previewed=...)`
- Produces: private operator attribute `_confirmation_previewed: bool`
- Preserves: `expected_review_signature`, `_confirmation_plan_signature`, and all public RNA

- [ ] **Step 1: Add a generated clean-plan fixture**

In `tests/blender/test_assignment_policies.py`, add:

```python
def _fully_alpha_image(name):
    image = bpy.data.images.new(name, width=1, height=1, alpha=True)
    image.pixels.foreach_set((1.0, 1.0, 1.0, 0.0))
    return image
```

Inside `run()`, create a clean plan after the existing confirmation-width
assertions:

```python
    _clear_scene()
    clean_image = _fully_alpha_image("AMS_UNPREVIEWED_IMAGE")
    clean_material, _tree, _principled, _texture = _material(
        "AMS_UNPREVIEWED_SOURCE",
        clean_image,
    )
    clean_object = _quad("AMS_UNPREVIEWED_OBJECT", clean_material)
    clean_analysis_id = _analyze(clean_object)
    clean_report = runtime.report(clean_analysis_id)
    clean_plan = build_assignment_plan(
        clean_report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    clean_payload = clean_plan.public_payload()
    assert clean_payload["faces_to_reassign"] == 1, clean_payload
    assert not clean_plan.has_skips, clean_payload
```

This produces one supported `ALPHA_AFFECTED` face, so the current
`requires_confirmation()` result is false.

- [ ] **Step 2: Add the failing unpreviewed-invoke regression**

Construct the same lightweight operator shape already used by this test:

```python
    clean_signature = review_signature(
        clean_analysis_id,
        "TO_ALPHA",
        "CANCEL_SOURCE_MATERIAL",
        "TO_ALPHA",
        "CANCEL_SOURCE_MATERIAL",
        clean_payload,
    )
    runtime.clear_review(bpy.context.window_manager)
    clean_dialog_manager = _CancelledDialogWindowManager(
        bpy.context.window_manager
    )
    clean_operator = SimpleNamespace(
        api_major=1,
        expected_analysis_id=clean_analysis_id,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        expected_review_signature=clean_signature,
        _confirmation_plan_signature="",
        _confirmation_plan_json="{}",
        _confirmation_previewed=True,
        _confirmation_draw_width=420,
        execute=lambda _context: {"EXECUTED_WITHOUT_DIALOG"},
    )
    cancelled = ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.invoke(
        clean_operator,
        SimpleNamespace(
            window_manager=clean_dialog_manager,
            object=bpy.context.object,
            window=SimpleNamespace(width=1920),
        ),
        None,
    )
    assert cancelled == {"CANCELLED"}, cancelled
    assert clean_dialog_manager.options is not None
    assert clean_operator._confirmation_previewed is False
    assert tuple(
        polygon.material_index for polygon in clean_object.data.polygons
    ) == (0,)
```

Draw the recorded dialog and assert its first complete sentence:

```python
    clean_draw = _DialogRecordingLayout()
    clean_operator.layout = clean_draw
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.draw(
        clean_operator,
        SimpleNamespace(region=SimpleNamespace(type="WINDOW", width=420)),
    )
    clean_draw_text = [text for text, _icon in clean_draw.labels]
    assert clean_draw_text[0] == "Faces have not been previewed."
```

- [ ] **Step 3: Add the reviewed clean-plan compatibility regression**

Record the exact token and invoke the same clean plan again:

```python
    runtime.set_review(
        bpy.context.window_manager,
        clean_analysis_id,
        clean_signature,
    )
    reviewed_operator = SimpleNamespace(
        api_major=1,
        expected_analysis_id=clean_analysis_id,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        expected_review_signature=clean_signature,
        _confirmation_plan_signature="",
        _confirmation_plan_json="{}",
        _confirmation_previewed=False,
        _confirmation_draw_width=420,
        execute=lambda _context: {"FINISHED"},
    )
    reviewed = ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.invoke(
        reviewed_operator,
        SimpleNamespace(
            window_manager=bpy.context.window_manager,
            object=bpy.context.object,
            window=SimpleNamespace(width=1920),
        ),
        None,
    )
    assert reviewed == {"FINISHED"}, reviewed
```

Prove that a scripted invocation without the guided UI signature retains its
current behavior:

```python
    runtime.clear_review(bpy.context.window_manager)
    scripted_operator = SimpleNamespace(
        api_major=1,
        expected_analysis_id=clean_analysis_id,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        expected_review_signature="",
        _confirmation_plan_signature="",
        _confirmation_plan_json="{}",
        _confirmation_previewed=False,
        _confirmation_draw_width=420,
        execute=lambda _context: {"FINISHED"},
    )
    scripted = ALPHA_MATERIAL_SEPARATOR_OT_assign_materials.invoke(
        scripted_operator,
        SimpleNamespace(
            window_manager=bpy.context.window_manager,
            object=bpy.context.object,
            window=SimpleNamespace(width=1920),
        ),
        None,
    )
    assert scripted == {"FINISHED"}, scripted
```

Finally, exercise the real direct execution path used after dialog
confirmation:

```python
    confirmed = bpy.ops.alpha_material_separator.assign_materials(
        expected_analysis_id=clean_analysis_id,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert confirmed == {"FINISHED"}, confirmed
    assert tuple(
        polygon.material_index for polygon in clean_object.data.polygons
    ) == (1,)
```

Retain the existing warning-plan dialog test. Its token state and confirmation
copy must continue to pass.

- [ ] **Step 4: Run the headless Blender suite and verify RED**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: the clean unpreviewed invocation returns
`EXECUTED_WITHOUT_DIALOG`, proving that the existing operator does not yet force
confirmation. Confirm no earlier unrelated failure hides this expected result.

- [ ] **Step 5: Implement the smallest operator change**

Add one private non-RNA attribute beside the existing confirmation state:

```python
    _confirmation_previewed = True
```

In `invoke()`, after `_validated_plan()` returns:

```python
        report, plan, plan_payload = prepared
        previewed = (
            not self.expected_review_signature
            or runtime.review_matches(
                context.window_manager,
                report.analysis_id,
                self.expected_review_signature,
            )
        )
        self._confirmation_previewed = previewed
        actionable = plan.actionable
        if not actionable:
            return self.execute(context)
        if previewed and not requires_confirmation(
            report.public_payload(),
            plan_payload,
        ):
            return self.execute(context)
        lines = assignment_confirmation_lines(
            plan_payload,
            previewed=previewed,
        )
```

Delete the old unconditional `report_payload` local and old
`if not requires_confirmation(...)` branch. Keep confirmation width, plan JSON,
plan signature, and `invoke_props_dialog()` unchanged.

In `draw()`:

```python
        lines = assignment_confirmation_lines(
            plan,
            previewed=self._confirmation_previewed,
        )
```

Do not check or consume the token in `execute()`. The existing authoritative
validation and expected signature comparison remain the mutation boundary.

- [ ] **Step 6: Extend state-transition assertions**

In `tests/blender/test_revalidation_matrix.py`, retain the existing proof that
selection and mode transitions preserve the token. Add assertions after the
existing assignment-only review invalidation case:

```python
    assert runtime.report(analysis_id) is report
    assert not runtime.review_matches(
        bpy.context.window_manager,
        analysis_id,
        review_token,
    )
```

Use `workflow_view()` in the existing presentation test—not duplicated Blender
panel logic—to prove that this valid actionable state still enables Apply.
Keep existing stale-input assertions proving that a real classification change
blocks mutation.

- [ ] **Step 7: Run the headless Blender suite and verify GREEN**

Run the Step 4 command again.

Expected: complete suite passes, including
`ASSIGNMENT_POLICY_TESTS_OK`, `REVALIDATION_MATRIX_TESTS_OK`, and
`BLENDER_TESTS_OK`.

- [ ] **Step 8: Commit the operator behavior**

Run:

```powershell
git add addon/operators/assign_materials.py `
  tests/blender/test_assignment_policies.py `
  tests/blender/test_revalidation_matrix.py
git diff --cached --check
git commit -m "feat: confirm unpreviewed material assignment"
```

Expected: only the assignment operator and generated Blender regressions are
committed.

---

### Task 3: Align Documentation and Validate the Installed Workflow

**Files:**
- Modify: `README.md:28-50,131-135,141-160,200-212`
- Modify: `docs/integration-api.md:121-132`
- Modify: `docs/testing.md:120-165`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/superpowers/plans/2026-07-29-optional-preview-confirmation.md`
- Ignored local helper: `.local-references/default-example/_validate_analysis.py`
- Generated ignored archive: `.packaged-releases/alpha_material_separator-0.1.0.zip`

**Interfaces:**
- Documents: optional Preview, forced unpreviewed confirmation, exact-token behavior
- Preserves: no-topology, stale-input, partial-apply, undo, and scripted API guarantees
- Produces: validated installable ZIP and exact continuation evidence

- [ ] **Step 1: Add failing documentation contracts**

In `tests/unit/test_readme_contract.py`, extend the workflow contract with exact
phrases:

```python
        self.assertIn("Preview is recommended but optional", self.readme)
        self.assertIn(
            "Apply without Preview always asks for confirmation",
            self.readme,
        )
        self.assertIn(
            "Assignment-only plan changes require confirmation, not another analysis",
            self.readme,
        )
```

Update any existing assertion that requires Preview before Apply so it expects
the optional workflow instead.

- [ ] **Step 2: Run the README contract and verify RED**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_readme_contract -v
```

Expected: fail because the approved optional-preview phrases are absent.

- [ ] **Step 3: Update end-user and integration documentation**

In the README's 60-second workflow:

1. Describe **Preview Faces to Move** as recommended but optional.
2. State that Apply without Preview always asks for confirmation.
3. State that a matching Preview lets a clean supported plan apply immediately.
4. Replace “use Preview again” after an assignment-only shader edit with
   “Apply asks for confirmation unless you Preview the revised plan.”

In `docs/integration-api.md`, replace “mandatory preview review token” with:

```markdown
The UI uses the exact-plan review token to decide whether confirmation is
mandatory. It does not gate direct scripted assignment: scripts still supply
the expected analysis ID, and assignment performs authoritative stale-input
validation.
```

In `docs/testing.md`, add separate installed-ZIP checks for:

- Apply enabled immediately after actionable analysis.
- unpreviewed clean plan opens confirmation;
- cancel causes zero mutation;
- confirmed unpreviewed plan applies and remains undoable;
- exact Preview preserves warning-only confirmation behavior;
- assignment-only plan changes force confirmation without reanalysis.

- [ ] **Step 4: Run documentation and full automated gates**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Expected: all unit tests pass, the complete Blender suite prints
`BLENDER_TESTS_OK`, source validation succeeds, and no whitespace error is
reported beyond known line-ending notices for unstaged `AGENTS.md`.

- [ ] **Step 5: Run the private default-example workflow smoke**

Update only the ignored helper so it exercises:

1. Analyze all eligible meshes in `before.blend`.
2. Prove the plan is current and actionable before Preview.
3. Prove the guided Apply state is enabled without a review token.
4. Cancel the unpreviewed confirmation and prove zero mutation.
5. Confirm the same exact plan and prove the applied face set equals the plan.
6. Undo, run Analyze again, Preview the exact plan, leave Edit Mode, and Apply
   through the existing warning flow.
7. Preserve the established lower-bound comparison and structural snapshots.

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

Expected: workflow and preservation gates pass. Existing separately recorded
`OPAQUE` lower-bound discrepancies may remain open but must not increase. Do not
record private names, paths, face sets, graph dumps, or raw output in committed
files.

- [ ] **Step 6: Rebuild and validate the ignored ZIP**

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

Expected: build and archive validation pass. Record exact size and SHA-256 in
`docs/HANDOFF.md`; never stage the archive.

- [ ] **Step 7: Perform installed-ZIP Blender 5.2 acceptance**

In the isolated Blender profile:

1. Install or reinstall the rebuilt ZIP.
2. Analyze a generated clean actionable mesh and confirm both Preview and Apply
   are enabled.
3. Click Apply without Preview and confirm the dialog begins with
   **Faces have not been previewed.**
4. Cancel and confirm no face, material, slot, or metadata change.
5. Reopen, confirm Apply, and verify the exact planned assignment.
6. Press Ctrl+Z and verify complete undo.
7. Analyze again, run Preview, and verify a clean plan applies without the
   unpreviewed warning.
8. Repeat on the lawful private messy example and confirm its existing warning
   summary, partial apply, completion summary, and undo remain correct.
9. Do not save the private file.

- [ ] **Step 8: Update handoff and plan status**

Record:

- RED and GREEN commands and exact outcomes;
- commits created;
- private smoke aggregate pass/failure without private details;
- source/archive validation results;
- archive size and SHA-256;
- installed-ZIP acceptance results and unverified interactions;
- remaining unrelated failures and the single recommended next action.

Mark only steps backed by executed evidence. Do not modify `AGENTS.md`.

- [ ] **Step 9: Commit documentation and validation evidence**

Run:

```powershell
git add README.md docs/integration-api.md docs/testing.md docs/HANDOFF.md `
  tests/unit/test_readme_contract.py `
  docs/superpowers/plans/2026-07-29-optional-preview-confirmation.md
git diff --cached --check
git commit -m "docs: document optional face preview workflow"
```

Expected: documentation, its contract, handoff, and plan status are committed.
Private files, test output, ZIPs, and `AGENTS.md` remain uncommitted or ignored.

- [ ] **Step 10: Report final local state**

Run:

```powershell
git status --short --branch
git log -6 --oneline
```

Expected: report every remaining uncommitted file accurately, state the package
path and validation status, keep the branch as-is, and confirm nothing was
pushed.
