# Blender Alpha Material Separator 0.1 implementation plan

Status: milestones 0-4A are implemented and verified locally on
`feat/alpha-material-separator-0.1`. The workflow-friction hardening prompted
by real-file testing is complete in commits `a09593b`, `4c26dfd`, and
`1e61993`: safe groups apply independently, exact-plan preview survives
harmless selection/mode changes, and the installed-ZIP Analyze → Preview →
Tab → Apply workflow no longer requires redundant analysis. Milestone 5 is
partially complete. Manual Unity material/submesh validation remains a release
gate; VRChat validation remains optional stack-specific evidence.

## Product outcome

Version 0.1 analyzes selected original/base mesh polygons, reports and previews
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
  `0.1.0`, and maintainer `Alrauna`.
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
  UV addressing, exact-plan Preview and Apply, semantic reference-face coverage,
  and preservation. Treat the after example as a human-tuned lower bound:
  conservative additional alpha and `MIXED` faces are valid, while missed
  reference-alpha faces require an explicit reason. Keep all assets, helpers,
  paths, and raw output uncommitted.
- Update panel messages, confirmation/completion summaries, README, integration
  API, test guide, and contributor rules to describe the implemented behavior.

Gate: unit and headless Blender tests cover harmless versus real input changes,
preview/plan equivalence, partial success, undo/redo, idempotence, save/reopen,
and registration cleanup. Installed-ZIP Blender 5.2 acceptance must complete
the reported workflow without redundant analysis.

Gate result: the generated and installed-ZIP layers completed locally on
2026-07-25. A later full multi-object private before/after smoke confirmed
out-of-range UV analysis. The user confirmed that extra conservative `MIXED`
faces are correct; unresolved reference-alpha faces remain an open item.

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
- [ ] Resolve the remaining private semantic lower-bound discrepancy. The
  remaining reference-alpha faces are currently classified `OPAQUE` from their
  decoded participating A channel; investigate separately without broadening
  resolver scope or changing raster margin in this milestone.

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
- [ ] Record a distinct final Apply-preflight timing row. Correctness and
  instrumentation are covered, but the released performance table does not yet
  isolate that timing.
- [x] Complete installed-ZIP Analyze → Preview → Tab → Apply at default UI
  scale without a second analysis.
- [ ] Complete the generated two-material interactive partial-apply case in
  `docs/testing.md`.
- [ ] Resolve and pass the required ignored multi-object before/after smoke.
  Out-of-range UV addressing passes and conservative extra faces are allowed;
  the remaining reference-alpha discrepancy is classified opaque.
- [ ] Complete the 150 percent UI-scale visual pass.
- [ ] Complete required ordinary Unity material/submesh validation.
- Optional: record VRChat SDK/shader validation only as a reference for the
  exact tested versions.

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

## Version 0.1 exclusions

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
