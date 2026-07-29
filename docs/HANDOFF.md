# Repository handoff

Updated: 2026-07-29

## Current objective

Obtain approval for the Preview component-selection fix design. Preview
currently replaces polygon selection correctly but can retain stale edge and
vertex flags from earlier Edit Mode work, making opaque regions look selected.

## Completed work

- Reproduced the Preview visual-noise defect through the real Analyze and
  Preview operators with a generated three-face mesh. The target face set was
  correct, but every preselected edge and vertex survived.
- Confirmed the root cause: `select_faces.py` writes `MeshPolygon.select` but
  does not normalize `MeshEdge.select` or `MeshVertex.select` before entering
  face-select Edit Mode. A generated control that cleared those component flags
  retained only components belonging to selected faces.
- Confirmed that a shared boundary edge between a selected alpha face and an
  opaque neighbor must remain highlighted in Blender face-select mode; this is
  not an erroneous extra selection.
- Strengthened `AGENTS.md` development guidance so Superpowers explicitly owns
  the investigate → design → approval → plan → approval → TDD → review →
  verification → commit lifecycle. Ponytail now minimizes scope inside those
  phases and cannot bypass them.
- Added a memory-bounded Blender-native `Image.pixels.foreach_get` path.
  The complete temporary working estimate must be at most 384 MiB.
- Retained the existing complete-row chunked path for explicit chunking,
  oversized images, memory failure, or unavailable/rejected native reads.
- Preserved identical participating-channel digests, affected-texel grids, and
  non-finite-value rejection across both reader paths.
- Removed the duplicate modal `_prepare` pass after deferred image reads.
  Completed snapshots are attached to the already prepared objects and combined
  with the authoritative structural signature.
- Removed duplicate geometry/UV/signature work from `_prepare`; the existing
  structural signature remains authoritative for mesh, slot, resolver, UV,
  addressing, image state, and configuration inputs.
- Reused one material fingerprint per material datablock in an assignment
  signature.
- Added generated regressions for bulk/chunk parity and fallback, supported
  component/channel combinations, non-finite pixels, one modal preparation
  pass, one UV traversal, and shared-material fingerprint reuse.
- Tested an allocation-reduced exact raster row implementation. It preserved
  the clipping-oracle output but improved the representative polygon phase by
  only 4.8 percent, below the approved 20 percent threshold, so it was removed.
- Deferred multiprocessing. Four pure-core workers reached 2.14x in isolation,
  but the original whole-workflow projection was about 1.29x and became less
  compelling after the retained single-process improvements.
- Updated performance/testing documentation and `PLAN.md`.
- Rebuilt and validated the ignored extension ZIP.
- Created local commit `9264fec perf: reduce analyze preparation overhead`.

## Important decisions and constraints

- Production defects require systematic debugging before edits. Product,
  architecture, UX, API, cache, assignment, resolver, and performance changes
  require an approved design and test-first plan before implementation.
- Inline `executing-plans` is the default. Subagent or parallel execution
  requires an explicit user request and safely isolated independent work.
- Version remains `0.1.0`; API remains `1.2`.
- Exact positive-area rasterization, deterministic budgets, classifications,
  preview/apply behavior, and public payloads are unchanged.
- Full participating-pixel digests remain authoritative. No timestamp or
  `Image.is_dirty` shortcut was added.
- The bulk reader is a bounded optimization, not a separate semantic path.
- The 8K case intentionally uses row chunks under the 384 MiB cap.
- Do not add multiprocessing unless a future post-profile demonstrates at
  least 20 percent complete-workflow improvement with acceptable memory,
  cancellation, and Blender lifecycle behavior.
- Preserve the current branch. `AGENTS.md` now requires explicit-path staging
  and regular coherent commits after verified units; do not push without
  explicit approval.

## Files changed and why

- `addon/adapters/image_data.py`: bounded native bulk read with existing
  chunked fallback.
- `addon/adapters/analysis.py`: one preparation pass, authoritative combined
  input signature, and per-signature material fingerprint reuse.
- `tests/blender/test_analysis_preview.py`: generated reader and pass-count
  regressions.
- `docs/performance.md`: measured medians, memory, private diagnostic, discarded
  raster experiment, and multiprocessing decision.
- `docs/testing.md`: reader-path and single-pass test contracts.
- `PLAN.md`: completed Analyze-throughput milestone.
- `AGENTS.md`: durable development guidance now also requires regular scoped
  commits, staged-diff inspection, and the full proportional Superpowers
  lifecycle with Ponytail constrained to scope reduction inside each phase.
- `docs/HANDOFF.md`: current milestone state and evidence.
- Ignored only: rebuilt `.packaged-releases/alpha_material_separator-0.1.0.zip`
  and benchmark/test output under `.test-output/`.

## Validation commands and results

RED evidence:

```powershell
python -m unittest `
  tests.unit.test_rasterization.RasterizationTests.test_scanlines_do_not_allocate_clipped_polygons `
  -v
```

Failed as intended with 104 `_clip_y` calls. The exact candidate later passed
the oracle but was removed for insufficient measured gain.

The Blender regression suite also failed as intended before each retained
production edit:

- native bulk reader constant/path absent;
- modal inputs prepared twice;
- UV layers traversed four times instead of two;
- one shared material fingerprinted twice.

GREEN correctness:

```powershell
python -m unittest discover -s tests/unit -t . -v
```

Result: 51/51 passed.

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Result: passed through `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, including
analysis/preview, assignment, identity, FBX, preservation, UX, revalidation,
characterization, and lifecycle tests.

```powershell
.\scripts\run_benchmarks.ps1 -Blender $Blender52
```

Result: passed one discarded warm-up plus five measured runs. Current cold
medians were 0.723s small, 8.538s typical, 82.812s high, and 2.028s tiled.
Compared with the prior recorded run, changes were -8.5%, -32.1%, +4.7%, and
+0.9%. High-tier peak working set was about 2.90 GiB, within 2% of the prior
record. Digest medians were 0.073s at 1K, 0.291s at 2K, 1.242s at 4K, and
47.094s at 8K. Structural revalidation remained below both targets at 0.0385s,
4.89% of cold analysis, with zero digest rows and zero rasterized polygons.

Private diagnostic re-profile:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python .test-output\profile_current_analysis.py -- `
  .local-references\default-example\before.blend
```

The ignored profiler was deleted after use. The anonymous aggregate
classifications were unchanged. Total diagnostic time fell from 82.48s to
46.09s; image preparation fell from 38.76s to 10.20s; preparation was 2.91s,
polygon analysis 31.28s, and publication 1.70s.

Private required smoke:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

Analyze, Preview/Apply equivalence, out-of-range addressing, mutation
allowlist, preservation, and immutable-reference checks passed. The command
ended nonzero only for the established 1,176-face semantic lower-bound
discrepancy: those reference-alpha faces still classify `OPAQUE`. Planned and
applied faces remained 65,773; no new mismatch was introduced.

Source and archive:

```powershell
& $Blender52 --factory-startup --command extension validate addon
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

All passed. The ignored archive is 65,586 bytes with SHA-256
`CF4C3E39B2CD6A401E4261DCAFAF25D6051FBF19ADC4808C8FBBEE0C7D4F33A4`.

## Known failures, warnings, and unverified assumptions

- Preview selection has a confirmed visual-noise bug when stale vertex or edge
  selection flags exist. Material assignment remains correct because it uses
  the reviewed face plan, not edge or vertex selection.
- The established 1,176-face private `OPAQUE` lower-bound discrepancy remains
  open and is unrelated to this performance milestone.
- The private 82.48s-to-46.09s comparison is a single diagnostic run. The
  generated warm-up-plus-five benchmark is the regression authority.
- No clean-profile installed-ZIP interaction was repeated because this
  milestone changes Analyze internals rather than registration or UI behavior.
- Ordinary Unity material/submesh validation remains a release requirement.
- Expected warnings remain Blender's bundled Grease Pencil brush-path warning,
  the deliberately exercised stale-input warning, and Git LF/CRLF notices.

## Remaining tasks

1. After design approval, add a generated failing Preview regression that
   preselects stale components on adjacent and disconnected opaque faces.
2. Implement the smallest selection-normalization fix and verify REPLACE, ADD,
   SUBTRACT, repeated Preview, multi-object Edit Mode, review-token retention,
   and assignment-plan equivalence.
3. Run the full change gate and private before/after Preview smoke.
4. Investigate the private 1,176-face `OPAQUE` lower-bound misses separately,
   using ignored diagnostics and a generated failing regression before any
   production change.
5. Complete the remaining installed-ZIP interaction checks in
   `docs/testing.md` if strict release sign-off is desired.
6. Record the distinct final Apply-preflight timing and the interactive
   two-material partial-apply check.
7. Complete the 150% UI-scale pass and user-performed ordinary Unity
   material/submesh acceptance.

## Recommended next action

Approve the minimal Preview selection-normalization design, then prepare its
test-first implementation plan before editing production code.
