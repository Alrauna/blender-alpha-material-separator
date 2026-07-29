# Repository handoff

Updated: 2026-07-29

## Current objective

The Preview component-selection normalization milestone is complete. Preview
now clears stale vertex and edge flags on plan-target meshes before entering
face-select Edit Mode, so highlighted components derive from the reviewed face
plan. The next production investigation is the established private
1,176-face `OPAQUE` semantic lower-bound discrepancy.

## Completed work

- Reproduced the Preview noise through the real Analyze and Preview operators.
  The face plan was correct, but stale `MeshVertex.select` and
  `MeshEdge.select` flags survived.
- Added a generated three-face Blender regression with adjacent selected and
  opaque faces plus a disconnected opaque face.
- Covered `REPLACE`, `ADD`, `SUBTRACT`, repeated Preview from Edit Mode,
  multi-object Preview, skipped/non-target preservation, review-token
  retention, and `enter_edit_mode=False`.
- Fixed the shared operator path with target-only RNA selection normalization.
  No public API, classification, assignment, topology, or cache behavior
  changed.
- Extended the ignored default-example helper to reject selected components
  that belong only to unselected faces.
- Documented that a shared alpha/opaque boundary edge remains highlighted
  because it belongs to the selected face.
- Built and validated the installable extension ZIP.
- Completed an installed-ZIP Blender 5.2 interaction with a generated fixture:
  visual Preview was clean, repeated Preview was identical, and Apply created
  one derived slot and reassigned only the affected face.
- Created local implementation commit
  `cd21ebb fix: normalize preview component selection`.

## Important decisions and constraints

- Selection normalization applies only when Preview will enter Edit Mode and
  only to objects in the deterministic assignment plan.
- `enter_edit_mode=False` preserves existing vertex and edge selection flags.
- Skipped, unsafe, unrelated, and newly selected meshes remain untouched.
- Shared selected/unselected boundary components are expected Blender
  face-select behavior and must not be hidden.
- Material assignment remains authoritative from the reviewed polygon plan;
  it does not read edge or vertex selection.
- Version remains `0.1.0`; API remains `1.2`.
- The fix uses ordinary Blender RNA loops. The measured Preview regression is
  below the approved 25 percent same-machine limit, so no bulk-selection
  abstraction or BMesh production path was added.
- Private reference files and raw results remain ignored and uncommitted.
- Keep the current branch and do not push without explicit approval.

## Files changed and why

- `addon/operators/select_faces.py`: clears target mesh vertex and edge
  selection flags immediately before applying the final Preview polygon set.
- `tests/blender/test_analysis_preview.py`: generated real-operator regressions
  for face-derived component selection and compatibility boundaries.
- `README.md`: explains Preview component normalization and unavoidable shared
  boundaries.
- `docs/testing.md`: records the completed installed-ZIP interaction.
- `docs/superpowers/plans/2026-07-29-preview-component-selection-normalization.md`:
  records completed implementation-plan steps.
- `docs/HANDOFF.md`: replaces the stale pre-implementation status with current
  evidence and remaining work.
- Ignored only:
  `.local-references/default-example/_validate_analysis.py` was strengthened
  locally; the built ZIP and isolated acceptance profile remain under ignored
  directories.

## Validation commands and results

### TDD RED

Before the production change:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Result: failed in `_assert_face_derived_component_selection` with
`selected edge belongs only to unselected faces`. The expected polygon face
set already matched, isolating the defect to component flags.

### Preview timing

An ignored 50,000-polygon generated fixture used one discarded warm-up and
five measured Preview runs:

- Before: median `0.5657749000092736s`.
- After: median `0.6511920000048121s`.
- Change: +15.1 percent, below the approved 25 percent gate.

The profiler was deleted after use.

### Private default-example smoke

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

The new component-selection gate, exact Preview/Apply plan equivalence,
out-of-range UV addressing, assignment, preservation, and immutable-reference
checks passed. The command ended nonzero only for the unchanged established
1,176-face `OPAQUE` semantic lower-bound discrepancy. Planned and applied
faces remained 65,773.

### Complete change gate

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest discover -s tests/unit -t . -v
```

Result: 51/51 passed.

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Result: passed through
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --command extension validate addon
git diff --check
```

Result: source validation passed and no whitespace errors were reported.

### Package and installed-ZIP acceptance

```powershell
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

Result: build and archive validation passed.

- Size: 65,641 bytes.
- SHA-256:
  `B1B81E2144C40B1FDE9D0FF4EB0390AB5931F51A9369CF762141A1B652B82706`.

The ZIP was reinstalled in an isolated Blender 5.2 profile. A generated
three-face interaction verified clean visual Preview, the expected shared
boundary, no disconnected opaque component highlight, repeat stability, and
the exact one-face Apply result.

## Known failures, warnings, and unverified assumptions

- The established private lower-bound discrepancy remains: 1,176 faces that
  are alpha-assigned in the human-tuned after example classify `OPAQUE`.
  This was unchanged by the Preview-only patch and is the next production
  investigation.
- Expected Blender warnings remain the bundled Grease Pencil brush-path warning
  and the deliberately exercised stale-input warning.
- Git reports expected LF-to-CRLF working-copy notices on this Windows checkout.
- Ordinary Unity material/submesh validation remains a release requirement.
- The installed fixture proves the generated Preview case, not every possible
  Blender theme or viewport overlay configuration.

## Remaining tasks

1. Systematically characterize the private 1,176-face `OPAQUE` lower-bound
   misses using ignored diagnostics.
2. Before any production edit, create a generated failing regression for any
   newly identified resolver, image, UV, or rasterization defect.
3. Complete the remaining installed-ZIP checklist items in `docs/testing.md`
   needed for release sign-off.
4. Record the distinct final Apply-preflight timing and interactive
   two-material partial-apply check.
5. Complete the 150 percent UI-scale pass and user-performed ordinary Unity
   material/submesh acceptance.

## Recommended next action

Investigate the 1,176 private reference-alpha faces that still classify
`OPAQUE`, record only anonymized aggregate causes, and stop at a root-cause
report and test-first design before changing production behavior.
