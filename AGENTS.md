# Blender Alpha Material Separator repository guidance

## Goal

Eliminate unnecessary alpha overdraw by moving only original mesh polygons
whose UV-covered image texels require alpha rendering onto a distinct material.
Favor conservative classification: missing an optimization is safer than
leaving a transparent face on an opaque material. No topology changes are
allowed.

Build a standalone Blender 5.2 LTS extension; the manifest minimum is `5.2.0`.
Use `GPL-3.0-or-later` in the manifest, README, and source SPDX notices. The
public identity is `alpha_material_separator`; never reintroduce the retired
`alpha_face_separator` name.

## Repository map and policy routing

- `addon/`: extension-native package and manifest.
- `addon/core/`: data-only rasterization and classification; no `bpy`.
- `addon/adapters/`: Blender mesh, image, resolver, cache, and assignment code.
- `tests/unit/`: ordinary Python core and documentation-contract tests.
- `tests/blender/`: headless Blender lifecycle and integration tests.
- `tests/fixtures/`: generated, redistributable fixtures.
- `scripts/`: characterization, build, and CI entry points.
- `docs/`: algorithms, support, API, testing, performance, and workflow.
- `.local-references/`: lawful private inputs; never commit its contents.
- `.packaged-releases/`: generated ZIPs; never commit.

Read the conditional authority before changing its domain:

- `docs/development-workflow.md`: branch, design, planning, review, commit,
  handoff, and publication procedure.
- `docs/testing.md`: commands, test layers, state-transition and assignment
  matrices, private acceptance, installed-ZIP checks, CI/CD, and release gates.
- `docs/performance.md`: instrumentation and same-session regression protocol.
- `docs/material-support.md`: approved automatic resolver patterns, overrides,
  and unsupported cases.

## Instruction precedence

Repository safety invariants and direct user instructions govern; safety limits
prevail if they conflict. Next follow task-specific repository documentation,
then applicable Superpowers and Ponytail workflows, then generic agent defaults.
Repository-specific rules override incompatible generic skill steps. Do not use
a skill merely to create ceremony.

## Development workflow summary

- Read-only inspection, status reporting, and mechanical documentation fixes
  may proceed with evidence and proportionate validation.
- For a narrow, explicit request, the request itself supplies design approval;
  state a concise plan and proceed unless the user requested a checkpoint.
- Ambiguous, architectural, public-contract, material-support, security, or
  high-risk work requires a written design and explicit approval. Multi-step
  implementation then requires an approved test-first plan.
- Begin defects and unexpected results with systematic debugging. Establish a
  reproduction and root cause before production edits.
- Use RED/GREEN TDD for production behavior changes. Stop for approval when
  findings materially change agreed behavior, scope, risk, or architecture.
- Inline execution and self-review are the defaults. Subagent implementation,
  parallel dispatch, and reviewer subagents require explicit user authorization.
- Ponytail governs scope: prefer reuse, Blender/Python-native behavior, minimal
  dependencies and abstractions, and the smallest correct diff.

## Compatibility and safety invariants

- Analyze original/base meshes, not evaluated modifier topology.
- Analyze invoked from Mesh Edit Mode must switch to Object Mode before reading
  authoritative base-mesh polygons, loops, or UV data. This is intended.
- Use exact positive-area UV triangle/texel-cell coverage. Do not use centroid,
  vertex-only, sparse fixed sampling, or an approximation after a raster budget
  failure.
- Analyze must not persistently change mesh, material, image, face selection,
  or topology data. Preview may change face/object selection and enter
  multi-object Edit Mode only as defined by the reviewed plan.
- Dependency-graph notifications are invalidation hints, not proof of staleness.
  Selection and Object/Edit Mode changes preserve a reviewed report when
  authoritative fingerprints remain equal.
- Apply may create or reuse a local derived material, write namespaced AMS
  metadata on that derived material, append or reuse its material slot, and
  change only reviewed polygon material indices.
  Source materials remain unchanged. Assignment must support undo and
  repeated-run idempotence.
- Never modify unselected objects or silently make linked/shared data local or
  single-user.
- Preserve topology, coordinates, UVs, normals, attributes, shape keys, vertex
  groups, modifiers, armatures, parenting, images, source material graphs, and
  unselected objects except for the reviewed assignment allowlist above.
- Unsupported or ambiguous inputs remain explicitly reported with a reason
  scope and are never relabeled as opaque. Explicit policy may route face-local
  uncertainty in an otherwise resolved material to alpha; an unresolved
  material-wide source stays unchanged.
- No runtime network, telemetry, updater, installer, or CATS dependency.

## Material support and private inputs

`docs/material-support.md` is authoritative. Additional automatic patterns
require explicit user approval before implementation.

Committed fixtures and regressions must be generated and redistributable.
Private characterization may inspect `.local-references/` only with user
authorization. Never commit private assets, helpers, contents, identifying
details, raw graph dumps, screenshots, measurements, or output. Directory and
file paths may be documented when necessary.

## Validation matrix

- During RED/GREEN, run the smallest relevant regression first.
- Before a coherent commit, run affected tests and static/document checks.
- Production branch completion requires the unit suite, complete headless
  Blender suite, and source validation.
- Packaging or installable-behavior changes require a clean build and
  validation of version-independent AMS ZIPs.
- Performance-sensitive changes follow the same-session protocol in
  `docs/performance.md`; never claim a cross-session baseline.
- Release work follows every automated, private-if-authorized, installed-ZIP,
  export, performance, Unity, and human interaction gate in `docs/testing.md`.
- Documentation-only changes use applicable document/link contracts and
  `git diff --check`, not the Blender product matrix.

Add practical in-scope regressions automatically; record unrelated discoveries
as future work rather than expanding the branch. When automation is genuinely
impractical, document why, retain the nearest automated protection, and report
the remaining manual validation.

## Git and publication guard

Before the first tracked edit, follow `docs/development-workflow.md` to confirm
branch scope, relationship to freshly fetched `origin/main`, existing commits,
and working-tree safety. One topic branch has one coherent objective. Preserve
unrelated user changes and stage explicit paths only.

`main` is protected. Every change lands through a pull request based on `main`.
Do not push, create or merge pull requests, change repository settings or
visibility, create tags, publish releases, delete branches, rewrite published
history, or discard work without the required explicit approval. Never weaken
the CI/CD security contracts in `docs/testing.md`.

## Handoff

Update `docs/HANDOFF.md` at a durable pause, ownership transfer, material
blocker, or branch completion. Record purpose, decisions, completed work,
verification evidence, limitations, and the immediate next action. Ordinary
tool activity, branch switches, and generated outputs do not require a handoff
edit.
