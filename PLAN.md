# Blender Alpha Material Separator 1.0 release plan

Status: milestones 0-4A are implemented and verified locally on
`feat/alpha-material-separator-0.1`. The workflow-friction hardening prompted
by real-file testing is complete in commits `a09593b`, `4c26dfd`, and
`1e61993`: safe groups apply independently, exact-plan preview survives
harmless selection/mode changes, and the installed-ZIP Analyze → Preview →
Tab → Apply workflow no longer requires redundant analysis. The listed
Milestone 5 checks are complete: the compact count-only confirmation,
optional-preview flows, partial apply, 150% UI scale, Unity material/submesh
handoff, final Apply-preflight measurement, and installed-ZIP progress and
Escape cancellation have passed. A minor cursor/sidebar percentage
desynchronization remains a follow-up UX issue. VRChat validation remains
optional stack-specific evidence. The approved repository-simplification pass
is complete in commits `4138236` through `f330192`; public API 1.2 and tested
workflow behavior are unchanged.

## Product outcome

Version 1.0 analyzes selected original/base mesh polygons, reports and previews
opaque, alpha-affected, mixed, suppressed, and unsupported faces, and assigns
reviewed alpha-affected/mixed faces to a derived material slot. It never changes
topology or physically separates objects.

The original material remains the opaque/source candidate. A local
`<source>__AMS_ALPHA` copy represents faces that need alpha. The copy remains
visually identical in Blender; Unity or VRChat shader modes are configured
manually after export.

## Milestone 0: documentation and scaffold

- Preserve the cloned repository, canonical license, remote, and initial commit.
- Extend existing documentation and ignore rules.
- Create an extension-native Blender 5.2 package with reversible registration.
- Declare `GPL-3.0-or-later`, manifest ID `alpha_material_separator`, version
  `1.0.0`, and maintainer `Alrauna`.
- Validate registration, unregistration, re-registration, and the manifest.

## Milestone 1: bounded material characterization

Inspect only lawful references already present in `.local-references/`. Do not
wait or download inputs. If representative graphs are unavailable, publish a
matrix that records the limitation and proceed with only the guaranteed direct
alpha resolver and explicit image/UV overrides.

Consider direct alpha, alpha-bearing color images, separate masks, UV Map,
Texture Coordinate, Mapping, reroutes, simple groups, combined masks, and
ambiguous multi-image graphs. Commit only anonymized aggregates and synthetic
reproductions.

**Mandatory checkpoint:** stop after `docs/material-support.md` and
`docs/material-characterization.md`; obtain approval before freezing or adding
automatic resolver patterns.

Checkpoint result: approved. The direct-alpha, simple-reroute, unique Base
Color image, direct UV Map, and Texture Coordinate UV patterns are frozen for
0.1. Explicit image/UV/channel overrides and baked masks provide the manual
escape hatch for other alpha sources.

## Milestone 2: pure coverage and classification core

- Use positive-area UV-triangle/texel-cell coverage and deterministic row spans.
- Union spans by original polygon; never sample only vertices or centroids.
- Support Repeat, Extend, Clip, and Mirror after rasterization.
- Default threshold `0.999`, margin `0`, minimum affected count `1`, and minimum
  fraction `0`; all enabled minima must pass.
- Use alpha row prefixes and deterministic limits of 1,000,000 scanlines and
  2,000,000 emitted runs per polygon.
- Report `OPAQUE`, `ALPHA_AFFECTED`, `MIXED`, `SUPPRESSED`, or `UNSUPPORTED`.
- Compare the optimized algorithm with a slow fixed-seed clipping oracle.

## Milestone 3: Blender analysis, preview, cache, and UI

- Resolve survey-approved material paths plus explicit overrides.
- Hash every classification input with versioned BLAKE2b signatures: base mesh
  geometry/topology, slots, UVs, settings, resolved node path, image identity,
  dimensions, state, and participating pixel channels.
- Treat Blender notifications as revalidation hints. Track `CLEAN`,
  `RECHECK_PENDING`, and confirmed `STALE` separately; a hint alone must not
  clear the report, review token, or content-addressed coverage cache.
- Store component fingerprints for mesh identity/safety, geometry/topology,
  material indices and slots, UVs, material/resolver graphs, image state and
  participating pixels, and configuration. Recheck only relevant hinted
  components where correctness can be proven.
- Preserve the analysis ID and reviewed preview across selection and
  Object/Edit Mode changes whose fingerprints remain equal. Final Preview and
  Apply preflight still synchronously drain pending validation.
- Benchmark full alpha hashing separately from proven digest reuse, threshold
  prefix reuse, and UV-coverage reuse. Recompute when invalidation reliability
  is uncertain.
- Use chunked modal work with visible progress and Escape cancellation before
  mutation. Headless execution uses the same engine synchronously.
- Complete the interactive panel/progress/cancel/preview/multi-object Edit
  Mode/assignment/undo smoke checklist in `docs/testing.md`.

## Milestone 4: safe material assignment

- Require the reviewed analysis ID and revalidate before mutation.
- Route alpha-affected and mixed faces to the derived material.
- Apply independently safe material groups even when another group remains
  unchanged or is skipped; one group must not veto unrelated useful work.
- Keep `UNSUPPORTED` as a public face classification while reporting whether it
  is face-local, material-source-wide, or data-safety related.
- In Simple mode, route face-local uncertainty inside an otherwise resolved
  material to alpha after preview and warning confirmation. Leave a
  material-wide unresolved source unchanged and offer a manual alpha-source
  override. Keep suppressed evidence and unsafe/ambiguous data conservative.
- Store namespaced metadata and a source-material pointer only on the local
  derived material; never tag the source merely for identity.
- Refuse multi-user, linked, read-only, or override-restricted mesh mutation.
- Never overwrite, delete, rename, localize, or make user data single-user.

Required identity behavior:

| Change | Behavior |
| --- | --- |
| Source rename | Reanalyze; follow the persistent source pointer and reuse the variant. |
| Source shader edit | Reanalyze when the resolved Alpha/Base Color authority changes. An assignment-only edit elsewhere retains classification but clears review; existing variants then report `SOURCE_CHANGED` and default to no mutation unless explicitly reused or replaced with a fresh variant. |
| Ordinary source duplicate | Treat as a distinct source with its own variant. |
| Derived duplicate | Detect copied UUID/metadata and report `DUPLICATED_DERIVED`; never choose silently. |
| Slot reorder | Resolve by datablock identity, not slot number, and reuse matching variants. |
| Slot reassignment | Invalidate and resolve the new source; never apply an old variant automatically. |
| Derived slot removed | Reappend the exact valid datablock after reviewed preflight. |
| Derived datablock deleted | Preflight creation of a new variant. |
| Derived manually edited | Preserve it and require an explicit reuse/new choice. |
| Source deleted | Mark the variant orphaned; never chain another variant from it. |
| Save/reopen | Restore the source pointer and verify fingerprints before reuse. |

## Milestone 4A: workflow-friction hardening

- Add synthetic regressions for a resolved material with face-local UV
  uncertainty alongside an unrelated unresolved material, and for Analyze →
  Preview → Tab to Object Mode → Apply.
- Replace global assignment vetoes with per-material dispositions: split,
  leave unchanged, or blocked for safety. Preview the exact planned move set.
- Route resolved face-local uncertainty to alpha by the Simple default; Expert
  policy may keep it on the source or skip that material group.
- Replace generic dependency-graph dirtiness with relevant, coalesced recheck
  scopes. Do not rehash participating image pixels or rerasterize geometry for
  selection/mode-only transitions.
- Use the lawful private before/after pair as a required ignored multi-object
  smoke layer when available. Exercise partial unsupported results, out-of-range
  UV addressing, exact-plan Preview and Apply, aggregate partition comparison,
  and preservation. Treat the hand-made after example as a workflow reference,
  not a per-face classification oracle. Keep all assets, helpers, paths, and
  raw output uncommitted.
- Update panel messages, confirmation/completion summaries, README, integration
  API, test guide, and contributor rules to describe the implemented behavior.

Gate: unit and headless Blender tests cover harmless versus real input changes,
preview/plan equivalence, partial success, undo/redo, idempotence, save/reopen,
and registration cleanup. Installed-ZIP Blender 5.2 acceptance must complete
the reported workflow without redundant analysis.

Gate result: the generated and installed-ZIP layers completed locally on
2026-07-25. A later full multi-object private before/after smoke confirmed
out-of-range UV analysis. The user confirmed that extra conservative `MIXED`
faces are correct and that the remaining `OPAQUE` differences come from broad,
hand-made alpha sections in the early-development after example.

The authoritative hardening matrix includes:

- Real dependency-graph events for repeated mode/selection/active-face/
  active-object/multi-object transitions plus unrelated datablock updates.
- Paired topology, vertex, UV, material-index, slot order/content, mesh
  replacement/deletion, shader link/setting, image pixel/reload/pack/replace,
  analysis-setting, undo, redo, and file-load changes.
- Apply-before-deferred-recheck and mutation-during-modal-analysis races with
  zero assignment/publication on mismatch.
- Exact plan-review and confirmation fingerprints, including off-slot derived
  edit/duplicate/delete and create-versus-reuse transitions.
- A generated combined fixture with opaque, alpha-affected, mixed, collapsed
  UV, unresolved, suppressed, unsafe, and metadata-conflict states; test
  partial application, cancellation, rollback, undo/redo, idempotence, and
  save/reopen semantically.
- Clean installed-ZIP Analyze → Preview → Tab → Apply acceptance and separate
  cold-analysis, structural-recheck, Apply-preflight, and full-image-digest
  measurements with recorded instrumentation counters.

## Milestone 4B: main Base Color alpha fallback

- [x] Establish a generated failing regression for an alpha-bearing Base Color
  image alongside connected normal, roughness, emission, and disconnected
  ancillary image nodes.
- [x] Resolve one direct or simply rerouted Base Color Image Texture authority
  when Principled Alpha is genuinely unlinked. Preserve explicit override and
  supported Principled Alpha precedence.
- [x] Distinguish unlinked Alpha from connected invalid/reroute-cycle paths.
  Keep connected unsupported processing explicit and recoverable through a
  manual per-material source.
- [x] Keep classification authority separate from assignment-only material
  state. Ancillary image pixels are not digested; unrelated source-graph edits
  retain analysis but clear exact-plan review.
- [x] Bind review/confirmation to a deterministic fingerprint containing exact
  object/face mutations, current source fingerprints, and derived decisions.
- [x] Characterize Blender 5.2 decoded stored A behavior for generated
  RGB-style/RGBA images, fully opaque A, missing images, and the `STRAIGHT`,
  `PREMUL`, `CHANNEL_PACKED`, and `NONE` alpha modes without changing decoding
  semantics.
- [x] Update README, UI remedies, material support, integration API, testing,
  and performance documentation.
- [x] Pass generated unit/Blender tests, source/archive validation, isolated ZIP
  lifecycle validation, and the provisional 25 percent same-machine
  performance gate.
- [x] Pass the private resolver, exact-plan workflow, out-of-range UV,
  derived-role, immutable-reference, and preservation gates.
- [x] Retire the private semantic lower-bound discrepancy as a release blocker.
  The user confirmed that the 1,176 `OPAQUE` differences reflect broad,
  hand-made material separation in the early-development after example rather
  than an extension classification defect.

## Milestone 4C: Analyze throughput

- [x] Establish generated failing regressions for eligible native bulk image
  reads, bounded/failure fallback, digest/classification parity, one modal
  preparation pass, one UV traversal, and shared-material fingerprint reuse.
- [x] Use Blender's native pixel transfer only when the complete temporary
  working estimate is at most 384 MiB; retain complete-row chunking otherwise.
- [x] Remove the duplicate post-image preparation/signature pass without
  weakening publication-time structural and participating-pixel validation.
- [x] Measure an exact raster allocation candidate against the clipping oracle
  and discard it because its 4.8 percent polygon-phase gain did not meet the
  approved 20 percent keep threshold.
- [x] Re-profile multiprocessing and defer it because the measured 2.14x
  isolated-core gain does not justify Blender serialization, memory,
  cancellation, and process-lifecycle complexity for the projected complete
  workflow.
- [x] Pass the final source/archive validation gate. Unit, headless Blender,
  generated benchmark, and private multi-object/preservation smoke are
  complete. The private aggregate retains 1,176 `OPAQUE` differences from the
  hand-made reference partition; these are diagnostic only.

## Milestone 4D: Analyze responsiveness

- [x] Measure modal initialization, native-image post-processing, polygon
  callbacks, timer scheduling, and publication validation on the generated and
  lawful private stress cases.
- [x] Approve the balanced design: resumable native-image post-processing, a
  1 ms modal timer, a 12 ms between-polygon target, a 4,096-polygon cap, and
  truthful progress stages.
- [x] Add failing generated regressions for image chunking, buffer cleanup,
  deadline scheduling, progress stages, and prior-report preservation.
- [x] Implement the approved image, engine, operator, and private progress-state
  changes without altering public API `1.2` or analysis semantics.
- [x] Pass unit, headless Blender, private workflow/preservation, source/archive,
  generated performance, and installed-ZIP lifecycle gates.
- [x] Record five-run callback, digest, memory, and instrumented modal-cadence
  medians, and block any unexplained established same-machine regression above
  25 percent.
- [x] Complete the installed-ZIP visual stage, progress, and Escape-cancellation
  interaction. The user confirmed Escape cancellation works. The cursor and
  sidebar percentages can briefly disagree and remain a follow-up UX issue.

## Milestone 5: release validation

- [x] Record small, typical-avatar, high-complexity, repeated-UV, and pathological
  benchmark tiers. Establish the first baseline before release and block an
  unexplained same-machine time or memory regression over 25%.
- [x] Validate/build/install the extension ZIP in an isolated Blender
  environment.
- [x] Test enable/disable, analysis immutability, preview/undo, assignment/undo,
  idempotence, save/reopen metadata, and FBX material partitioning.
- [x] Benchmark cold analysis, full image validation, coverage/prefix reuse,
  and mode-exit component recheck. Mode-only rechecks rasterize zero polygons
  and digest zero image rows. The recorded same-machine structural median is
  0.0345 seconds, 4.13 percent of cold analysis.
- [x] Record a distinct final Apply-preflight timing row. The 2026-08-01
  generated median is 0.0353 seconds, 4.89 percent of cold analysis, with zero
  image-digest rows, zero rasterized polygons, and no mutation.
- [x] Complete installed-ZIP Analyze → Preview → Tab → Apply at default UI
  scale without a second analysis.
- [x] Complete the generated two-material interactive partial-apply case in
  `docs/testing.md`.
- [x] Pass the required ignored multi-object before/after smoke for workflow,
  out-of-range UV addressing, exact-plan assignment, and preservation. The
  hand-made after partition is retained as an aggregate diagnostic only.
- [x] Complete the 150 percent UI-scale visual pass.
- [x] Complete required ordinary Unity material/submesh validation.
- Optional: record VRChat SDK/shader validation only as a reference for the
  exact tested versions.

## Milestone 6 — GitHub Actions CI/CD

- [x] Fix Blender 5.2.0 Windows and Linux download identities and hashes.
- [x] Add generated helper and workflow security contracts.
- [x] Add read-only Windows and Linux validation.
- [x] Add protected manual draft-first publication.
- [x] Run the complete local product gate.
- [x] Bound Blender downloads with a 30-second connection timeout, fixed total
  limit, two retries, and partial-file cleanup.
- [x] Use safe Linux tar extraction and version-independent validation ZIP
  discovery.
- [x] Remove actions and credentials from the write-authorized release source
  fetch; use unauthenticated native Git and verify the exact `GITHUB_SHA`.
- [x] Reproduce the first hosted bootstrap failures and add local RED/GREEN
  coverage for Quad9 DoT plus exact archive root discovery.
- [x] Harden Quad9 response validation and pass all authenticated A answers to
  curl's native address fallback.
- [x] Push `ci/automation` after separate approval.
- [ ] Observe both hosted validation checks.
- [ ] Make the repository public after separate approval.
- [ ] Configure required checks, the `release` environment, and immutable
  releases.
- [ ] Dispatch and verify release `1.0.0` after separate approval.

The first hosted run confirmed that Quad9's HTTP/2-only DoH endpoint is
incompatible with the Windows curl path. The approved standard-library Quad9
DoT replacement and pinned HTTPS checksum download pass locally. The Linux
executable locator now uses the exact archive root. Hosted rerun remains the
compatibility authority for both corrections.
Blender native extension-repository hosting remains a separate milestone.

## Public integration boundary

Stable operators use `bpy.ops.alpha_material_separator.*`: capability query,
analyze, select faces, assign materials, and clear results. API 1.2 additively
reports validation state, pending scopes, unsupported scope, material-group
disposition, and planned action. `unsupported_policy="TO_ALPHA"` applies only
to face-local uncertainty in a resolved group; earlier values and scripted
defaults remain compatible. A versioned WindowManager status record exposes
JSON-compatible capabilities, stable status codes, counts, planned changes,
skips, and the analysis ID.

Future CATS code must feature-detect the capability operator, tolerate absence
or incompatible API majors, and use only documented operators/status. This
extension never imports or depends on CATS.

## Version 1.0 exclusions

- Topology cutting, subdivision, or physical object separation.
- Shader rewriting or Unity editor automation.
- Automatic CATS integration.
- Evaluated-modifier topology analysis.
- Arbitrary or ambiguous shader evaluation.
- Automatic make-local or single-user conversion.
- Exact Unity filtering/mipmap/compression/shader simulation.
- Persistent face-result attributes, runtime installers, updaters, telemetry,
  or network access.

## Local commit sequence

1. `docs: revise architecture and implementation plan`
2. `chore: scaffold Blender extension`
3. `test: add material and rasterization characterization`
4. `feat: add alpha analysis and preview`
5. `feat: add safe material assignment`
6. `test: add packaging performance and export validation`
7. `docs: document Unity VRChat workflow and integration API`
8. `a09593b fix: preserve reviewed analysis and apply safe groups`
9. `4c26dfd test: harden revalidation and partial assignment coverage`
10. `1e61993 docs: document partial apply and preview revalidation`

Commits remain local. No push or release occurs without separate approval.
