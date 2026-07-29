# Repository handoff

Updated: 2026-07-29

## Current objective

Finish Blender Alpha Material Separator 0.1 release acceptance. The optional
Preview workflow is implemented: any current actionable analysis enables Apply,
while guided Apply without an exact matching Preview always opens the existing
confirmation dialog.

## Completed work

- `bc631e6 feat: make face preview optional`
  - Apply availability no longer depends on a review token.
  - The panel describes Preview as optional.
  - Confirmation presentation can add `Faces have not been previewed.`
- `a6ee3f0 feat: confirm unpreviewed material assignment`
  - Guided unpreviewed Apply always confirms, including clean supported plans.
  - Exact reviewed plans retain the existing warning-only behavior.
  - Scripted invocation/execution compatibility and authoritative mutation
    validation remain unchanged.
- README, integration API, testing documentation, and generated documentation
  contracts now describe the optional workflow.
- The ignored private multi-object helper now checks unpreviewed availability,
  confirmation cancellation with zero mutation, exact Preview/Apply agreement,
  preservation, and the established semantic lower bound.
- The extension ZIP was rebuilt, validated, installed into an isolated Blender
  profile, and exercised against the lawful 48-mesh stress example.

## Important decisions and constraints

- Preview is recommended but optional.
- Apply without a matching exact-plan Preview always asks for confirmation.
- Stale, running, non-actionable, or no-change reports still disable Apply.
- The review token affects confirmation only; it is not an assignment
  authorization boundary.
- Assignment still revalidates authoritative inputs and the complete plan
  fingerprint before mutation.
- Preserve version `0.1.0`, API `1.2`, operator IDs, public payloads, undo,
  rollback, idempotence, and the no-topology-change guarantee.
- Keep the branch as-is. Do not push or alter the gone upstream without user
  approval.
- The user approved the clarified `AGENTS.md` repository workflow guidance,
  including proportional plugin use, testing scope, private-path handling, and
  change-versus-release completion gates.

## Files changed and why

- `addon/presentation.py`: optional-Preview Apply state and confirmation copy.
- `addon/panel.py`: optional Preview guidance.
- `addon/operators/assign_materials.py`: detect exact reviewed plans during
  guided invocation and force confirmation otherwise.
- `tests/unit/test_presentation.py`: workflow and confirmation-copy regressions.
- `tests/blender/test_assignment_policies.py`: generated clean-plan
  unpreviewed/reviewed/scripted confirmation behavior.
- `tests/blender/test_revalidation_matrix.py`: assignment-only changes retain
  analysis but invalidate exact review.
- `README.md`, `docs/integration-api.md`, `docs/testing.md`: end-user,
  integration, and acceptance behavior.
- `tests/unit/test_readme_contract.py`: exact documentation contract.
- `docs/superpowers/specs/2026-07-29-optional-preview-confirmation-design.md` and
  `docs/superpowers/plans/2026-07-29-optional-preview-confirmation.md`: approved
  design, execution plan, and progress evidence.
- Ignored only: `.local-references/default-example/_validate_analysis.py`,
  `.packaged-releases/alpha_material_separator-0.1.0.zip`, and isolated test
  profile/output.

## Validation commands and results

RED evidence:

```powershell
& $Python52 -m unittest tests.unit.test_presentation -v
```

Failed as intended because unreviewed actionable state disabled Apply and
`assignment_confirmation_lines()` did not accept `previewed`.

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Failed as intended because the generated clean unpreviewed plan executed
without opening a dialog.

```powershell
& $Python52 -m unittest tests.unit.test_readme_contract -v
```

Failed as intended because the approved optional-Preview phrases were absent.

GREEN gate:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Results: 51/51 unit tests passed. The complete headless Blender suite passed
through `BLENDER_TESTS_OK`, including analysis/preview, assignment policy,
identity, FBX, preservation, UX, revalidation, characterization, lifecycle, and
simplification contracts. Source validation passed. `git diff --check` found no
whitespace errors; only established LF/CRLF notices were emitted.

Private smoke:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

The unpreviewed cancel, exact Preview/Apply plan, addressing, and preservation
checks passed. The command ended nonzero only on the established lower-bound
discrepancy: 1,176 reference-alpha faces still classify as `OPAQUE`. The planned
and applied set remained 65,773 faces, so this patch introduced no regression.
Neither private file was saved or modified.

Packaging:

```powershell
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate $Archive
Get-Item -LiteralPath $Archive | Select-Object FullName,Length
Get-FileHash -Algorithm SHA256 $Archive
```

Archive validation passed. Ignored package:
`.packaged-releases/alpha_material_separator-0.1.0.zip`, 65,225 bytes,
SHA-256 `59E4400FEABE680CD60C4019A0BB7C6F7ADFE73347B62AC259813BAE120C5B1F`.

Installed-ZIP acceptance used an isolated Blender profile with config, scripts,
extensions, and datafiles redirected under `.test-output`. Installation and
enablement passed. On the 48-mesh private example, Analyze completed; Preview
and Apply were both enabled before review; the panel displayed the optional
guidance; unpreviewed Apply opened a dialog beginning `Faces have not been
previewed.` with matching aggregate counts; Cancel returned to the same active
report. No Apply mutation or save was performed in that interactive session.

## Known failures, warnings, and unverified assumptions

- The 1,176-face private semantic lower-bound discrepancy remains open and is
  unrelated to optional Preview.
- Confirmed unpreviewed Apply, Ctrl+Z, and exact-Preview Apply were covered by
  generated tests and the private helper but were not all manually repeated
  from this rebuilt installed ZIP.
- The generated interactive two-material partial-apply check and distinct final
  Apply-preflight timing remain open.
- Ordinary Unity material/submesh validation remains a release requirement.
  VRChat evidence applies only to the exact tested stack.
- Expected warnings remain limited to Blender's bundled Grease Pencil
  brush-path warning, deliberately exercised stale-input warnings, and Git
  line-ending notices.

## Remaining tasks

1. Investigate the private `OPAQUE` lower-bound misses using ignored anonymized
   diagnostics and a generated failing regression before any production fix.
2. Complete the remaining installed-ZIP interaction checks if strict release
   sign-off is desired: confirm unpreviewed Apply, Ctrl+Z, and exact-Preview
   Apply.
3. Complete the interactive two-material partial-apply and final-preflight
   timing checks.
4. Record user-performed ordinary Unity material/submesh acceptance.

## Recommended next action

Investigate the 1,176 private reference-alpha faces that still classify as
`OPAQUE`, starting with ignored anonymized diagnostics and then a generated
failing regression before changing production code.
