# Testing and interactive verification

## Automated checkpoint commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'

python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

The checkpoint tests verify ordinary-Python import without `bpy`, deterministic
coverage/classification and API 1.2 capability JSON, registration/unregistration,
Simple and Expert workflow state, per-material overrides, analysis progress and
cancellation, review-token invalidation, warning confirmation, preview,
stale-result refusal, safe assignment, every documented material-identity
transition, completion summaries, preservation, save/reopen, FBX
export/reimport, README contracts, and anonymized synthetic characterization.

## Required test layers

Every behavior defect first receives a generated or synthetic failing
regression. Verification then proceeds through pure-Python tests, headless
Blender state-transition and mutation tests, semantic preservation checks,
installed-ZIP interaction, and instrumented performance measurements.

Private before/after files are local structural references only. No identifying
name, path, asset, raw graph dump, raw measurement, or screenshot enters a
committed test or report. Committed regressions reproduce the relevant shape
with generated materials, textures, meshes, and collapsed UVs.

For invalidation behavior, every harmless event has a paired real-change test:

| Event | Expected result |
| --- | --- |
| Face selection, active face/object, or Object/Edit Mode toggle | Same analysis ID and review token; zero rasterization and image-digest rows. |
| Unrelated mesh, material, or image update | No report or review change. |
| Relevant topology, UV, material index/slot, or shader change | Confirmed stale; review cleared; assignment performs zero mutation. |
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

Executed on 2026-07-22 with Blender 5.2.0 LTS. The UI observations used a
generated two-object grid and generated image; no private reference asset was
used. Machine-state assertions that are difficult to prove visually were also
checked by the corresponding headless regression test.

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
- [x] Confirm shared, linked, read-only, and multi-user meshes are skipped by
  preflight. Exact non-mutation is asserted by the preservation and assignment
  policy tests.
- [x] Change a real reviewed input and confirm stale-result refusal.
- [ ] In the rebuilt ZIP, complete Analyze → Preview → `Tab` to Object Mode
  → Apply without another analysis. Confirm the analysis ID and preview token
  survive, no image digest or rasterization runs, and the intended split is
  applied. The earlier checklist did not cover this exact transition.
- [ ] Repeat Object/Edit toggles, face selection changes, active-object changes,
  and multi-object Edit Mode transitions without a false stale message.
- [x] Review analyzed objects, source material, resolved image/UV/channel,
  destination material, skips, faces to move, and estimated slot/section
  increase before assignment.
- [x] Assign directly from the Edit Mode preview and verify the intended material
  partition.
- [ ] Process a generated two-material case where one resolved source has
  collapsed-UV faces and another material has no traceable alpha source. Confirm
  uncertain faces move to alpha, the unresolved material stays unchanged, and
  useful work is not globally blocked.
- [x] Undo and redo assignment from the 3D View.
- [x] Confirm the completion card reports moved faces, created/reused material,
  added slots, Ctrl+Z guidance, and the Unity handoff. Rerun and confirm
  “Already separated—no additional changes”; regression tests also assert no
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
