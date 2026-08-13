<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# GPU rasterization design

Status: approved. Measurements behind every number here are in
`docs/performance.md` under the Stage 6E sections.

## Objective

Replace scanline rasterization and alpha counting with one compute shader when
the platform can run it bit-exactly, and leave every observable result
unchanged. The CPU implementation stays authoritative: it defines correctness,
it runs wherever the GPU path cannot, and it is what the GPU path is tested
against.

## Non-goals

- No change to `docs/algorithm.md`. The contract is the same; only who computes
  it changes.
- No change to classification, grouping, material resolution, assignment,
  image extraction, or any public API.
- No GPU path for preview or apply.
- No new dependency, no runtime download, no shader cache on disk.

## Why this is worth doing

| | Seconds on the realistic tier |
| --- | ---: |
| Rasterization | 0.513 |
| `count_batch` gather | 0.160 |
| Coverage cache key hashing | 0.103 |
| Coverage cache lookup | 0.024 |
| **CPU work the GPU path replaces** | **0.800** |
| **Fused kernel, all 150,544 faces** | **0.104** |

0.696 s of a 2.258 s tier, or 30.8%, against a 20% keep gate. The kernel is
already proven exact on all 150,544 polygons of that tier.

## Architecture

### Placement

A new `addon/adapters/gpu_raster.py`. Not `addon/core/`: core forbids Blender
imports and the unit suite runs on plain Python without Blender, while `gpu` is
a Blender module. The GLSL lives in that file as a module constant, not as a
data file, so packaging is unaffected.

### Capability probe

`gpu_raster.available()`, evaluated once per process and cached, returning False
on any failure without letting an exception escape:

1. `gpu` imports and `_has_fp64()` proves the backend computes in double
   precision.
2. The shader compiles.
3. A fixed self-test batch reproduces its expected results exactly.

Step 1 is measured, not looked up. It compiles a one-thread shader that takes
the halves of `1.0 + 2**-52` through push constants — so nothing can be folded on
the host — subtracts one, and requires the halves of `2**-52` back. A backend
without fp64 either rejects the source, which is caught, or computes it as
`float` and returns zero, which is also caught. Both answer `NO_FP64`. Naming a
backend instead would be wrong twice over: the list goes stale whenever a driver
gains or loses the capability, and silent demotion would slip past it into the
self-test and be reported as a defect rather than as a missing capability.

Step 3 is the one that matters, because compilation proves very little. The
self-test runs the real kernel on a small fixed fixture and compares its counts
against `rasterize_batch` plus `count_batch` computed at probe time, so the
expectation cannot drift away from the CPU implementation it must match.

It is worth being precise about what this does and does not catch. It does not
catch multiply-add contraction: the kernel with every `precise` stripped returns
identical counts on all 150,544 polygons of the realistic tier, and a search
over 4,000,000 random triangles found none whose runs change under fusion. What
it catches is any divergence that reaches a count — a driver that rounds
division differently, that implements `floor` or `bitCount` unexpectedly, that
mishandles the 24-bit packing or the address-mode arithmetic, or that miscompiles
the kernel outright. Those are the failures that would corrupt a report.

`precise` stays in the source regardless. It is not load-bearing against any
observed defect; it is the cheap way to hold the bit-equality contract, and the
probe is not a substitute for it.

A machine that fails the probe is not degraded. It runs exactly what it runs
today.

### Interface

```python
def counted_batch(triangles, counts, grid, mode, *, settings) -> GpuCounts | None
```

`GpuCounts` carries, per polygon, the affected count and a `RasterStats`, plus a
sparse `reasons` mapping for any polygon the CPU path rejected. `None` means the
caller must use the CPU path for the whole batch, which happens when the probe
failed, when the mode is unknown, or when a raster margin is set.

Non-finite UV is also routed to the CPU. `_analyze_polygon` raises before such a
face is deferred, so it should never arrive, but a NaN reads as a positive area
and would poison the scanline sums rather than announce itself.

Polygons the kernel cannot take are partitioned out on the host rather than
failing the batch, because one awkward polygon in a chunk must not silently
disable the GPU for a whole mesh:

- more triangles than the span cap of 32;
- any polygon over `max_scanlines` or `max_run_emissions`.

Those indices go to `rasterize_batch` plus `count_batch` and the results merge
by index. Budget trips keep their exact scalar reason and ordering semantics for
free, which is worth far more than reproducing `_first_trip` in GLSL.

Both budgets are decided on the host before the dispatch, from the sorted
heights alone, rather than reported back by the kernel. `_within_segment` makes
the CPU's budget a running total within a polygon, so a polygon whose total
stays inside the budget never trips and one whose total exceeds it always does:
the per-polygon total is an exact test, not an approximation of one. Emitted
runs are at most one per triangle per row, so the scanline total bounds the
emission total and a single comparison against the smaller of the two budgets
covers both. That is conservative in the safe direction — it can route a polygon
to the CPU that would not have tripped, and that polygon still gets the right
answer — and it saves both an output channel and a second pass.

Non-finite UV never reaches here: `_analyze_polygon` already raises before the
face is deferred.

### The kernel

One thread per polygon, no atomics, as prototyped. Per row it recomputes each
triangle's cross-sections in `precise` fp64, unions the spans, and adds the
covered length and the popcount of the alpha mask over that span.

`precise` goes on every declaration feeding a comparison. No observed defect
depends on it — see the probe section — but the contract is bit-equality with
the CPU, and the qualifier is the cheapest way to hold it.

All four address modes ship together. CLIP and EXTEND use the clamped form with
their respective outside handling; REPEAT and MIRROR use the periodic form, with
MIRROR folding the index at `2 * width`. Each mirrors the corresponding branch
of `AlphaGrid._count_run` and `count_batch`.

MIRROR costs the kernel no second counting path. Its mask rows are uploaded
already folded, each row followed by its own reverse, which is what
`AlphaGrid._ensure_mirrors` builds on the CPU; the period then becomes twice the
width and the REPEAT form covers it unchanged. The folded mask is a separate
cache entry, so a grid only pays for it when something addresses it that way.

### The alpha mask on the GPU

24 texels per float32, rows padded to a whole number of words so a run never
reads across a row boundary. `R32F` is the only exact upload channel and is
exact below 2^24, which is exactly what a 24-bit word needs.

Chosen over uploading the 2D prefix sums, which would need the same number of
reads and 154 MB of upload against 3.6 MB. Packing costs 0.030 s per image and
is cached on the snapshot alongside the existing mask, so repeated analyses and
every chunk after the first pay nothing.

### The coverage cache

The GPU path bypasses it entirely, including the digest.

The cache is keyed on UV geometry and image dimensions, not image content, so it
stores spans and the alpha count is computed per image afterwards. A kernel that
fuses rasterizing and counting cannot use a geometry-only entry. Bypassing it is
also faster than honouring it: 49.1% of faces hit the cache on the tier, but the
kernel processes all 150,544 faces in 0.104 s where the CPU rasterizes only the
76,647 misses in 0.513 s, and skipping the digest saves a further 0.127 s.

Consequence, and the one report-visible change in this design: on the GPU path
`coverage_cache_hits` and `coverage_cache_misses` are not incremented, so they
are absent from `report.metrics` exactly as the raster counters are absent when
nothing rasterizes. A `coverage_cache_bypassed` count takes their place. These
keys are not part of `docs/integration-api.md` and no test asserts them today,
but this is the one place the design is observable from outside, so it is called
out rather than buried.

### Metrics

| Counter | Source |
| --- | --- |
| `triangles` | host, from `counts` |
| `degenerate_triangles` | host, from the zero-area mask |
| `scanlines` | host, from `ceil(high_y) - floor(low_y)` |
| `emitted_runs` | kernel |
| `union_runs` | kernel |
| `covered_texels` | kernel |

The first three need no rasterization, only the sorted heights the host already
computes to feed the kernel.

`GpuCounts` keeps all six as int64 arrays rather than one `RasterStats` per
polygon. Building 150,544 frozen dataclasses is the cost the batch path exists to
avoid; the caller constructs them only for the faces it actually reports.

A polygon the CPU path rejected has every counter zero, because
`rasterize_batch` gives it a reason string and no `RasterStats` at all. No
counter may carry a partial figure for a face that produced no coverage.

## Test strategy

The CPU path is the oracle throughout. Every GPU test compares against it on the
same input and demands equality, never a tolerance.

Tests live in `tests/blender/`, not `tests/unit/`, because they need a GPU
context. Each skips with a recorded reason when `available()` is False, so CI
without a GPU stays green and honest rather than silently passing. A skip is
reported in the run output; a machine that can run the tests and skips them is a
failure of the harness, not a pass.

RED/GREEN order, each step a commit:

1. **Probe.** `available()` returns a bool and never raises, on a machine with
   and without the capability. RED by asserting the self-test rejects a
   deliberately non-`precise` shader variant.
2. **Address modes.** Per mode, a fixture whose runs cross the image edge in
   both directions, and for MIRROR across the fold. Equality against
   `AlphaGrid.count_batch` per polygon.
3. **Exactness at scale.** The realistic tier, every polygon, covered and
   affected equal to `rasterize_batch` plus `count_batch`. This is the test that
   already passes in the prototype.
4. **Partitioning.** A mesh mixing an n-gon past the span cap with ordinary
   quads returns identical results to an all-CPU run, proving the merge by index
   and that one awkward polygon does not disable the batch.
5. **Budgets.** A polygon engineered past `max_scanlines` and another past
   `max_run_emissions` produce the same reason strings and the same per-face
   reason scopes as the CPU path.
6. **Metrics.** All six raster counters equal the CPU path's on the tier, and
   the cache-metric substitution behaves as designed.
7. **Engine equality.** A full `AnalysisEngine` run with the GPU path forced on
   and forced off produces identical `report.object_results`, face by face.

Test 7 is the one that would catch an integration mistake the unit-level tests
cannot, so it is the gate for the integration commit rather than an extra.

## Validation

- Unit suite, complete headless Blender suite, and `extension validate addon`
  before branch completion.
- The same-session protocol in `docs/performance.md` for the whole-workflow
  measurement, GPU forced off then forced on, in one process.
- The 20% keep gate is measured, not projected, on that pair.
- No packaging change is expected; a clean build and version-independent ZIP
  validation run anyway because a new module is added.

## Preservation checks

- Analyze remains read-only: the kernel reads mesh-derived arrays and image
  masks and writes only its own textures.
- No mesh, material, image, selection, or topology data is touched.
- The report is byte-identical between paths apart from the declared cache
  metrics and timing.
- A machine without the capability behaves exactly as it does today, including
  its metrics.

## Risks

- **Some machines cannot run this.** The kernel needs fp64, which Metal does not
  have. That is measured rather than assumed: `_has_fp64()` compiles and runs one
  `double` before anything else and reports `NO_FP64` when the backend either
  refuses the source or computes it in single precision. No backend is named
  anywhere, so a driver that gains or loses the capability needs no code change.
  The CPU rasterizer is a permanent fallback, and two implementations of the most
  correctness-critical code in the addon are maintained under one set of
  bit-exactness tests. This is the real price and it is not measured in seconds.
- **One machine, one driver.** Every *measurement* and the exactness result come
  from a single OpenGL NVIDIA machine. The probe's two outcomes have since been
  confirmed by hand on Windows/OpenGL and on a Mac, where the panel showed the
  instruction-set message — reachable only from `NO_FP64`, so Metal took the
  fp64 branch rather than failing some other way. Neither hand run was timed.
  Another driver could still round, fold or miscompile differently; the runtime
  self-test is what makes that disable the path rather than corrupt a report,
  and it is why the probe verifies results rather than compilation.
- **Drivers can regress.** The self-test runs every process start, so a driver
  update that breaks exactness disables the GPU path instead of corrupting
  output.

## Commit boundaries

1. `gpu_raster.py` with the probe and its self-test, plus test 1.
2. The kernel and host preparation for REPEAT, plus tests 2 and 3.
3. The remaining three address modes, extending test 2.
4. Partitioning and budget fallback, plus tests 4 and 5.
5. Metrics, plus test 6.
6. Engine integration behind the probe, plus test 7.
7. The same-session measurement recorded in `docs/performance.md`.

Each commit leaves the addon working with the CPU path unchanged; the GPU path
is not reachable from the engine until commit 6.

## Implementation notes

Recorded as the design meets the machine. Nothing here changes the agreed
behaviour, scope, risk, or architecture.

### Commits 1 and 2 merged

The probe's self-test verifies results, so it needs the kernel and the host
preparation to exist. Building a throwaway shader for the probe to reject would
have been ceremony. The two boundaries became one commit; the rest stand.

### Negative operands to `%` are undefined in GLSL, and the driver proves it

The first test run disagreed with the CPU on exactly the polygons with a
negative row range or a negative run start: covered counts all matched, so the
spans were right and only the addressing was wrong. Replicating the shader's
`periodic` and `bits_in` in Python with C truncation semantics reproduced the
CPU exactly, which placed the defect below the algorithm.

GLSL leaves `%` undefined when either operand is negative. The kernel now folds
the value positive before the operator ever sees it, rather than truncating and
correcting afterwards.

Two things about how this was missed are worth keeping:

- The 150,544-polygon exactness result did not catch it. Every image in the
  benchmark tier has power-of-two dimensions, and for a power-of-two period the
  broken form and the correct one agree. A large exactness run is not
  automatically a broad one.
- The self-test did not catch it either, for the same reason: the fixture was
  64×16. It is now 53×17, and neither dimension will become a power of two.

### The self-test fixture needs triangles that are not axis-aligned

Removing the mid-vertex straddle correction was caught by the at-scale test on
526 of 3,000 polygons, but the probe passed it. A rectangle split into two right
triangles puts the middle vertex on a shared corner, where the straddle
correction never changes a run, so a fixture of rectangles alone cannot see that
defect. The fixture now carries two triangles whose middle vertex is the row's
extremum strictly inside a band.

Both defects are now rejected by the probe itself, which was verified by
reintroducing each one and observing `available()` turn False.

### A failed self-test is a test failure, not a skip

`gpu_raster.reason()` reports why the probe decided as it did. A machine with no
usable GPU skips; a machine whose GPU returns wrong answers reports `MISMATCH`
and fails the suite. Without that split, breaking the kernel would have turned
the GPU tests into a silent skip, which is the harness failure the test strategy
above warns about.

### A raster margin always falls back

`settings.margin_texels` is a permanent CPU case. The kernel counts spans as it
unions them and never materializes them, so it has nothing to dilate;
reproducing the margin pass would mean giving up the fusion that makes it fast.
No default configuration sets a margin.

### `gpu.init()` in background mode

A background Blender has no window to borrow a GPU context from, so the probe
calls `gpu.init()` when `bpy.app.background` is set. It costs about 0.36 s, once
per process, and only where a context does not already exist.

### The at-scale test is scaled down

Test 3 uses synthetic polygons rather than the benchmark tier, so the headless
suite stays quick: three image sizes including a non-square, non-power-of-two
one, 8,000 polygons, UVs six times the unit square and offset negative so most
runs wrap, mixed triangle counts per polygon, and degenerate triangles. The
whole module runs in about one second. The benchmark tier remains the subject of
the same-session measurement in commit 7.

### The engine equality test builds its own scene

Test 7 uses 200 quads over a 37×23 image with UVs spread five times the unit
square and offset negative, not the benchmark tier. The tier is private and the
headless suite is redistributable, and a scene this size already produces the
whole matrix the comparison needs: MIXED, OPAQUE and wrapping in both
directions. It compares `ClassificationResult` objects face by face rather than
totals, because two paths can reach the same totals from different per-face
answers.

### One CPU test had to opt out of the probe

`_uv_traversal_values_test` hooks `analysis_module.rasterize_batch` to capture
what the engine hands the rasterizer. The GPU path does not call it, so on a
machine with a GPU the hook saw nothing. The test now sets `engine._gpu = False`:
the traversal it checks is shared by both paths, but only one of them routes
through the function it watches. Any future test that hooks a CPU internal has
the same obligation.

### A mid-run decline turns the path off for the rest of the run

`counted_batch` returning `None` is unreachable from the engine as written — the
margin case is decided once at construction, the probe is cached, and the survey
already routes over-cap polygons to the CPU. It is still handled, because the
alternative to handling it is a wrong report. The chunk's faces get their
coverage keys computed, are counted as cache misses since they were never looked
up, and the CPU path finishes them; `self._gpu` stays False afterwards so one
analysis runs on one implementation.

## Cross-step dispatch pipelining

**Status: implemented. Necessary but not sufficient.** The mechanism works and
the guards below all hold, but on its own the whole-workflow result at the modal
cadence is -11.9%, not the -27% this section estimated. `docs/performance.md`,
Stage 6K, records why. The submit threshold below is what carries it over the
gate, and it needs the pipeline underneath it.

### The mechanism

Reading a result texture is the synchronization point: it waits for the dispatch
it belongs to. That wait is 1 to 2 ms and the engine pays it once per dispatch,
which the measured breakdown separates cleanly from the 0.053 s of real compute.

Nothing is done between submitting and reading. The fix is to do the next
chunk's work there. Submit a flush's dispatches, return; on the following flush,
submit that flush's work first and only then read the previous one. The GPU gets
a whole step — roughly 7 ms of UV traversal for 4,096 polygons, plus the next
submit — to finish in.

Measured, on the tier's raster region alone so machine noise does not swamp it:

| Configuration | Raster region |
| --- | ---: |
| CPU | 0.616 s |
| GPU, serial | 0.500 s |
| GPU, submit the whole flush then read it | 0.407 s |
| GPU, 65,536 per dispatch (ceiling) | 0.184 s |

The third row is intra-flush only and needs no new state; it is worth about
0.09 s. The ceiling's entire advantage over the others is that it pays the stall
fifteen times instead of 185, so a pipeline deep enough to hide the stall should
approach it. Estimated whole-tier result about -27%, against a -27.5% ceiling.

### What changes

`_dispatch` splits at the readback into `_submit`, returning a handle that owns
the output textures and the input textures it must outlive, and `_collect`,
reading it. `counted_batch` splits the same way: `submit_batch` does the survey,
the partition and the dispatch; `collect_batch` reads back, then runs the CPU
partition for over-cap and budget-tripped polygons — which also happens while
the GPU is busy, for free.

`AnalysisEngine` gains one field, `self._inflight`, holding the previous flush's
deferred faces alongside their handles. `_flush_pending` on the GPU path becomes:
submit this flush, then collect and record the previous one, then rotate. Faces
are therefore recorded one flush later than they are deferred.

### What that costs, and the guards it needs

- `step()` must drain before it reports completion, or the last flush is lost.
- `finish()` must refuse to build a report with work in flight, rather than
  silently omitting those faces.
- `cancel()` must drop the in-flight handles so their textures are released.
- The mid-run decline path must collect what is already in flight before it
  turns the GPU off, or those faces are analyzed twice or not at all.
- Peak memory rises by one flush of deferred faces and one set of textures.
  At 4,096 polygons that is small, but it is a rise.
- `self.completed` advances when a polygon is deferred, not when it is recorded,
  so progress reporting is unaffected. This is existing behaviour.

### Why this is a real risk and not bookkeeping

Every one of those guards is a way to lose faces from a report silently. That is
the failure mode this repository cares most about, and it is not one the
arithmetic tests can see. Test 7, the full-engine equality run, is the test that
catches it: it compares face by face with the path forced on and forced off, so
a dropped, duplicated or misordered chunk fails it. Three more are needed — a
run stepped in small budgets so several flushes are in flight in sequence, a
cancel with work in flight, and a `finish()` attempted with work in flight.

### The measurement this rested on was not trustworthy

The whole-workflow figures moved between -10.4% and -19.0% for the same serial
code across four runs in one session, while the CPU baseline drifted from
2.470 s to 2.976 s. `VirtualDesktop.Streamer` was resident and using the GPU
throughout, which contaminates dispatch latency specifically. The raster-region
figures above are stable, but the estimate built on them was wrong in a way the
noise did not cause: every one of those runs stepped 4,096 polygons with no time
budget, a cadence the modal operator never reaches.

### What the implementation added beyond the design

`_RASTER_BATCH_POLYGONS` no longer chunks the GPU path. It is a CPU cache-window
constant, and on the GPU it only multiplied the per-dispatch fixed cost. The
kernel now takes one dispatch per image and address mode group per flush.

Three tests were added as this section required, and each was verified to fail
against a deliberate break: `assert_the_pipeline_survives_small_steps` counts
how many steps ended with a chunk still on the GPU and fails if the engine
drains every flush, `assert_work_in_flight_is_never_lost` covers the `finish`
refusal and the `cancel` drop, and `_report` now asserts nothing is in flight
once a step reports completion.

## The submit threshold

`_GPU_SUBMIT_POLYGONS = 16_384`. The GPU path returns from `_flush_pending`
without submitting until it holds that many polygons; `step` passes `final=True`
on the flush that completes the run, which submits whatever is left.

### Why a threshold and not a bigger step

Every dispatch allocates and uploads its own input and result textures, and that
cost does not shrink with the batch. At the modal cadence a flush is roughly
1,300 polygons and the fixed cost dominates; at 512 polygons per step the GPU
path is slower than the CPU outright.

The obvious fix — step more polygons at a time — trades the responsiveness
contract for the gate, because a 65,536-polygon step is one 488 ms callback.
The threshold separates the two: the contract bounds one `step`, the threshold
bounds one dispatch, and neither has to move for the other. Measured worst step
with the hold is 171 ms, below the CPU path's own 208 ms.

### What it must not break

- The final flush must force a submit. Any mesh under 16,384 polygons never
  reaches the threshold, so without `final=True` its entire report is empty.
  `_report` asserts `_pending` is empty once a step reports completion, and
  `assert_held_polygons_are_never_dropped` runs a 200-polygon scene at the
  shipped threshold and checks nothing is submitted before the end.
- The CPU path must not hold. It has no dispatch to amortize and holding would
  only delay its work.
- Peak memory rises by the held chunk and the one in flight, about 11 MB at
  16,384 deferred faces.

The threshold is a measured constant for this machine and tier, like
`_RASTER_BATCH_POLYGONS`, and the tests that depend on pipeline depth shrink it
through `_submitting_every` rather than building a 16,384-polygon fixture.

## The manual fallback

**Disable GPU acceleration**, at the bottom of Expert Analysis Settings, is a
`BoolProperty` on the session settings group. Off by default; checked and locked
where the probe failed.

The lock lives in the property's `get=`, not in the panel row, because the engine
and any script read the property rather than the row. Its `set=` only stores: a
property with a `get=` and no `set=` is read-only, and the checkbox would never
toggle. A machine whose probe failed therefore reads `True` from every caller.

Three things it deliberately is not:

- Not in `ANALYSIS_SETTING_NAMES`, so it is not an `analyze()` keyword and
  **Reset to Default Values** does not move the reader back onto the GPU.
- Not in `AnalysisConfig.payload()`, so it is not in the input signature.
  Both paths reproduce each other exactly, so switching device must not make a
  completed report stale.
- Not carried on the analyze operator. Which device runs is not an analysis
  parameter, so `_config` reads it from the settings group and the published
  operator surface is unchanged.

The two failure sentences are drawn as label copy under the disabled row rather
than as the tooltip, because a Blender tooltip is fixed at registration and this
text is decided per machine. `NO_FP64` gets the instruction-set sentence;
`MISMATCH`, `UNAVAILABLE`, and anything else get the unknown-reason sentence,
which is honest — none of them is something the reader can act on.
