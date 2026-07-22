# Testing and interactive verification

## Automated checkpoint commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'

python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

The checkpoint tests verify ordinary-Python import without `bpy`, deterministic
capability JSON, registration/unregistration twice, property/operator cleanup,
API-major incompatibility, and anonymized synthetic material characterization.

## Interactive Blender smoke checklist

This checklist becomes a release gate when analysis and assignment exist.

- [ ] Install the built ZIP and confirm the panel appears in the 3D View sidebar.
- [ ] Confirm empty and invalid selections produce clear messages.
- [ ] Verify alpha, significance, address, image override, and UV override controls.
- [ ] Run a nontrivial analysis and observe progress advancing.
- [ ] Press Escape and confirm cancellation leaves no partial report or data change.
- [ ] Verify opaque, affected, mixed, suppressed, and unsupported counts/explanations.
- [ ] Preview each class and confirm selected faces are visible.
- [ ] Preview multiple eligible objects in multi-object Edit Mode.
- [ ] Confirm shared, linked, and read-only meshes are visibly skipped.
- [ ] Edit UVs, image pixels, material links, and settings; confirm stale refusal.
- [ ] Review planned materials, reuse, skips, and estimated slot/section increase.
- [ ] Assign and verify only intended polygon material indices change.
- [ ] Undo and redo assignment.
- [ ] Rerun and confirm no duplicate material or slot is created.
- [ ] Disable/re-enable and confirm clean panel/operator lifecycle.

## Preservation snapshots

Later headless tests will permit changes only to reviewed material slots and
polygon material indices. They will compare topology, vertex groups, armatures,
shape keys, UVs, normals, attributes, modifiers, parenting, images, source
materials, and unselected objects before and after assignment and undo.
