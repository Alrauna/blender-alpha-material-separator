# Repository handoff

Updated: 2026-07-29

## Current objective

The balanced Analyze responsiveness design is approved. Its test-first
implementation plan is written in
`docs/superpowers/plans/2026-07-29-balanced-analyze-responsiveness.md`.
No production change has begun. The next gate is user review of that plan and
selection of inline or subagent-driven execution.

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
- Retired the private after file as a per-face classification oracle. Its
  hand-made partition remains useful for workflow, aggregate comparison, UV
  addressing, assignment, and preservation checks.
- Updated the ignored private helper so the 1,176 opaque reference-only faces
  are reported diagnostically while the authoritative smoke gates pass.
- Profiled the real 247,718-polygon stress example twice without timer sleeps.
  The two runs produced stable callback counts and stage timings.
- Confirmed that commit `9264fec` improved total image throughput but made each
  eligible image's native transfer and Python post-processing one indivisible
  modal callback.
- Isolated the generated 2K bulk callback: allocation took 5.9 ms, native
  `foreach_get` 2.2 ms, alpha extraction 11.2 ms, digesting 17.9 ms, and the
  Python threshold loop 563.2 ms. The native transfer is not the stutter;
  chunkable post-processing is.
- Quantified the pre-existing 20 ms modal timer cost. About 55 seconds of
  callback work projects to 103 seconds in the current schedule because 3,870
  polygon callbacks frequently finish before the next timer event.
- Selected the balanced target: retain exact algorithms, split bulk image
  post-processing, use a 1 ms timer and 12 ms polygon deadline, improve progress
  stages, and accept rare single-polygon stalls.
- Wrote a four-task test-first implementation plan covering image chunking,
  polygon scheduling, progress/cancellation, private acceptance, performance,
  packaging, and durable documentation.

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
- Analyze correctness still requires main-thread Blender datablock access,
  exact rasterization, authoritative image digests, cancellation without a
  partial report, and publication-time validation.
- The safest performance direction retains native full pixel transfer but
  time-slices digest/threshold work from the retained buffer. Reverting the
  modal path to Blender pixel slices removes stutter but made a generated 2K
  read about 3.2 times slower.
- Multiprocessing remains deferred unless a measured implementation clears the
  complete-workflow threshold after serialization, memory, cancellation, and
  Blender lifecycle costs.
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
- `AGENTS.md`, `PLAN.md`, and `docs/testing.md`: record that the hand-made after
  partition is not a per-face oracle and remove the false release blocker.
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

The component-selection gate, exact Preview/Apply plan equivalence,
out-of-range UV addressing, assignment, preservation, and immutable-reference
checks passed. After correcting the test expectation, the command exits zero.
It reports 1,176 opaque reference-only faces as an anonymized aggregate
diagnostic; planned and applied faces remain 65,773.

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

### Analyze cadence investigation

Ignored aggregate profiler:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .test-output\profile_analyze_cadence.py -- `
  .local-references\default-example\before.blend
```

Both runs completed successfully. Representative second-run results:

- Initialization: 3.836 s, including 3.448 s in the structural signature.
- Image work: 12 bulk callbacks, median 1.560 s, maximum 1.630 s; eight exceeded
  one second.
- Polygon work: 3,870 callbacks, 41.780 s total, median 3.6 ms, maximum
  279.3 ms; 105 exceeded 50 ms.
- Publication validation: 2.230 s.
- Total callback work: 55.032 s.
- Estimated timer phase: 103.262 s at 20 ms, 74.298 s at 10 ms, 61.748 s at
  5 ms, and 55.434 s at 1 ms.
- Generated 2K bulk read: one 384.8 ms callback.
- Generated 2K 32-row Blender-slice read: 64 callbacks, maximum 24.7 ms, but
  1.217 s total.

Generated phase breakdown:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python .test-output\profile_bulk_phases.py
```

Result: the threshold loop dominated the callback; native transfer was 2.2 ms.
Both ignored profilers and their raw output were deleted after use.

## Known failures, warnings, and unverified assumptions

- The 1,176 private `OPAQUE` differences are not a known extension failure.
  They reflect broad, hand-made alpha sections in the early-development after
  example and remain visible only as a diagnostic.
- Current modal image callbacks freeze Blender for up to about 1.63 seconds.
- Analyze spends an estimated 48 seconds waiting on the 20 ms timer in the
  private stress case. This is scheduling overhead, not classification work.
- Progress has unrepresented stalls: about 3.8 seconds while showing 0 percent
  during initialization and about 2.2 seconds at completion during publication
  validation.
- Rare expensive 64-polygon batches still take up to about 279 ms. A balanced
  fix can reduce typical stalls but cannot guarantee a strict frame budget
  without making single-polygon rasterization resumable.
- Expected Blender warnings remain the bundled Grease Pencil brush-path warning
  and the deliberately exercised stale-input warning.
- Git reports expected LF-to-CRLF working-copy notices on this Windows checkout.
- Ordinary Unity material/submesh validation remains a release requirement.
- The installed fixture proves the generated Preview case, not every possible
  Blender theme or viewport overlay configuration.

## Remaining tasks

1. Obtain user review and execution approval for the written test-first plan.
2. Implement generated cadence/cancellation regressions before production
   changes.
3. Re-run unit, Blender, private smoke, performance, package, and installed-ZIP
   interactive gates.
4. Complete the remaining release-validation checklist.

## Recommended next action

Review
`docs/superpowers/plans/2026-07-29-balanced-analyze-responsiveness.md`, then
approve inline execution or request changes.
