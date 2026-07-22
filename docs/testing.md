# Testing and interactive verification

## Automated checkpoint commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'

python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

The checkpoint tests verify ordinary-Python import without `bpy`, deterministic
coverage/classification and API 1.1 capability JSON, registration/unregistration,
Simple and Expert workflow state, per-material overrides, analysis progress and
cancellation, review-token invalidation, warning confirmation, preview,
stale-result refusal, safe assignment, every documented material-identity
transition, completion summaries, preservation, save/reopen, FBX
export/reimport, README contracts, and anonymized synthetic characterization.

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
- [x] Change reviewed inputs and confirm stale-result refusal. This exercise
  exposed an Edit Mode validation problem; the fix and regression tests now
  validate from Object Mode and restore the requested preview state.
- [x] Review analyzed objects, source material, resolved image/UV/channel,
  destination material, skips, faces to move, and estimated slot/section
  increase before assignment.
- [x] Assign directly from the Edit Mode preview and verify the intended material
  partition.
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
