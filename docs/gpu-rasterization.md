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

1. `gpu` imports and `gpu.platform.backend_type_get()` is not `METAL`.
2. The shader compiles.
3. A fixed self-test batch reproduces its expected results exactly.

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

- **macOS cannot run this.** Metal has no fp64. The CPU rasterizer is a
  permanent fallback, and two implementations of the most correctness-critical
  code in the addon are maintained under one set of bit-exactness tests. This is
  the real price and it is not measured in seconds.
- **One machine, one driver.** Every measurement and the exactness result come
  from a single OpenGL NVIDIA machine. Another driver could round, fold or
  miscompile differently; the runtime self-test is what makes that disable the
  path rather than corrupt a report, and it is why the probe verifies results
  rather than compilation.
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
the same-session measurement in commit 7 and of the engine equality test in
commit 6.
