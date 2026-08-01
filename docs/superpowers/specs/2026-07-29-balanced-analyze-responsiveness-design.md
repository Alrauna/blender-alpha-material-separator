# Balanced Analyze Responsiveness Design

**Status:** Approved
**Date:** 2026-07-29

## Goal

Reduce interactive Analyze time and remove the loading-percentage stutter
introduced by whole-image bulk callbacks, while preserving exact
classification, authoritative validation, cancellation safety, and the current
single-process Blender architecture.

The balanced target keeps rare single-polygon pauses as a documented limit. It
does not make rasterization resumable inside one polygon.

## Measured cause

Two ignored runs against the lawful private stress example measured:

- 3.836 seconds of synchronous initialization, including 3.448 seconds in the
  structural signature.
- 12 native bulk-image callbacks with a 1.560-second median and 1.630-second
  maximum; eight exceeded one second.
- 3,870 polygon callbacks totaling 41.780 seconds. Their median was 3.6 ms,
  maximum 279.3 ms, and 105 exceeded 50 ms.
- 2.230 seconds of publication validation.
- 55.032 seconds of callback work.
- An estimated modal phase of 103.262 seconds with the current 20 ms timer,
  versus 55.434 seconds with a 1 ms timer.

A generated 2K phase breakdown showed that native pixel transfer is not the
bulk-image stall:

- Buffer allocation: 5.9 ms.
- `Image.pixels.foreach_get`: 2.2 ms.
- Alpha extraction: 11.2 ms.
- Digest update: 17.9 ms.
- Python threshold loop: 563.2 ms.

The earlier throughput change correctly retained native transfer but combined
all post-processing into one indivisible modal callback. Separately, the fixed
20 ms event timer adds avoidable waiting after short 64-polygon callbacks.

## Approved behavior

### Native image transfer with resumable post-processing

Keep the current eligibility rule and conservative 384 MiB working-memory cap
for native bulk reads.

For an eligible image:

1. Allocate the full float buffer and call `Image.pixels.foreach_get` once.
2. Retain that buffer only inside the active `ImageSnapshotBuilder`.
3. Process at most 65,536 participating texels per `step()` call:
   - extract the requested channel;
   - validate values are finite;
   - update the existing BLAKE2b digest in source order;
   - write threshold results into the existing affected grid;
   - advance processed rows and texels.
4. Release the full buffer and temporary chunk immediately after completion,
   cancellation, or error.

The digest, affected grid, component handling, channel behavior, and error
semantics must remain byte-for-byte equivalent to the current bulk and
row-slice paths.

The non-bulk fallback continues reading complete row chunks directly from
Blender. No second image reader or generalized task framework is introduced.

Synchronous and headless callers use the same builder and may call `step()` in
a tight loop. Only the modal event loop yields between steps.

### Responsive polygon scheduling

Change the interactive Blender event timer from 20 ms to 1 ms.

Interactive face processing uses both:

- a 12 ms target deadline checked between completed polygons; and
- a maximum of 4,096 polygons per callback.

The callback stops at the first safe boundary after reaching either limit.
Synchronous analysis retains count-bounded tight-loop execution and does not
sleep or yield.

No check is inserted inside `rasterize_polygon()` or
`classify_coverage()`. One unusually expensive polygon can therefore exceed the
12 ms target. The measured current maximum of roughly 280 ms is an accepted
balanced-target ceiling, not a promised constant.

### Truthful progress stages

The panel and Blender status bar use these stages:

1. **Preparing Inputs**
2. **Reading Textures**
3. **Analyzing Faces**
4. **Validating Inputs**
5. **Analysis Complete**

Image progress advances after each processed row chunk instead of after an
entire eligible image. Face progress advances after each time-bounded callback.

Preparation and publication validation do not claim a numeric percentage
because their current authoritative signature operations are not resumable.
Validation must not display a misleading completed percentage. The final
100 percent state appears only after publication validation succeeds.

Progress remains monotonic within each measurable stage. Cancel guidance stays
visible throughout every cancellable stage.

### Cancellation and cleanup

Cancellation is observed at every modal callback boundary.

If cancellation, image-read failure, mutation detection, or another exception
occurs:

- release retained bulk buffers and temporary chunk data;
- discard the incomplete engine and report;
- end Blender progress and remove the timer;
- retain any previous complete report and review token;
- publish no partial counts, classifications, or cache entries.

Only finished image snapshots and finished polygon coverage may enter existing
caches.

### Publication safety

Keep the current publication-time structural signature and conservative image
revalidation. During this synchronous guard the stage reads
**Validating Inputs** without showing 100 percent.

Do not replace authoritative hashing with timestamps, dirty flags, dependency
graph hints, or optimistic mutation generations.

## Compatibility

- Extension version remains `0.1.0`.
- Public API remains `1.2`.
- Operator IDs, arguments, payload fields, classifications, policies, cache
  keys, and defaults remain compatible.
- Exact positive-area coverage and deterministic scanline/run budgets remain
  unchanged.
- Analyze still switches from Mesh Edit Mode to Object Mode before reading the
  base mesh.
- Headless and scripted `execute()` behavior remains synchronous.
- No runtime dependency, thread, process, preference, persistent setting, or
  network access is added.

## Expected performance

The scheduling-only ceiling on the private stress example is approximately
1.78x over the current modal path:

- Current 20 ms estimate, including initialization and publication:
  approximately 109 seconds.
- Same measured work at a 1 ms schedule: approximately 62 seconds.

The image change targets responsiveness while retaining the native reader's
throughput advantage. It is not expected to materially reduce total image
computation.

Release acceptance requires:

- no bulk image post-processing callback above 250 ms on the same generated 2K
  and 4K characterization machine;
- no image callback above one second in the private stress example;
- at least a 25 percent reduction in measured interactive Analyze time on the
  private stress example;
- no unexplained regression above 25 percent in cold analysis, callback work,
  digest time, peak working set, or existing release tiers.

Timing limits are characterization gates, not ordinary deterministic unit-test
assertions.

## Test-first verification

### Generated image tests

Before production edits, add regressions proving that:

- an eligible bulk image no longer completes all post-processing in one
  `step()`;
- `foreach_get` is called exactly once;
- each post-transfer step processes no more than 65,536 participating texels;
- bulk, fallback, and synchronous paths produce identical digests and affected
  grids for all supported component counts and channels;
- non-finite values fail identically regardless of chunk boundary;
- completion, cancellation, fallback, and error release retained buffers.

### Generated engine and progress tests

Add deterministic tests using an injected or patched clock:

- the modal face loop yields after the 12 ms deadline;
- the 4,096-polygon cap remains a hard upper bound;
- synchronous analysis is not time-sliced;
- progress stages occur in the approved order;
- texture and face progress are monotonic;
- validation never presents a completed percentage;
- cancellation during image and polygon stages preserves the previous report
  and publishes no partial result.

### Integration and performance gates

Run:

- the complete ordinary-Python suite;
- the complete headless Blender suite;
- generated bulk/chunk parity and modal lifecycle tests;
- source and built-ZIP validation;
- the private Analyze → Preview → Apply and preservation smoke;
- one discarded warm-up plus five measured generated performance runs;
- the ignored private cadence profiler;
- installed-ZIP interactive progress and Escape-cancellation acceptance.

The private files and raw profiler output remain ignored and uncommitted.

## Deferred work

- Resumable preparation and publication signatures.
- Resumable scanline/run processing inside one polygon.
- Strict callback deadlines.
- Multiprocessing or threading.
- Native compiled thresholding.
- Changes to rasterization, classification, material resolution, or assignment.
- New public progress payload fields or user-configurable performance settings.
