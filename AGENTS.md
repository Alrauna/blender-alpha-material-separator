# Blender Alpha Material Separator repository guidance

## Goal

Build a standalone Blender 5.2 LTS extension that conservatively identifies
original mesh polygons whose UV-covered image texels require alpha rendering,
allows review through face selection, and assigns reviewed faces to a distinct
material slot without changing topology.

## Layout

- `addon/`: complete extension-native package and manifest.
- `addon/core/`: data-only rasterization and classification code; no `bpy`.
- `addon/adapters/`: Blender mesh, image, resolver, cache, and assignment code.
- `tests/unit/`: ordinary Python core tests.
- `tests/blender/`: headless Blender lifecycle and integration tests.
- `tests/fixtures/`: generated, redistributable fixtures and generators.
- `scripts/`: characterization, build, test, and benchmark entry points.
- `docs/`: algorithm, support matrix, API, testing, performance, and workflow.
- `.local-references/`: lawful private inputs; never commit contents or paths.
- `.packaged-releases/`: generated ZIPs; never commit.

## Compatibility and invariants

- Target Blender 5.2 LTS; manifest minimum is `5.2.0`.
- Use `GPL-3.0-or-later` in the manifest, README, and source SPDX notices.
- Public identity is `alpha_material_separator`; do not introduce the retired
  `alpha_face_separator` name.
- Analyze original/base meshes, not evaluated modifier topology.
- Do not use centroid, vertex-only, sparse fixed sampling, or an approximation
  after a raster budget failure.
- Analysis must not persistently change meshes, materials, images, selection,
  or topology.
- Version 0.1 assignment may add/reuse a derived material slot and change only
  polygon material indices. It must support undo and repeated-run idempotence.
- Never modify unselected objects or silently make linked/shared data local or
  single-user.
- Preserve armatures, weights, shape keys, UVs, normals, attributes, modifiers,
  parenting, and source materials.
- Unsupported or ambiguous inputs must be reported, never guessed.
- No CATS dependency, runtime network, telemetry, updater, installer, or
  external Python dependency.

## Material-support checkpoint

Guaranteed version 0.1 support is direct Image Texture Alpha to the active
Principled Alpha input plus explicit image/UV overrides. Additional automatic
patterns require the approved material-support matrix. Stop after producing the
matrix and obtain user approval before implementing extra resolver patterns.

Private characterization may inspect lawful `.local-references/` inputs, but no
asset, name, path, identifying information, or raw result may be committed.

## Commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
python -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
```

## Completion gate

Before work is complete, run ordinary unit tests, headless Blender tests, source
validation, archive build, archive validation, ZIP installation, save/reopen,
FBX material-assignment validation, performance baselines, and the documented
interactive UI checklist. Ordinary Unity material/submesh validation is
required; VRChat SDK/shader results apply only to the exact tested stack.

## Git policy

Work on `feat/alpha-material-separator-0.1`. Create coherent local commits only
at approved milestone boundaries. Do not initialize another repository, rewrite
history, alter remotes, commit ignored/private/generated outputs, or push without
separate approval.
