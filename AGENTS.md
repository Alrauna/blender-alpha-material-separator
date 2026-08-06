# Blender Alpha Material Separator repository guidance

## Goal

The purpose is to eliminate unnecessary overdraw. A real-time renderer cannot
skip hidden pixels on a transparent surface, so it shades the same screen pixel
over and over; that repeated shading is overdraw. When one alpha-blended
material covers a whole mesh, every face pays that cost, including faces that
are completely solid. Moving only the faces that genuinely need alpha onto their
own material lets the renderer draw the solid remainder the cheap way.

Every design decision follows from that purpose. Being conservative matters
because wrongly leaving a transparent face on the opaque material makes the
model render incorrectly, which is far worse than missing a small optimization.

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
- `scripts/`: characterization, build, and CI entry points.
- `docs/`: algorithm, support matrix, API, testing, performance, and workflow.
- `.local-references/`: lawful private inputs; never commit its contents.
- `.packaged-releases/`: generated ZIPs; never commit.

## Development approach

- Superpowers owns the development lifecycle. Use its phases in this order when
  they apply: investigate, design, obtain design approval, write a test-first
  plan, obtain plan approval, implement, review, verify, and commit.
- Begin every defect or unexpected result with systematic debugging. Establish
  a reproduction and root cause before proposing or editing production code.
- Treat new or changed behavior—including UX, API, architecture, cache,
  assignment, material resolution, and performance behavior—as design work.
  Use brainstorming, present the design, and obtain user approval before
  production edits.
- Convert an approved design or other multi-step production request into a
  written implementation plan with explicit files, RED/GREEN tests, validation,
  preservation checks, and commit boundaries. Obtain user approval before
  execution. A plan may be concise for a narrow change, but a small expected
  diff is not a reason to omit it.
- Design specs and implementation plans live in `docs/superpowers/specs/` and
  `docs/superpowers/plans/` while the work is in flight, and are committed so
  the approved wording is reviewable. Delete them from `main` once the milestone
  they describe is complete and committed. Git history retains them, so a
  completed milestone leaves its rationale recoverable without carrying
  superseded documents in the working tree. Do not treat that deletion as
  optional cleanup; it is the last step of the milestone.
- Execute approved plans with `executing-plans` by default.
  `subagent-driven-development` or parallel dispatch requires an explicit user
  request and independent work that can be safely isolated.
- Use test-driven development for every production behavior change: demonstrate
  the generated or synthetic regression before the production edit, implement
  the smallest fix, and run the applicable change gate. Track plan progress and
  record any material deviation; stop for approval when findings change the
  agreed behavior, scope, risk, or architecture.
- Review material production changes for correctness before completion. Use
  `requesting-code-review` for major or risky milestones and
  `receiving-code-review` before acting on review feedback. Use
  `verification-before-completion` before success claims or commits, and
  `finishing-a-development-branch` only when integration is actually requested.
- Ponytail governs scope inside every Superpowers phase. Use it during
  investigation, design, planning, implementation, and review to prefer reuse,
  Blender/Python-native behavior, minimal dependencies, minimal abstractions,
  and the smallest correct diff. Ponytail may recommend deleting or deferring
  work, but it may not skip investigation, design or plan approval, TDD,
  review, verification, preservation checks, or required acceptance gates.
- Read-only inspection, status reporting, and mechanical documentation
  corrections that do not create or change product/process policy may proceed
  without design, plan, or implementation artifacts. They still require
  evidence for factual claims and `git diff --check` when files change.
- Direct user instructions and repository safety invariants take precedence
  over both toolsets. Do not create ceremony merely to demonstrate a skill, but
  do not relabel required reasoning, approval, or verification as ceremony.

## Compatibility and invariants

- Target Blender 5.2 LTS; manifest minimum is `5.2.0`.
- Use `GPL-3.0-or-later` in the manifest, README, and source SPDX notices.
- Public identity is `alpha_material_separator`; do not introduce the retired
  `alpha_face_separator` name.
- Analyze original/base meshes, not evaluated modifier topology.
- Analyze invoked from Mesh Edit Mode must switch to Object Mode before reading
  authoritative base-mesh polygons, loops, or UV data. This mode change is an
  intended effect of Analyze.
- Do not use centroid, vertex-only, sparse fixed sampling, or an approximation
  after a raster budget failure.
- Analyze must not persistently change mesh, material, or image data, face
  selection, or topology. Preview may change face selection and enter
  multi-object Edit Mode; Apply may perform only the reviewed mutations below.
- Blender dependency-graph notifications are invalidation hints, not proof that
  an analysis is stale. Selection and Object/Edit Mode changes must preserve a
  reviewed report when authoritative input fingerprints remain equal.
- Assignment may create or reuse a local derived material, write namespaced AMS
  metadata on that derived material, append/reuse its material slot, and change
  only reviewed polygon material indices. It must support undo and repeated-run
  idempotence. Source materials remain unchanged.
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

The material-support checkpoint is complete. `docs/material-support.md` is the
authoritative list of approved automatic patterns, overrides, and unsupported
cases for the current release. Do not duplicate a partial resolver list here.
Additional automatic patterns still require user approval before implementation.

Private characterization may inspect lawful `.local-references/` inputs.
Directory and file paths may be documented, but private file contents, assets,
identifying information extracted from them, and raw results must not be
committed.

## Required testing methodology

Every production behavior fix requires a failing generated or synthetic
regression test before the production edit. A private or interactive
reproduction may establish the defect first, but the committed regression must
remain generated and redistributable. Do not encode private assets, contents,
raw graph dumps, raw measurements, or identifying screenshots in a committed
test.

Use all applicable layers of this test pyramid:

1. Pure-Python tests for rasterization, classification, assignment planning,
   presentation, validity-state transitions, and public payload compatibility.
2. Headless Blender tests for dependency-graph events, modal lifecycle,
   preview, material assignment, undo/redo, save/reopen, and registration.
3. Semantic before/after preservation tests. Compare material datablock roles
   and polygon assignments rather than private names or slot numbers.
4. Installed-ZIP interactive acceptance in a clean Blender 5.2 configuration.
   This layer is user-performed. An agent cannot drive the Blender UI, so it
   must report these items as pending and name exactly which interactions remain
   unconfirmed rather than implying they passed.
5. Instrumented performance tests covering cold analysis, digest validation,
   component rechecks, and coverage/prefix reuse.

The private `.local-references/` before/after smoke is likewise user-gated: an
agent may run it only when the user confirms those inputs are available.

For a state-invalidation fix, add the smallest paired harmless/real-change
regression that demonstrates the defect through both the real dependency-graph
handler and direct authoritative validation, then run the existing full
revalidation matrix. Do not duplicate the entire matrix in every new test.
The shared matrix must continue to cover Object/Edit Mode and selection
transitions, unrelated datablock updates, topology/vertex/UV/material changes,
datablock replacement/deletion, shader and image changes, settings, undo/redo,
file load, and the Apply-before-deferred-recheck race. Harmless transitions
must retain the analysis ID and exact plan-review token with zero rasterization
and participating-image digest work. Real changes must confirm `STALE`, clear
review, and allow no mutation.

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

Preservation assertions allow only reviewed local derived-material
creation/reuse, namespaced metadata writes on derived materials, material-slot
additions/reuse, and planned polygon material-index changes. Hash or compare
topology, coordinates, UVs, attributes, shape keys, vertex groups, normals,
modifiers, armatures, parenting, images, source material graphs, and unselected
objects before and after.

Cache and performance tests must record component-hash calls, image-digest
rows, rasterized polygons, coverage cache hits/misses, validity transitions,
and elapsed time. Use one discarded warm-up followed by five measured runs.
Block an unexplained regression over 25 percent against a before/after pair
measured in the same session on the same machine. No baseline persists between
sessions: `.test-output/` is ignored, so a cross-session comparison is not
available and must not be claimed.

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
available, include them when a change could affect material resolution,
rasterization, classification, cache validity, preview plans, assignment plans,
or mutation safety. Documentation-only and presentation-only changes do not
require this private smoke unless they alter data derived from an assignment
plan.
Use the ignored multi-object helper in that directory to run Analyze → Preview
→ Apply, tolerate explicitly reported unsupported materials/faces, verify
positive-area UV faces outside 0–1 are addressed rather than rejected for their
range, compare semantic changed-face sets with the after example, and recheck
preservation. The after example is an early-development, hand-made material
partition, not a per-face classification oracle. Additional conservative alpha
assignments, especially `MIXED` faces, are valid, and faces left in a broad
hand-made alpha section may correctly classify `OPAQUE` from their sampled A
values. Treat those differences as an aggregate diagnostic, not an acceptance
failure; generated fixtures remain authoritative for classification behavior.
Never commit the files, helper, private contents, identifying details, or raw
output.

## Handoff maintenance

Update `docs/HANDOFF.md` at the end of a turn that changes repository state or
materially changes what the next turn must address. Pure read-only answers and
status checks that leave the next action unchanged do not require a handoff
edit. Remove or revise items that no longer require immediate attention.

## CI/CD security

- Keep `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2` stable. Both
  are required merge checks on `main`, bound to the GitHub Actions app, with
  force pushes and branch deletion blocked and administrators included.
  Consequently `main` accepts no direct push: every change lands through a pull
  request whose two checks pass. The workflow triggers only for pull requests
  based on `main`, so a pull request aimed at any other branch reports no checks
  and cannot satisfy protection.
- Keep workflow permissions at `contents: read` by default. Only the protected
  manual release job may use `contents: write`, and `GH_TOKEN` belongs only on
  individual `gh` command steps.
- Keep `actions/checkout` confined to read-only jobs, pinned to a reviewed full
  commit SHA, with `persist-credentials: false`. The write-authorized release
  job must use unauthenticated native Git, fetch the exact `GITHUB_SHA`, and
  verify `HEAD` without credentials. Adding an action, dependency, cache,
  artifact transfer, trigger, runner type, permission, or network source
  requires design review and explicit approval.
- Blender downloads must retain the fixed HTTPS identity, committed SHA-256,
  system DNS/Cloudflare DoH/Quad9 DoT checksum consensus, pre-extraction archive
  hash, exact archive root, and executable version check. Quad9-resolved
  addresses must come from a complete, exact-question, standard A/IN answer;
  every direct A owner must match that question case-insensitively, compression
  pointers may target only validated label boundaries, and authority,
  additional, and CNAME records do not supply addresses. Pass at most 16
  distinct valid answers to curl while retaining the Blender hostname for TLS
  validation. Network timeouts and retries may bound failure but may not weaken
  resolver or hash requirements.
- Ordinary validation must discover exactly one version-independent AMS ZIP;
  only the strict release path may derive a filename from the validated version.
- Validation builds are disposable. Publication rebuilds from the validated
  `main` commit, creates a draft, uploads the ZIP and `SHA256SUMS.txt`, downloads
  and re-hashes the stored ZIP, then publishes.
- Do not push, change visibility or repository settings, configure protection,
  create tags, or publish releases without explicit user approval.
- Quad9's HTTP/2-only DoH endpoint is incompatible with the tested Windows curl
  path. Keep the approved standard-library Quad9 DoT path unless hosted port
  853 is proven unavailable; preserve TLS hostname validation, dynamic Blender
  addresses, Quad9, and byte consensus.

## Commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
Remove-Item .\.packaged-releases\*.zip -ErrorAction SilentlyContinue
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$Archive = (Get-ChildItem .\.packaged-releases\alpha_material_separator-*.zip | Select-Object -ExpandProperty FullName)
& $Blender52 --factory-startup --command extension validate $Archive
```

The benchmark suite is separate because it runs for many minutes and is not part
of the ordinary change gate:

```powershell
& $Blender52 --factory-startup --background --python-exit-code 1 `
  --python tests/blender/run_benchmarks.py `
  -- --output .test-output/benchmarks/baseline.json
```

Clear `.packaged-releases` before building. Ordinary validation must find
exactly one AMS ZIP, so leaving archives from earlier versions there breaks
discovery. Never name a version in an ordinary validation path; only the strict
release path derives a filename from the validated version.

## Change completion gate

Run the smallest relevant regression first. Production changes must then pass
the ordinary unit suite, headless Blender suite, and source validation. Run the
private before/after smoke only for the behavior scopes defined above. Rebuild
and validate the archive when packaging or installable behavior is affected.
Documentation-only changes require document/link contracts where applicable
and `git diff --check`, not the Blender release matrix.

## Release gate

Before a release is complete, run archive build/validation, clean ZIP
installation, save/reopen, FBX material-assignment validation, performance
baselines, and the documented interactive UI checklist in addition to the
change gate. The installed workflow must include Analyze → Preview → Tab to
Object Mode → Apply without a second analysis when no classification input
changed. Ordinary Unity material/submesh validation is required; VRChat
SDK/shader results apply only to the exact tested stack.

## Git policy

Start each piece of work on a topic branch cut from an up-to-date `main`, and
land it through a pull request. `main` is protected and accepts no direct push.

Base a pull request on `main`, not on another unmerged branch. A stacked pull
request reports no checks, cannot satisfy protection, and if its base branch is
deleted on merge the stacked merge silently lands nowhere. When work genuinely
builds on an unmerged branch, wait for that branch to land, rebase onto the
updated `main`, then open the pull request.

During implementation, commit each coherent, verified unit before starting a
materially different task; do not accumulate unrelated completed work until the
end of a long turn. Stage explicit paths and inspect the staged diff so each
commit contains only its stated scope. Preserve unrelated user changes, and
never commit ignored/private/generated outputs. Do not initialize another
repository, alter remotes, or push without separate approval. Rewriting history
is allowed only to rebase a branch that has never been pushed; published history
requires separate approval.
