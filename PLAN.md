# Blender Alpha Material Separator 0.1 implementation plan

Status: approved for local implementation on
`feat/alpha-material-separator-0.1`, with mandatory approval checkpoints.

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
- Treat Blender notifications as eviction hints. Revalidate authoritative
  content before preview or assignment and refuse stale reports.
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
- Block source-material groups containing suppressed, unsupported, unsafe, or
  ambiguous faces by default.
- Store namespaced metadata and a source-material pointer only on the local
  derived material; never tag the source merely for identity.
- Refuse multi-user, linked, read-only, or override-restricted mesh mutation.
- Never overwrite, delete, rename, localize, or make user data single-user.

Required identity behavior:

| Change | Behavior |
| --- | --- |
| Source rename | Reanalyze; follow the persistent source pointer and reuse the variant. |
| Source shader edit | Report `SOURCE_CHANGED`; default to no mutation. Explicitly reuse or create a fresh variant without overwriting the old one. |
| Ordinary source duplicate | Treat as a distinct source with its own variant. |
| Derived duplicate | Detect copied UUID/metadata and report `DUPLICATED_DERIVED`; never choose silently. |
| Slot reorder | Resolve by datablock identity, not slot number, and reuse matching variants. |
| Slot reassignment | Invalidate and resolve the new source; never apply an old variant automatically. |
| Derived slot removed | Reappend the exact valid datablock after reviewed preflight. |
| Derived datablock deleted | Preflight creation of a new variant. |
| Derived manually edited | Preserve it and require an explicit reuse/new choice. |
| Source deleted | Mark the variant orphaned; never chain another variant from it. |
| Save/reopen | Restore the source pointer and verify fingerprints before reuse. |

## Milestone 5: release validation

- Record small, typical-avatar, high-complexity, repeated-UV, and pathological
  benchmark tiers. Establish the first baseline before release and block an
  unexplained same-machine time or memory regression over 25%.
- Validate/build/install the extension ZIP in an isolated Blender environment.
- Test enable/disable, analysis immutability, preview/undo, assignment/undo,
  idempotence, save/reopen metadata, and FBX material partitioning.
- Require ordinary Unity material/submesh validation. Record VRChat SDK/shader
  validation only as a reference for the exact tested versions.

## Public integration boundary

Stable operators use `bpy.ops.alpha_material_separator.*`: capability query,
analyze, select faces, assign materials, and clear results. A versioned
WindowManager status record exposes JSON-compatible capabilities, stable status
codes, counts, planned changes, skips, and the analysis ID.

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

Commits remain local. No push or release occurs without separate approval.
