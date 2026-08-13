# Repository handoff

Updated: 2026-08-13

## Current branch objective

`feat/gpu-acceleration` is based on `origin/main` commit `6973a44`. It
implements `PLAN.md`, the staged analysis performance plan. The plan's thesis is
that GPU acceleration is a candidate gated on measurement, not a specification:
the CPU implementation stays authoritative, every later target is chosen from a
fresh profile, and a successful outcome does not require shipping GPU code.

Stages 1 through 5 are complete. Stage 6A and 6B are complete, 6B twice: once
against the grid fixture and then again against a realistic tier that ranks the
candidates differently. Every CPU candidate the re-ranking surfaced has landed:
flat-array coverage, batched rasterization, and vectorized UV traversal.

The GPU path is built and integrated behind a capability probe, authorized by
the user across nine commit boundaries after `docs/gpu-rasterization.md` was
approved. It is exact, and after two rounds of dispatch scheduling work it
clears the keep gate at **-27.2% cold** with re-analysis level and a lower
worst-case callback than the CPU path. The branch's implementation work is
complete; what remains is the packaging and release gates it has never run.

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

- Stage 6 stopped at the ranking rather than prototyping a dataflow, because the
  surviving GPU candidate and the CPU alternative share a prerequisite that
  moves the baseline. Recorded in `docs/performance.md`.
- Two claims in the first version of that ranking were wrong and are corrected
  in place: Blender's shader interface *does* expose exact `double` and
  `int64_t`, and the bandwidth-bound reduction measurements do *not* price the
  fused rasterize-and-classify candidate, which has a different dataflow.
- The grid fixture misranks accelerators, so a `realistic` tier was added rather
  than continuing to rank from it. Its shape was learned from an authorized
  private asset and then reproduced from generated data, so the evidence is
  committable; no private number entered the repository. Ranking uses this tier,
  not High complexity.
- Classification was rejected at 14.3 percent on the grid and is 25.8 percent on
  the realistic tier, which clears the keep threshold. **The Stage 6B ranking
  changed as a result and the earlier grid-based ranking is superseded.**
- Flat-array coverage was approved and implemented after a scratchpad prototype
  measured batched counting at 9.5x on the realistic tier's real run
  distribution, exact against the shipped counter. Scope was deliberately cut to
  counting plus the representation; batched rasterization is a separate,
  unapproved decision.
- `Coverage` uses one `(3, n)` int64 array rather than three arrays or a dict.
  Chosen on measurement, not taste: it is cheaper to build than the dict it
  replaces, which is why rasterization improved as well.
- `Coverage` sets `eq=False`. A generated `__eq__` would compare span arrays
  with `==` and return an array rather than a bool.
- The unattributed remainder was engine construction, which ran before
  `metrics` existed and so sat outside every phase accumulator. Two timers now
  cover it and unattributed fell 30.7 percent to 11.6 percent. What remains is
  diffuse interpreter overhead in the stepping loop, not a phase.
- `_structural_signature` was vectorized after establishing that its digest
  never leaves the process: every comparison is against a same-process
  recompute, and the `@persistent` handlers on `load_post`, `undo_post` and
  `redo_post` blank `report_json` and `analysis_id`. The digests written into
  the `.blend` come from `material_fingerprint`, which it does not feed. The
  version tag moved to `STRUCTURAL_V2` to record the encoding change.
- Stage 3's own name — vectorize the rasterizer — is measured, approved and
  built. numpy inside the per-polygon call was 2.7x slower and stays rejected.
  Batching was re-measured against the current implementation, projected 5.8x,
  and shipped at 3.91x on the phase and 34.2 percent on the realistic tier. Two
  findings drove the throughput: a three-key `lexsort` was 58 percent of the
  first prototype and one composite int64 key replaced it at about 10x, and a
  256-polygon chunk is about 20 percent faster than any other window because the
  intermediates stay in cache.
- Rasterization is deferred exactly like counting: `_analyze_polygon` records a
  coverage-cache miss and `_flush_pending` rasterizes the whole step chunk. The
  chunk size is a measured constant, not the caller's step budget.
- Deferring the lookups ahead of the stores makes both copies of an in-chunk
  duplicate coverage key miss the cache. `_rasterize_pending` rasterizes each
  key once and moves the duplicate back to the hit counter, so all eight
  benchmark counters are identical before and after.
- A polygon's loop triangles are a slice of one array rather than a dict entry.
  Blender emits them grouped by polygon and ascending, but `_triangle_layout`
  stable-sorts when they are not, because depending on the ordering buys nothing
  over a sort of an already-sorted array. `_loop_triangle_order_test` pins it.
- Texel grids are cached per `(UV map, width, height)`, not per material slot.
  Sixteen realistic-tier slots share four image sizes, so that is four scaled
  arrays. It is the first change on this branch to raise peak memory, by 0.4
  percent; scaling per polygon instead costs more than the phase saves.
- A non-finite UV still aborts the entire analysis rather than becoming a
  per-face `INVALID_UV`. The vectorized path reproduces the abort deliberately
  and `_non_finite_uv_test` pins it. **Turning it into a per-face reason is a
  behavior change and has not been proposed to the user.**
- The GPU path bypasses the coverage cache entirely, digest included, because a
  kernel that fuses rasterizing and counting cannot use a geometry-keyed span
  entry. `coverage_cache_bypassed` replaces the hit and miss counters on that
  path. This is the design's one report-visible change and it was approved.
- Both paths classify through one rule. `classify_stats` was added to
  `core.classify` so the GPU path reaches it with counters instead of faking a
  `Coverage`; `classify_counted` delegates to it.
- Commit boundaries 1 and 2 of the approved design were merged. Behaviour, scope,
  risk and architecture were unchanged; only granularity.
- GLSL leaves `%` undefined when either operand is negative and the driver acts
  on that. Power-of-two image dimensions hide it, which is why the self-test
  fixture is 53x17. Detail in `docs/gpu-rasterization.md`.
- A failed self-test is a test failure, not a skip. `gpu_raster.reason()` returns
  a `MISMATCH`-prefixed string in that case and the headless tests assert on the
  prefix, so a machine with a wrong GPU fails while a machine with no GPU skips.
- Every GPU measurement before Stage 6K used `step(4096)` with no time budget, a
  cadence the modal operator never reaches because its 12 ms timer cuts the step
  first. The real flush is roughly 1,300 polygons. **Every earlier GPU
  percentage in `docs/performance.md` was taken at the wrong cadence** and the
  6K and 6L tables supersede them.
- Dispatch pipelining was approved and built, and on its own it was worth about
  two points, not the projected 22. The stall it hides is real, but the
  per-dispatch texture allocation and upload underneath it is not hidden by
  anything, and small flushes pay it repeatedly.
- The fix is a submit threshold, not a bigger step. `_GPU_SUBMIT_POLYGONS`
  holds polygons across steps and submits at 16,384. The responsiveness contract
  bounds one `step`, the threshold bounds one dispatch, so neither has to move
  for the other. Approved by the user after the pipelining measurement.
- `_RASTER_BATCH_POLYGONS` no longer chunks the GPU path. It is a CPU cache
  window; on the GPU it only multiplied the fixed per-dispatch cost.
- The GPU path's worst callback is *lower* than the CPU's, 171 ms against
  208 ms, because it builds packed mask textures instead of a 4096-square 2D
  prefix table and only builds that table for the CPU partition.

## Commits

- `af5de91` — vectorized image extraction and per-phase instrumentation
  (Stages 1 and 2);
- `f01a016` — cross-section scanline rasterization (Stage 3);
- `8b1b812` — `numpy.cumsum` row prefixes (Stage 4);
- `f749202` — Stage 6A spike and Stage 6B ranking;
- `3a8b636` — corrected numpy rasterizer projection;
- `34629bf` — corrected the exactness blocker and the fixture's representativeness;
- `405c9f3` — Stage 6 handoff correction;
- `d7e7ae3` — realistic benchmark tier and the re-ranked Stage 6 gate;
- `7b25abd` — flat-array coverage and batched alpha counting;
- `e1f2cbc` — the flat-array coverage result;
- `ca2b4fe` — engine construction instrumentation;
- `0ad3852` — vectorized structural signature;
- `756f03c` — the re-measured batched rasterization result;
- `907246f` — batched rasterization;
- `d20952f` — vectorized UV traversal, cache keys, and triangle layout;
- `33af2e6` — per-chunk raster counters;
- `a54e241` — the Stage 6E transfer floor, exactness and round-trip spikes;
- `290fd99` — the fused GPU kernel result;
- `25671af` — the approved GPU design, and the power-of-two caveat on the
  Stage 6E exactness run;
- `081dcc0` — the kernel, the capability probe, and the REPEAT tests;
- `df47f04` — CLIP, EXTEND and MIRROR;
- `e8b5733` — host-side partitioning, budget trips, and the raster counters;
- `8747074` — engine integration behind the probe, and the equality test;
- `e74464e` — the integrated measurement, which missed the keep gate;
- `13668ba` — the handoff at that decision point;
- `4bbeaf6` — the cross-step pipelining design;
- `2bc5f28` — cross-step dispatch pipelining, measured at -11.9%;
- `075565d` — the submit threshold, which clears the gate at -27.2%.

## GPU findings worth not rediscovering

Full detail is in `docs/performance.md`; the three that would cost a future
agent the most time:

- `GPUTexture` has no write method and its constructor accepts only a `FLOAT`
  buffer, so `R32F` is the only exact CPU-to-GPU channel and it is exact only
  below 2^24. `R32UI` output readback is exact.
- `gpu.texture.from_image()` returns `SRGB8_A8` for byte images and `RGBA16F`
  for float images, so it cannot carry float image data losslessly.
- `gpu.compute.dispatch()` leaves the shader bound, and releasing the shader
  while it is bound hard-crashes Blender on the next bind. `gpu.shader.unbind()`
  is mandatory, not hygiene.
- `double`, `int64_t` and `uint64_t` compile and compute exactly through
  `GPUShaderCreateInfo` on OpenGL/NVIDIA. Metal has no fp64, so `double` cannot
  reach the *Backend-portable* claim level even though it works here.

## Verification evidence

Fresh local results on this branch:

- unit suite on Blender's bundled Python 3.13.13: 141 passed;
- headless Blender suite: exit 0, all 19 modules OK, including
  `ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_OK`;
- `blender --factory-startup --command extension validate addon`: success;
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
| Flat-array coverage | 10.983 s | 6.963 s | -36.6% |

The last two changes were measured on the realistic tier only, since that is the
tier that ranks candidates:

| Change | Before | After | Change |
| --- | ---: | ---: | ---: |
| Signature vectorization | 7.482 s | 6.491 s | -13.2% |
| Batched rasterization | 6.017 s | 3.962 s | -34.2% |
| Vectorized UV traversal | 3.742 s | 2.412 s | -35.5% |
| Per-chunk raster counters | 2.415 s | 2.264 s | -6.2% |

The signature phase itself went 1.188 s to 0.120 s, the rasterization phase
2.625 s to 0.672 s, and the UV phase 1.220 s to 0.247 s. The before-figures are
not comparable to each other: each pair is its own same-session measurement, and
every baseline was re-measured rather than carried over.

The realistic tier went 11.604 s to 6.444 s on the flat-array change, a 44.5
percent improvement.

Peak working set fell slightly at Stages 1 and 4, was flat at Stage 3, and fell
2949.8 MiB to 2080.4 MiB with flat-array coverage. It rose once, 995.9 MiB to
999.7 MiB on the realistic tier, with the UV texel grids. Coverage totals, run
counts, and scanline counts are identical before and after every stage on the
benchmark fixtures.

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
- Private characterization was authorized and run. Its script and output stay in
  the session scratchpad and were never committed, per the user's instruction
  that tests using local references remain local. Only the derived fixture shape
  entered the repository.
- No packaging, installed-ZIP, export, Unity, or human interaction gate has been
  run, none of which this branch's changes have yet required.
- `_record_face` was 11.9 percent of the tier and no phase timer had ever seen
  it: it runs once per polygon at the tail of `_flush_pending`, outside every
  accumulator. Half of it was one `metrics.update` of six raster counters
  through a fresh dict literal, per face. Summing them per chunk instead landed
  at 6.1 percent of the tier.
- Engine construction is fully attributed and was all along. The claim that
  0.21 s of it was unattributed came from subtracting only the prepare and
  signature timers and forgetting the four image phases that `_prepare` nests.
  The whole residual is in the stepping loop.
- The earlier claim that the residual was diffuse overhead needing the
  per-polygon loop replaced is corrected in `docs/performance.md`. Replacing the
  loop's RNA reads was measured at 0.9 percent of the tier and rejected.
- The signature vectorization improved the whole workflow 13.2 percent, below
  the repository's 20 percent keep threshold. Recorded rather than rounded; it
  is kept because the diff is smaller than what it replaces, which is not true
  of most sub-threshold wins.
- The 47 percent attributed to the flat-array change did not transfer from
  high-tier scale. The measured result is 44.5 percent on the realistic tier and
  36.6 percent on the high tier.
- Batched rasterization shipped at 3.91x on the phase against a projected 5.8x.
  The gap is the tuple-to-array flattening and the coverage-key deduplication
  pass, neither of which the prototype paid for. It clears the keep threshold at
  34.2 percent regardless.
- Batched rasterization and the UV vectorization were measured on the realistic
  tier only. The high tier has not been re-measured since flat-array coverage.
- The UV texel grids are the first change on this branch to raise peak memory.
  It is 0.4 percent on the realistic tier, and the resident cost is
  `loops * 16 * (1 + distinct image sizes)` bytes per UV map per object, so a
  mesh with many more loops or many more distinct image sizes would pay more.
  Only the realistic tier has been measured.
- The GPU path is enabled by default on any machine whose probe passes. It now
  clears the gate at 27.2 percent cold with re-analysis at +1.6 percent, level
  within run-to-run spread; the 15.1 percent re-analysis regression recorded
  earlier is gone. One machine, one tier.
- `_GPU_SUBMIT_POLYGONS` is a measured constant for this machine and tier, not
  an adaptive one, exactly like `_RASTER_BATCH_POLYGONS`. A machine with a much
  faster or slower GPU has not been measured, and neither has a mesh whose
  polygons spread across many more images than the tier's five.
- The hold raises peak memory by about 11 MB at 16,384 deferred faces. That was
  computed from the per-face size, not measured with a working-set sample as the
  earlier stages were.
- The integrated measurement is one machine, one driver, one OpenGL backend.
  Metal has no fp64, so `available()` returns False on macOS and those users get
  the CPU path; that is untested on actual hardware.
- The GPU tests skip on a machine without a usable GPU, so CI proves the
  fallback rather than the kernel. Only this machine has run them.
- No packaging or installed-ZIP run has been done since the GPU path landed. It
  adds no dependency and no file outside `addon/adapters/`, but the ZIP gates in
  `docs/testing.md` have not been re-run.

## Next action

Run the packaging and installed-ZIP gates in `docs/testing.md`, which this
branch has never run and which are the only automated gates still outstanding.
The GPU path adds no dependency and no file outside `addon/adapters/`, so this
is expected to pass; it has simply not been done.

Everything the GPU design specified exists: all four address modes, host-side
partitioning for polygons past the span cap, budget trips with the CPU's reason
strings, all six raster counters, a runtime self-test probe, and ten headless
tests including a full-engine equality run and three that cover the dispatch
pipeline's guards. Every one of those ten was verified to fail against a
deliberate break before being kept.

Where the path finished, same session, medians of five:

| Configuration | Cold | vs CPU | Re-analysis | vs CPU | Worst step |
| --- | ---: | ---: | ---: | ---: | ---: |
| CPU | 2.270 s | — | 1.718 s | — | 208 ms |
| GPU, no hold | 2.053 s | -9.6% | 1.925 s | +12.1% | 194 ms |
| GPU, shipped | 1.653 s | -27.2% | 1.745 s | +1.6% | 171 ms |
| GPU, 65,536 per step | 1.530 s | -32.6% | 1.707 s | -0.7% | 488 ms |

The gate is 20 percent and 150,544 face comparisons produced zero differences.

After packaging, the remaining work is release-gate work, not implementation:
the export, Unity, and human interaction gates in `docs/testing.md`, none of
which has been run on this branch.

The one open question no measurement here can settle is portability. Metal has
no fp64, so `available()` returns False on macOS and those users get the CPU
path. That is untested on actual hardware, and it means the CPU rasterizer is
permanent and both implementations stay bound by the same bit-exactness tests.

Push and pull-request creation require separate authorization and have not been
requested.
