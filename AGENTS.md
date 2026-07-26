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

## Plugin coordination

- Superpowers owns the overall development lifecycle: brainstorming, design,
  planning, TDD, normal implementation, review, and branch completion.
- Ponytail full applies to solution scope and implementation: prefer reuse,
  native functionality, minimal dependencies, minimal abstractions, and the
  smallest correct diff.
- Ultracode is opt-in. Do not invoke it unless I explicitly request Ultracode
  or explicitly request an exhaustive, adversarial, repository-wide,
  multi-perspective investigation.
- When Ultracode is invoked, it replaces Superpowers parallel-agent dispatch
  for that specific phase. Do not nest one orchestration system inside the other.
- Default Ultracode workers to read-only. Do not allow parallel edits unless I
  explicitly request implementation and each writer uses an isolated worktree.
- Superpowers TDD and verification requirements remain authoritative for any
  production changes, including changes produced by Ultracode workers.
- Do not assume Ultracode workers inherit parent-thread context or plugin
  instructions. Include all necessary constraints in their worker prompts.

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
- Blender dependency-graph notifications are invalidation hints, not proof that
  an analysis is stale. Selection and Object/Edit Mode changes must preserve a
  reviewed report when authoritative input fingerprints remain equal.
- Version 0.1 assignment may add/reuse a derived material slot and change only
  polygon material indices. It must support undo and repeated-run idempotence.
- Never modify unselected objects or silently make linked/shared data local or
  single-user.
- Preserve armatures, weights, shape keys, UVs, normals, attributes, modifiers,
  parenting, and source materials.
- Unsupported or ambiguous inputs must remain explicitly reported, never be
  relabeled as opaque, and carry a reason scope. Face-local uncertainty in an
  otherwise resolved material may be routed to alpha by an explicit policy;
  an unresolved material-wide source remains unchanged.
- No CATS dependency, runtime network, telemetry, updater, installer, or
  external Python dependency.

## Material-support checkpoint

Guaranteed version 0.1 support is direct Image Texture Alpha to the active
Principled Alpha input plus explicit image/UV overrides. The material-support
checkpoint is complete; the approved 0.1 patterns are recorded in
`docs/material-support.md`. Additional automatic patterns still require user
approval before implementation.

Private characterization may inspect lawful `.local-references/` inputs, but no
asset, name, path, identifying information, or raw result may be committed.

## Required testing methodology

Every reported behavior defect starts with a failing generated or synthetic
regression test. Do not encode private reference names, paths, assets, raw graph
dumps, raw measurements, or identifying screenshots in a committed test.

Use all applicable layers of this test pyramid:

1. Pure-Python tests for rasterization, classification, assignment planning,
   presentation, validity-state transitions, and public payload compatibility.
2. Headless Blender tests for dependency-graph events, modal lifecycle,
   preview, material assignment, undo/redo, save/reopen, and registration.
3. Semantic before/after preservation tests. Compare material datablock roles
   and polygon assignments rather than private names or slot numbers.
4. Installed-ZIP interactive acceptance in a clean Blender 5.2 configuration.
5. Instrumented performance tests covering cold analysis, digest validation,
   component rechecks, and coverage/prefix reuse.

For every state-invalidation fix, test paired harmless and real-change event
sequences through both the real dependency-graph handler and direct
authoritative validation. Harmless cases must include repeated Object/Edit Mode
toggles, face selection, active face, active object, multi-object Edit Mode,
and unrelated Object/Mesh/Material/Image/NodeTree updates. Real-change cases
must include topology, vertex positions, UV values and active/render UV,
polygon material indices, slot order/content, mesh replacement/deletion,
shader links/settings, image pixels/reload/pack/replacement, settings, undo,
redo, and file load. Include an Apply-before-deferred-recheck race. A harmless
transition must retain the analysis ID and exact plan-review token and perform
zero rasterization and zero participating-image digest work. A real input
change must confirm `STALE`, clear review, and allow no mutation.

Preview tests must prove that only plan-target objects enter multi-object Edit
Mode; skipped, unsafe, unrelated, or newly selected meshes must be deselected.
Only the plan-derived Preview action may create the guided review token. Bind
that token and any warning confirmation to a deterministic full assignment-plan
fingerprint so derived-material edits, duplication, deletion, or reuse changes
cannot silently alter the reviewed operation.

Assignment tests must combine material support and safety states instead of
testing only isolated happy paths. Include a resolved source with opaque,
alpha-affected, mixed, and face-local uncertain faces; an unresolved material
that remains unchanged; suppressed evidence; unsafe data; and metadata
conflicts. Assert preview/plan equivalence, confirmation cancellation with zero
mutation, partial success, undo/redo, idempotent rerun, and save/reopen.

Preservation assertions allow only reviewed material-slot additions and planned
polygon material-index changes. Hash or compare topology, coordinates, UVs,
attributes, shape keys, vertex groups, normals, modifiers, armatures, parenting,
images, source material graphs, and unselected objects before and after.

Cache and performance tests must record component-hash calls, image-digest
rows, rasterized polygons, coverage cache hits/misses, validity transitions,
and elapsed time. Use one discarded warm-up followed by five measured runs.
Block unexplained established same-machine regressions over 25 percent.

Modal-analysis tests must mutate participating inputs between work chunks and
prove that no hybrid report is published. Cancellation or failed replacement
analysis must preserve both the previous complete report and its review token.
Transaction-fault tests must reconcile every changed face, appended slot,
created material, and metadata write after rollback; an incomplete rollback is
itself a test failure, not a swallowed exception.

Documentation checkboxes may be marked complete only after that exact command
or installed-ZIP interaction has been executed. Private before/after files may
support ignored local structural acceptance, but committed fixtures must be
generated and redistributable.

When `.local-references/default-example/before.blend` and `after.blend` are
available, every relevant Blender smoke or acceptance pass must include them.
Use the ignored multi-object helper in that directory to run Analyze → Preview
→ Apply, tolerate explicitly reported unsupported materials/faces, verify
positive-area UV faces outside 0–1 are addressed rather than rejected for their
range, compare semantic changed-face sets with the after example, and recheck
preservation. Treat the after example as a human-tuned lower bound: additional
conservative alpha assignments, especially `MIXED` faces, are valid, but faces
placed on alpha in the after example must not be missed without an explicit
unsupported reason. Report missed reference faces as an open acceptance
failure. Never commit the files, helper, identifying details, or raw output.

## Handoff maintenance

At the end of every chat turn, update `docs/HANDOFF.md` to reflect the current
repository state. Remove or revise items that no longer require immediate
attention, and add anything that the next turn must address.

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
interactive UI checklist. The installed workflow must include Analyze →
Preview → Tab to Object Mode → Apply without a second analysis when no
classification input changed. Ordinary Unity material/submesh validation is
required; VRChat SDK/shader results apply only to the exact tested stack.

## Git policy

Work on `feat/alpha-material-separator-0.1`. Create coherent local commits only
at approved milestone boundaries. Do not initialize another repository, rewrite
history, alter remotes, commit ignored/private/generated outputs, or push without
separate approval.
