# Testing and interactive verification

## Automated checkpoint commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'

python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
.\scripts\build_extension.ps1 -Blender $Blender52

$Archive = (Resolve-Path .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive

$IsolatedRoot = Join-Path (Resolve-Path .\.test-output).Path "isolated-install-$PID"
$env:BLENDER_USER_CONFIG = Join-Path $IsolatedRoot 'config'
$env:BLENDER_USER_SCRIPTS = Join-Path $IsolatedRoot 'scripts'
$env:BLENDER_USER_DATAFILES = Join-Path $IsolatedRoot 'datafiles'
New-Item -ItemType Directory -Force -Path $env:BLENDER_USER_CONFIG | Out-Null
New-Item -ItemType Directory -Force -Path $env:BLENDER_USER_SCRIPTS | Out-Null
New-Item -ItemType Directory -Force -Path $env:BLENDER_USER_DATAFILES | Out-Null
& $Blender52 --command extension install-file -r user_default -e $Archive
& $Blender52 --background --python-exit-code 1 --python tests/blender/verify_installed_zip.py
```

When all commands above pass, the checkpoint verifies ordinary-Python import
without `bpy`, deterministic
coverage/classification and API 1.2 capability JSON, registration/unregistration,
Simple and Expert workflow state, per-material overrides, analysis progress and
cancellation, review-token invalidation, warning confirmation, preview,
stale-result refusal, safe assignment, every documented material-identity
transition, completion summaries, preservation, save/reopen, FBX
export/reimport, README contracts, and anonymized synthetic characterization.
Do not mark the installed-ZIP or exact interaction checkboxes complete merely
because the source-tree headless suite passed.

## Required test layers

Every behavior defect first receives a generated or synthetic failing
regression. Verification then proceeds through pure-Python tests, headless
Blender state-transition and mutation tests, semantic preservation checks,
installed-ZIP interaction, and instrumented performance measurements.

Private before/after files are local structural references only. No identifying
name, path, asset, raw graph dump, raw measurement, or screenshot enters a
committed test or report. Committed regressions reproduce the relevant shape
with generated materials, textures, meshes, and collapsed UVs.

When the ignored default before/after pair is present, relevant Blender smoke
passes must also run its local multi-object validator:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

This local layer must exercise all mesh objects even when some materials or
faces remain explicitly unsupported. It checks Analyze → exact-plan Preview →
Object Mode → Apply without reanalysis, semantic changed-face coverage,
source/derived material roles, immutable reference files, and preservation of
meshes, source graphs, images, armatures, transforms, parenting, and original
slots. It also proves that at least one multi-image material resolves from its
supported Base Color authority and that positive-area faces whose UVs lie
outside 0–1 use their actual addressing modes.

The after example is a human-tuned performance reference, not an exact
partition oracle: the extension may conservatively move additional
alpha-evidence and `MIXED` faces, but it must explain any reference alpha face
it misses. It complements generated tests; private data or raw output must
never become a committed fixture or result.

Current status after the 2026-07-26 resolver correction: the resolver, workflow,
out-of-range UV, exact-plan, derived-role, and preservation gates pass. The
semantic lower-bound gate remains open only for a smaller set that the extension
classifies `OPAQUE` from the decoded participating A channel. Keep that as a
separate acceptance investigation; do not weaken authority resolution or
silently change raster margins in this milestone.

For invalidation behavior, every harmless event has a paired real-change test:

| Event | Expected result |
| --- | --- |
| Face selection, active face/object, or Object/Edit Mode toggle | Same analysis ID and review token; zero rasterization and image-digest rows. |
| Unrelated mesh, material, or image update | No report or review change. |
| Relevant topology, UV, material index/slot, or Alpha/Base Color authority change | Confirmed stale; review cleared; assignment performs zero mutation. |
| Assignment-only source graph edit outside the resolved authority | Analysis retained with zero image-digest rows; exact-plan review cleared and Preview required again. |
| Relevant image pixel/reload/pack/replace change | Conservative participating-channel validation, then confirmed stale if content/state differs. |
| Assignment-policy change | Analysis retained; another exact-plan preview required. |
| Analysis setting or manual-source change | Confirmed stale; another analysis required. |
| Apply before a deferred recheck runs | Synchronous preflight drains the recheck and blocks any real change atomically. |

Assignment tests combine a resolved source containing opaque,
alpha-affected, mixed, and face-local uncertain faces with an unresolved source
that remains unchanged. They assert exact Preview/Apply plan equivalence,
partial success, confirmation cancellation, undo/redo, idempotence,
save/reopen, and preservation of every non-allowlisted datablock property.

## Interactive Blender smoke checklist

Executed on 2026-07-22 and repeated for the preview/revalidation changes on
2026-07-25 with Blender 5.2.0 LTS. The UI observations used a generated
two-object grid and generated image; no private reference asset was used.
Machine-state assertions that are difficult to prove visually were also checked
by the corresponding headless regression test.

- [x] Install/development-load the extension and confirm the panel appears in
  the 3D View sidebar. The built ZIP was also installed into an isolated Blender
  configuration by the automated installation test.
- [x] Confirm empty and invalid selections produce clear messages.
- [x] Confirm Simple mode presents only Analyze, Review, and Apply, and Expert
  mode exposes the default-closed analysis, manual-source, alternate-class,
  policy, and diagnostics panels without changing analysis inputs.
- [x] Verify per-material image, channel, UV, and addressing records. Channel
  choice remains disabled until an explicit image is selected; unlisted
  materials continue using automatic detection.
- [x] Run a nontrivial analysis and observe progress advancing continuously.
- [x] Press Escape and confirm cancellation leaves no partial report or data
  change.
- [x] Verify the plain-language result counts and the suppressed/unsupported
  explanations and remedies. Raw codes and analysis IDs remain Expert-only.
- [x] Preview affected and mixed classes and confirm selected faces are visible.
- [x] Preview multiple eligible objects in multi-object Edit Mode.
- [x] Preselect edges and vertices on adjacent and disconnected opaque faces,
  run Preview, and confirm only components belonging to selected faces remain
  highlighted. Confirm a shared selected/unselected boundary edge remains
  highlighted normally.
- [x] Start Analyze from multi-object Mesh Edit Mode and confirm it switches to
  Object Mode before reading base-mesh UV/loop data, completes successfully,
  and preserves mesh contents.
- [x] Confirm shared, linked, read-only, and multi-user meshes are skipped by
  preflight. Exact non-mutation is asserted by the preservation and assignment
  policy tests.
- [x] Change a real reviewed input and confirm stale-result refusal.
- [x] In the rebuilt ZIP, complete Analyze → Preview → `Tab` to Object Mode
  → Apply without another analysis. Confirm the analysis ID and preview token
  survive, no image digest or rasterization runs, and the intended split is
  applied. The installed-ZIP walkthrough kept Apply enabled after a face
  selection change and the Object Mode transition; the instrumented headless
  matrix confirmed zero digest and rasterization work.
- [ ] Confirm Apply is enabled immediately after a current actionable analysis,
  before Preview.
- [ ] Apply an unpreviewed clean plan and confirm the dialog begins with
  **Faces have not been previewed.**
- [ ] Cancel the unpreviewed dialog and confirm zero changes to faces, material
  slots, materials, and metadata.
- [ ] Confirm the same unpreviewed plan, verify the exact planned assignment,
  then undo it completely with Ctrl+Z.
- [ ] Preview the exact clean plan and confirm Apply retains its immediate
  no-warning behavior.
- [ ] Change only assignment preflight, confirm no reanalysis is required, and
  verify Apply forces confirmation until the revised plan is previewed.
- [x] Repeat Object/Edit toggles, face selection changes, active-object changes,
  and multi-object Edit Mode transitions without a false stale message.
  Selection and mode changes were repeated in the installed ZIP; active-object
  and transition permutations are covered by the instrumented headless matrix.
- [x] Review analyzed objects, source material, resolved image/UV/channel,
  destination material, skips, faces to move, and estimated slot/section
  increase before assignment.
- [ ] Confirm each successful analysis automatically collapses the native
  **Material Details (N)** disclosure, duplicate material results count once,
  and a single advisory above it points to unsupported materials. Expand it in
  narrow and wide sidebars and confirm all existing cards and **Set Manual
  Alpha Source** actions remain usable. Cancellation must preserve the prior
  report and disclosure state.
- [ ] Confirm the warning popup after **Apply Material Separation** contains
  only aggregate plan-outcome counts, stays bounded without material/object
  lists, and uses the native **Apply Material Separation** title and **Apply**
  confirmation action. Check narrow/wide layouts and 100%/150% UI scale;
  cancel with zero mutation, then reopen, apply, and undo with Ctrl+Z.
- [x] Assign directly from the Edit Mode preview and verify the intended material
  partition.
- [ ] Process a generated two-material case where one resolved source has
  collapsed-UV faces and another material has no traceable alpha source. Confirm
  uncertain faces move to alpha, the unresolved material stays unchanged, and
  useful work is not globally blocked.
- [x] Undo and redo assignment from the 3D View.
- [x] Confirm the completion card reports moved faces, created/reused material,
  added slots, Ctrl+Z guidance, and the Unity handoff. Rerun and confirm
  “Already separated — no additional changes”; regression tests also assert no
  duplicate datablocks or slots.
- [x] Disable, re-enable, and confirm clean panel/operator lifecycle through the
  isolated ZIP installation and registration lifecycle tests.

The documentation captures under `docs/images/` were generated from this
redistributable synthetic scene, cropped to remove the local file path, and
checked against the final button labels. The live walkthrough was performed at
the default UI scale with a narrow sidebar; automated layout/state checks cover
long labels and both interface modes. A separate 150% scale visual pass remains
part of the release-candidate usability gate.

Ordinary Unity material/submesh validation remains a manual release gate. The
user will provide that result; a VRChat SDK/shader run is separate reference
evidence for only the recorded stack.

## Preservation snapshots

Headless tests permit changes only to reviewed material slots and polygon
material indices. They compare topology, vertex groups, armatures, shape keys,
UVs, normals, attributes, modifiers, parenting, images, source materials, and
unselected objects before and after assignment and undo.

## Cache and timing assertions

Cache tests record component-fingerprint calls, participating image-digest rows,
rasterized polygons, coverage hits/misses, validity transitions, and elapsed
time. A mode-only recheck must record zero image-digest rows and zero rasterized
polygons. Use one discarded warm-up and five measured runs. On the approved
same-machine structural workflow, the new mode-exit recheck targets a median
below one second and below 15 percent of cold analysis; established same-machine
metrics retain the 25 percent unexplained-regression gate.

The Analyze throughput regression also exercises both image-reader paths.
Eligible images must use one native bulk read with no Python slices; an
explicit chunk size, an oversized working estimate, or a rejected native call
must use the existing complete-row fallback. Both paths must produce identical
digests and affected-texel grids for every supported component count/channel,
and non-finite participating values must still fail. Modal analysis prepares
the selected inputs once, traverses each UV layer once, and fingerprints each
shared material once per assignment signature.
