# Repository handoff

Updated: 2026-08-13

## Current branch objective

`feat/gpu-fp32-support` is based on `origin/main` commit `343a575`, which is
pull request 20 — the whole of `feat/gpu-acceleration`, merged. Its objective
was the experiment recorded under *Future work* in `docs/gpu-rasterization.md`:
measure how often an fp32 kernel would actually disagree with the CPU, and
decide from that whether an fp32 fast path is worth having.

It disagreed on nothing, so the branch went past the experiment and shipped what
the answer allows. Single precision is now the default GPU path; double
precision is **High precision GPU acceleration**, its own checkbox in Expert
Analysis Settings. A machine without fp64 — Apple Silicon, Intel Alchemist —
loses that checkbox and keeps acceleration, which is the whole point. The design
is `docs/gpu-fp32-precision.md`, approved by the user, and all six of its commit
boundaries are implemented, measured, and validated.

**The branch is complete and unpushed. No pull request exists and neither push
nor pull-request creation has been authorized.** Everything on this page below
the fp32 material is the merged branch's record, kept because this work is a
direct continuation of it.

### The merged branch

`feat/gpu-acceleration` was based on `origin/main` commit `6973a44`. It
implemented `PLAN.md`, the staged analysis performance plan. The plan's thesis is
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
worst-case callback than the CPU path.

Two later user requests landed on top: the Metal deny list became a runtime fp64
measurement, and Expert Analysis Settings gained a manual **Disable GPU
acceleration** fallback. The branch's implementation work is complete; what
remains is the packaging and release gates.

## Decisions

### Single precision

- One templated GLSL source produces both kernels. The scalar type and its
  constructors are substituted, so the fp64 kernel is byte-identical to `main`
  and the two cannot drift apart by editing one of them.
- **Precision is the analysis input, not the device.** `AnalysisConfig` carries
  `use_gpu` and `high_precision`, and `precision()` resolves them to `EXACT` or
  `FP32`, which is what enters `payload()`. The CPU and the fp64 kernel
  reproduce each other bit for bit, so three of the four combinations are one
  input; only crossing into or out of fp32 changes the numbers.
- **A payload field alone cannot invalidate a report.** `validate_report`
  recomputes the input signature from `report.config`, never from the current
  settings, so an existing report can only go stale through an RNA `update=`
  callback. `_precision_changed` in `addon/properties.py` compares the width the
  two checkboxes now resolve to against the width the report was analyzed at and
  calls `runtime.mark_dirty("SETTINGS_CHANGED")` only when they differ. **The
  design assumed the signature did this by itself; it does not.** Recorded as a
  deviation in `docs/gpu-fp32-precision.md`.
- fp64 now gates only `high_precision=True`. The probe runs the self-test once
  per precision per process, and the fp32 self-test has its own fixture, since
  the fp64 one cannot discriminate a wrong fp32 kernel.
- **Zero disagreements on the unmodified realistic tier is arithmetic, not
  evidence.** Blender stores UVs as float32 and the tier's images are all
  power-of-two, so `uv * dimension` is an exponent shift and exact at 24 bits;
  its axis-aligned quads give exact diagonal slopes too. That is why the gate
  also ran a jittered tier and a magnitude control, and why the claim in
  `docs/performance.md` is measured rather than structural.
- The exactness invariant in `AGENTS.md` was amended rather than quietly bent.
  Single precision on the default GPU path is named as the only approved
  departure, measured before it ships, and switchable off. The user approved the
  wording verbatim before implementation began.

### The merged GPU branch

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
- fp64 is measured, not denied by backend name. `_has_fp64()` runs one `double`
  through push constants and requires the exact bits back, which catches both a
  backend that rejects `double` and one that silently computes it as `float`.
  The second case would otherwise reach the self-test and be reported as a
  defect. Requested by the user in place of the Metal deny list.
- The manual **Disable GPU acceleration** toggle enforces its lock in the
  property's `get=`, not in the panel row, because the engine and any script read
  the property. Its `set=` only stores, since a property with `get=` and no
  `set=` is read-only and would never toggle.
- The toggle is outside `ANALYSIS_SETTING_NAMES` and outside
  `AnalysisConfig.payload()`, and is not mirrored onto the analyze operator. The
  device is not an analysis parameter, so it must not reset with the settings,
  must not enter the input signature, and has no place in the published surface.

## Commits

On `feat/gpu-fp32-support`, in order:

- `1f6ac48`, `f7df947` — the ships-on-automation decision, and the handoff that
  pointed at the fp32 question;
- `669aacb` — the approved fp32 design;
- `c551c93` — its test-first plan;
- `b47db17` — the kernel templated on its scalar type;
- `84edb27` — the fp32 kernel, its own self-test fixture, and the probe split;
- `1112f65` — the first three plan deviations;
- `f42833d` — **High precision GPU acceleration** as its own setting and panel
  row;
- `185d58d` — precision as an analysis input, plus the staleness callback the
  plan did not anticipate;
- `d5b41d0` — the measurement, and the flipped default;
- `49d676c` — the documentation pass carrying the `AGENTS.md` amendment, the
  README *Speed* rewrite, `docs/gpu-rasterization.md`, and this handoff;
- the version bump to 1.4.1. The release itself is not made: no tag, no
  published archive, and the built ZIP stays out of the repository.

From the merged `feat/gpu-acceleration`:

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
- `075565d` — the submit threshold, which clears the gate at -27.2%;
- `01d3443`, `17e986c`, `1bd4bbc` — handoff, release 1.4.0, and the
  installed-ZIP isolation fix;
- `c9a5c9f` — fp64 measured at runtime in place of the Metal deny list;
- `6077b25` — the manual **Disable GPU acceleration** fallback;
- `543f5d9` — the README's Speed section and the corrected portability risk.

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
  reach the *Backend-portable* claim level even though it works here. That is
  detected at runtime by `_has_fp64()` rather than by backend name.

## Verification evidence

Fresh local results at fp32 branch completion:

- unit suite on Blender's bundled Python 3.13.13: 143 passed in 8.0 s;
- headless Blender suite twice, both exit 0. Default run reports
  `ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_SKIPPED`, which is the CPU fallback
  proven; the run with `ALPHA_MATERIAL_SEPARATOR_GPU_IN_BACKGROUND=1` reports
  `ALPHA_MATERIAL_SEPARATOR_GPU_RASTER_TESTS_OK`, which is the kernel proven;
- `blender --factory-startup --command extension validate addon`: success;
- clean rebuild, archive validation success, and the isolated install gate
  `ALPHA_MATERIAL_SEPARATOR_INSTALLED_ZIP_TEST_OK`, run twice: at 1.4.0
  (102,216 bytes) when the fp32 work was complete, and again at 1.4.1
  (102,218 bytes) after the version bump. Install status was `Installed`, not
  `Reinstalled`, both times, which is the tell that the isolated root held;
- `git diff --check`: clean before each commit;
- both probe outcomes hand-run in a real Blender window **before the fp32
  work**: Windows/OpenGL, where **Disable GPU acceleration** was unchecked and
  usable, and a Mac, where it came up checked, greyed out, and captioned.
  Neither run was timed, and the Mac outcome has since changed by design — see
  *Limitations*;
- same-session before/after benchmarks per stage, each with wall time and peak
  working set, recorded in `docs/performance.md`.

The fp32 gate, same session, realistic tier, 150,544 faces, three
configurations interleaved, medians of eleven:

| Configuration | Cold | vs CPU | Raster phase | Worst step |
| --- | ---: | ---: | ---: | ---: |
| CPU | 2.400 s | — | 0.517 s | 180 ms |
| GPU, high precision | 1.879 s | -21.7% | 0.229 s | 210 ms |
| **GPU, default fp32** | **1.819 s** | **-24.2%** | **0.193 s** | 209 ms |

fp32 against the fp64 oracle: 0 of 150,544 faces reclassified on the tier, and
still 0 with the tier's UVs jittered off their exactness, which does move 1.79
percent of covered-texel counts. A magnitude control confirms the apparatus can
see a difference — fp32 diverges as soon as a coordinate stops fitting in 24
bits. Full detail, including why the unjittered zero is arithmetic rather than
luck, is in `docs/performance.md`.

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
  Only that machine has timings.
- **The macOS hand check no longer describes what a Mac does.** It was run
  before fp32: Metal returned `NO_FP64`, so **Disable GPU acceleration** came up
  checked and greyed out, which confirmed the reason string reached the panel.
  On this branch that same `NO_FP64` greys out **High precision GPU
  acceleration** instead and leaves acceleration on. Nobody has put a Mac in
  front of the new panel, and no Mac has ever produced a timing. The Windows
  hand check still holds.
- **Disable GPU acceleration** in Expert Analysis Settings forces the CPU path.
  Neither it nor the high-precision checkbox is in `ANALYSIS_SETTING_NAMES`, so
  neither resets with the analysis settings. What they resolve to — `EXACT` or
  `FP32` — *is* in `AnalysisConfig.payload()`, so a change that moves the width
  marks a completed report stale and one that does not, does not. The earlier
  claim on this page that the device can never invalidate a report was true of
  the merged branch and is not true of this one.
- **Single precision is a real departure from the exactness invariant**, now
  named as such in `AGENTS.md`. A span boundary can move by a few ulps on the
  default path. It reclassified nothing across the measurements above, but that
  is a measurement on one asset shape on one GPU, not a proof. A reader who
  needs the CPU's exact numbers has one checkbox.
- The fp32 self-test is the only thing standing between a wrong single-precision
  kernel and a wrong report, and it has run on one GPU. A driver that rounds
  differently would have to fail that fixture to be caught.
- The disagreement measurement used the realistic tier and a jittered copy of
  it. No private asset, no non-power-of-two atlas, and no UV coordinate above
  the tier's range was measured against the fp64 oracle. The magnitude control
  says divergence starts where 24-bit representability ends, which bounds the
  risk but does not survey real content.
- `assert_the_probe_measures_fp64` still hard-requires fp64, so the headless GPU
  suite cannot pass on a machine that only has the default path. Recorded as
  future work in `docs/gpu-fp32-precision.md`; this machine has fp64, so nothing
  is being skipped silently here.
- The GPU tests skip on a machine without a usable GPU, so CI proves the
  fallback rather than the kernel. Only this machine has run them, and only with
  `ALPHA_MATERIAL_SEPARATOR_GPU_IN_BACKGROUND` set: a background Blender does not
  probe the GPU without it, because a machine with no display server cannot
  survive `gpu.init()` in a way Python can catch. Branch completion therefore
  needs the headless suite twice, once each way.
- The 29 human-interaction checkboxes in `docs/testing.md` were last confirmed
  on 2026-08-01, before any of the GPU work. The new Expert checkbox has since
  been exercised by hand on Windows and macOS, but the Analyze, progress, and
  cancellation rows have not been re-run against the GPU path and will not be
  before merge: the owner's decision on 2026-08-13 is that the branch ships on
  its automated gates plus the two-platform hand check already done, and that
  anything the automation missed arrives as an issue.
- `run_benchmarks.py` on the GPU path exits 11 with an access violation after
  its results are written. Pre-existing, not caused by the background gate, not
  reproduced by the headless suite with the same opt-in, and not fixed by
  clearing the mask textures. Recorded in `docs/performance.md`. Whether an
  interactive Blender has the same teardown fault on quit is unknown; checking
  it needs a human at a running Blender, so it stays unknown by the same
  decision. A crash report naming teardown after an analysis is the signal that
  this is the cause.
- The manual toggle does not survive a file load, on either `load_ui` setting.
  Neither does `max_scanlines`, so this is the settings group's ordinary
  session lifetime rather than anything specific to the toggle. Measured, not
  assumed.

## Next action

Review the branch and decide whether it gets pushed. Push and pull-request
creation each require explicit authorization and neither has been given, so
nothing leaves this machine until the owner says so.

What to look at, in order:

1. The approval block at the end of `docs/gpu-fp32-precision.md`. Item 1, the
   `AGENTS.md` amendment, was approved verbatim and is in `AGENTS.md`. Items 2,
   3 and 4 — precision as an analysis input, the panel copy for a GPU without
   fp64, and the measurement gate's acceptance criteria — were built as designed
   and reviewed only by their author.
2. `_precision_changed` in `addon/properties.py`. It is the only production code
   the approved plan did not contain, and it is what makes a width change
   invalidate a completed report.
3. The default flip itself. Every other part of this branch is reversible with a
   checkbox; this is the one that changes what an unattended user gets.

The open behavioural question a human could settle in a minute is the macOS
panel: fp32 default on, **High precision GPU acceleration** greyed out,
acceleration still running. Nobody has seen it.

### The merged branch's closing record

Pull request 20 is merged as `343a575`. Every check was green on Windows, Linux,
and macOS.

Everything the GPU design specified exists: all four address modes, host-side
partitioning for polygons past the span cap, budget trips with the CPU's reason
strings, all six raster counters, a runtime capability and self-test probe, and
twelve headless tests in `test_gpu_raster.py` including a full-engine equality
run and three that cover the dispatch pipeline's guards, plus three in
`test_expert_analysis_settings.py` for the manual toggle. Each was verified to
fail against a deliberate break before being kept.

Where the path finished, same session, medians of five:

| Configuration | Cold | vs CPU | Re-analysis | vs CPU | Worst step |
| --- | ---: | ---: | ---: | ---: | ---: |
| CPU | 2.270 s | — | 1.718 s | — | 208 ms |
| GPU, no hold | 2.053 s | -9.6% | 1.925 s | +12.1% | 194 ms |
| GPU, shipped | 1.653 s | -27.2% | 1.745 s | +1.6% | 171 ms |
| GPU, 65,536 per step | 1.530 s | -32.6% | 1.707 s | -0.7% | 488 ms |

The gate is 20 percent and 150,544 face comparisons produced zero differences.

Packaging is done and the automated export gate runs headlessly
(`ALPHA_MATERIAL_SEPARATOR_FBX_EXPORT_TESTS_OK`). The Unity and
human-interaction gates in `docs/testing.md` were confirmed on 2026-08-01 and
have not been re-run since any GPU work landed.

Portability is settled for the two backends anyone here can reach. `_has_fp64()`
decides per machine rather than by backend name; Windows/OpenGL had fp64 and a
Mac returned `NO_FP64`, both confirmed by hand. On the merged branch that meant
the Mac fell back to the CPU, which is exactly what the fp32 branch above
removes: `NO_FP64` now costs a machine the high-precision checkbox and nothing
else. What neither branch changes is the price — the CPU rasterizer is
permanent, the exact paths stay bound by the same bit-exactness tests, and any
reader can force the CPU with **Disable GPU acceleration**.

Push and pull-request creation require separate authorization and have not been
requested.
