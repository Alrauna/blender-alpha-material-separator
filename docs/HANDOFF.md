# Repository handoff

Updated: 2026-08-12

## Current branch objective

`feat/gpu-acceleration` is based on `origin/main` commit `6973a44`. It
implements `PLAN.md`, the staged analysis performance plan. The plan's thesis is
that GPU acceleration is a candidate gated on measurement, not a specification:
the CPU implementation stays authoritative, every later target is chosen from a
fresh profile, and a successful outcome does not require shipping GPU code.

Stages 1 through 5 are complete. Stage 6, the GPU feasibility gate, has not
started.

## Decisions

- Implemented on this one branch with a coherent commit per stage, rather than
  the five separate `codex/*` branches `PLAN.md` names. Those would each need
  their own authorized pull request, and stacking production pull requests is
  not permitted. **This deviates from the plan's branch layout and has not been
  confirmed by the user.**
- Stage 5's premise dissolved before it began. High-tier coverage reuse has
  measured faster than cold in every run on this machine since vectorization
  started, so the planned coverage-cache defect investigation has no defect to
  debug. Recorded in `docs/performance.md` as resolved by measurement rather
  than opened as a debugging task.
- Bit-equality with the replaced rasterizer was rejected as a correctness gate
  because that code is not stable under vertex permutation. The gate is the
  order-independent positive-area oracle from `docs/algorithm.md`.
- `addon/core` now depends on numpy, so `tests/unit` runs on Blender's bundled
  interpreter. CI already did this; `docs/testing.md` now matches. The core
  remains free of `bpy`.
- Row prefixes keep a `uint32` accumulator instead of the plan's int64 default.
  The bound is proven and the justification is recorded in
  `docs/performance.md`.

## Commits

- `af5de91` — vectorized image extraction and per-phase instrumentation
  (Stages 1 and 2);
- `f01a016` — cross-section scanline rasterization (Stage 3);
- `8b1b812` — `numpy.cumsum` row prefixes (Stage 4).

## Verification evidence

Fresh local results on this branch:

- unit suite on Blender's bundled Python 3.13.13: 132 passed;
- headless Blender suite: exit 0, all 18 modules OK, including the new
  `ALPHA_MATERIAL_SEPARATOR_IMAGE_DATA_OK`;
- `git diff --check`: clean before each commit;
- same-session before/after benchmarks per stage, each with wall time and peak
  working set, recorded in `docs/performance.md`.

High-tier cold analysis across the three landed changes, each percentage
same-session:

| Stage | Before | After | Change |
| --- | ---: | ---: | ---: |
| Image extraction | 80.239 s | 23.101 s | -71.2% |
| Rasterization | 22.825 s | 14.612 s | -36.0% |
| Row prefixes | 14.049 s | 11.342 s | -19.3% |

Peak working set never regressed; it fell slightly at Stages 1 and 4 and was
flat at Stage 3. Coverage totals, run counts, and scanline counts are identical
before and after every stage on the benchmark fixtures.

## Limitations

- **Coverage is slightly tighter than before on some exactly-representable
  triangles.** The replaced rasterizer emitted cells whose intersection with the
  triangle has zero area, contradicting its own documented positive-area rule;
  18 of 4,000 quarter-grid triangles were affected. The new code matches the
  oracle exactly there. The dropped cells have no positive-area overlap, so the
  only possible effect is fewer spurious alpha classifications, and the new path
  never under-covers the oracle across 14,000 randomized triangles. This is a
  real behavior change that has not been confirmed by the user.
- Stage 4 improved the high tier 19.3 percent, marginally below the repository's
  20 percent keep threshold. Recorded rather than rounded; the reasoning for
  keeping it is in `docs/performance.md`.
- No private characterization has been run on this branch. No packaging,
  installed-ZIP, export, Unity, or human interaction gate has been run, none of
  which this branch's changes have yet required.
- Rasterization is again the dominant cost at 49.3 percent of an 11.342 s high
  tier, followed by run counting at 12.6 percent and UV traversal at 9.5
  percent. About 18.9 percent remains outside the instrumented phases.

## Next action

Begin Stage 6A, the discardable GPU capability spike on scale rather than
existence. Every Stage 6 comparison must be against the current optimized CPU
implementation at 11.342 s, never the original baseline and never the pre-numpy
implementation. No production GPU backend may land until Stage 6J's keep/abort
gate passes at 20 percent whole-workflow improvement.

Push and pull-request creation require separate authorization and have not been
requested.
