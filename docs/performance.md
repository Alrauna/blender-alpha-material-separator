# Performance characterization

No arbitrary speed promise is made. This page records the first local baseline
and the repeatable method used to detect regressions.

## Tiers

- Small: about 5,000 polygons and one 1K image.
- Typical avatar: about 50,000 polygons, two 2K images, one 4K image, and ten
  materials.
- High complexity: about 150,000 polygons, two 4K images, one 8K image, and
  sixteen materials.
- Realistic: the same polygon count, but shaped like an actual asset rather than
  an even grid — unevenly sized UV islands, multi-tile addressing throughout,
  half the polygons reusing a shared island so the coverage cache hits, five
  images at mixed square and non-square resolutions, collapsed UV quads, and
  structured alpha. Use this tier, not High complexity, to rank any accelerator.
- Large UV footprint: negative and multi-tile addressing.
- Pathological: deterministic scanline/run budget termination.

## Measurements

Record Blender build, hardware, polygons, loop triangles, image texels,
triangle-row intersections, emitted/merged runs, median time, Python allocation,
and process RSS where available. Use one discarded warm-up and five measured
runs.

Measure full alpha digest, proven digest reuse, threshold-prefix rebuild,
coverage reuse with changed images, and total cold analysis separately at 1K,
2K, 4K, and 8K.

Also measure preview validation, Object/Edit Mode exit rechecks, final Apply
preflight, and genuine image-change validation separately. Instrument each run
with component-fingerprint calls, participating image-digest rows, rasterized
polygons, and coverage-cache hits/misses. A selection/mode-only recheck must
digest zero image rows and rasterize zero polygons.

Full pixel digests remain authoritative when Blender invalidation is uncertain.
Cross-operation reuse is allowed only for mutation paths shown by Blender 5.2
tests to emit reliable invalidation. `Image.is_dirty` or file timestamps alone
are insufficient.

After the first baseline is approved, an unexplained same-machine time or peak
memory regression over 25% blocks release.

## First measured baseline

Measured 2026-07-22 with Blender 5.2.0 LTS, Python 3.13.13, Windows 11, and an
AMD64 Family 26 Model 68 processor. Each cold result is the median of five runs
after one discarded warm-up. Raw machine output remains ignored under
`.test-output/benchmarks/baseline.json`.

| Tier | Polygons / triangles | Images | Cold | Coverage reuse | Reuse after pixel edit |
| --- | ---: | --- | ---: | ---: | ---: |
| Small | 4,900 / 9,800 | 1K | 0.79 s | 0.32 s | 0.32 s |
| Typical | 50,176 / 100,352 | 2K + 2K + 4K | 12.33 s | 9.38 s | 9.17 s |
| High | 150,544 / 301,088 | 4K + 4K + 8K | 77.59 s | 86.07 s | 91.36 s |
| Large/tiled UV | 4,900 / 9,800 | 1K | 2.52 s | 0.54 s | 0.53 s |

The high tier covered 36,782,080 virtual texels and emitted 4,469,760 runs;
the tiled tier covered 17,338,896 virtual texels. The process peaked at about
2.94 GB (2.73 GiB) working set during the high tier. The end-of-tier working
sets were approximately 242 MiB small, 682 MiB typical, 1.71 GiB high, and
435 MiB tiled. These figures include Blender and fixture image storage, not
only extension-owned Python objects.

| Image | Participating texels | Full digest median | Prefix build | Prefix reuse |
| --- | ---: | ---: | ---: | ---: |
| 1K | 1,048,576 | 0.17 s | 0.04 s | <0.001 s |
| 2K | 4,194,304 | 0.84 s | 0.16 s | <0.001 s |
| 4K | 16,777,216 | 5.36 s | 0.61 s | about 0.002 s |
| 8K | 67,108,864 | 50.10 s | 2.52 s | about 0.004 s |

The 1,000,001-scanline pathological case terminated deterministically against
the 1,000,000-scanline budget in under 0.1 ms.

## Interpretation and release policy

- Blender-native bulk pixel transfer is used when its complete working buffer
  is at most 1.5 GiB, which admits 8K RGBA float32 sources. An explicit chunk
  size and a failed native read retain the complete-row chunked path. Both
  paths produce the same participating-channel digest and threshold grid.
- Full authoritative hashing remains mandatory when Blender cannot prove that
  pixels are unchanged. Since vectorization it is no longer the dominant 8K
  cost; see "Vectorized image extraction".
- Coverage reuse is valuable at every tier, including high complexity. The
  2026-07-22 observation that high-tier reuse was slower than cold no longer
  reproduces; see "Coverage-cache reuse is no longer a regression".
- Cross-operation digest reuse remains disabled until a Blender 5.2 mutation
  class has reliable invalidation tests. Per-analysis image snapshot reuse and
  threshold-prefix reuse are active.
- The provisional 25% regression rule applies to the matching same-machine
  tier and metric. A fixture, Blender build, or hardware change establishes a
  new reviewed baseline instead of being compared blindly.
- The component-revalidation implementation adds a separate acceptance target:
  on the approved same-machine structural workflow, leaving preview must recheck
  in a median below one second and below 15 percent of cold analysis.

## Structural revalidation baseline

Measured 2026-07-25 on the same Blender, OS, Python, and processor family as the
first baseline. The generated 4,900-polygon/9,800-triangle mesh used one clean
file-backed 1K image. One warm-up was discarded and five mode-exit structural
rechecks were measured.

| Metric | Result |
| --- | ---: |
| Cold analysis | 0.836 s |
| Structural recheck median | 0.0345 s |
| Recheck / cold ratio | 4.13% |
| Component hashes | 1 |
| Participating image-digest rows | 0 |
| Rasterized polygons | 0 |
| Coverage cache entries retained | 4,900 |

The recheck passes both provisional targets. Raw per-run machine output remains
ignored in `.test-output/benchmarks/revalidation-current.json`.

The same generated fixture was rerun on 2026-08-01 to isolate the real final
Apply preflight. This measures authoritative validation, assignment-plan
rebuilding, public-plan creation, and review-signature comparison before
mutation; it excludes dialog response, assignment, and Undo.

| Apply-preflight metric | Result |
| --- | ---: |
| Apply preflight median | 0.0353 s |
| Apply preflight / cold ratio | 4.89% |
| Component hashes | 1 |
| Participating image-digest rows | 0 |
| Rasterized polygons | 0 |
| Mutation-free | yes |

## Main Base Color fallback regression check

Repeated on 2026-07-26 after separating classification authority from
assignment-only material state. The same Blender build, machine, fixtures, and
one-warm-up/five-measurement method were used.

| Tier | Previous cold | Current cold | Change |
| --- | ---: | ---: | ---: |
| Small | 0.79 s | 0.790 s | approximately 0% |
| Typical | 12.33 s | 12.574 s | +1.98% |
| High | 77.59 s | 79.079 s | +1.92% |
| Large/tiled UV | 2.52 s | 2.010 s | -20.23% |

The high-tier peak working set was about 2.86 GiB, within 5 percent of the
recorded peak. Structural revalidation remained 0.0345 seconds, digested zero
image rows, and rasterized zero polygons. Full 1K/2K/4K/8K digest medians were
all faster than the first baseline. No matching time or memory metric regressed
by the provisional 25 percent limit. Raw output remains ignored in
`.test-output/benchmarks/baseline.json`.

## Analyze throughput optimization

Measured 2026-07-29 after replacing eligible Python pixel slices with bounded
`Image.pixels.foreach_get` transfers and removing duplicate modal preparation,
UV traversal, and shared-material fingerprint work. The exact rasterizer was
left unchanged: an allocation-reduction candidate preserved the clipping-oracle
results but improved the representative polygon phase by only 4.8 percent,
below the 20 percent keep threshold.

| Tier | Previous cold | Current cold | Change |
| --- | ---: | ---: | ---: |
| Small | 0.790 s | 0.723 s | -8.5% |
| Typical | 12.574 s | 8.538 s | -32.1% |
| High | 79.079 s | 82.812 s | +4.7% |
| Large/tiled UV | 2.010 s | 2.028 s | +0.9% |

The high-tier peak working set was about 2.90 GiB, within 2 percent of the
previous recorded peak. Full digest medians were 0.073 seconds at 1K, 0.291
seconds at 2K, 1.242 seconds at 4K, and 47.094 seconds at 8K. The 8K image
correctly used the bounded fallback.

On the lawful 247,718-polygon private stress example, the same anonymous
aggregate classifications were preserved while a diagnostic cold run fell
from 82.48 seconds to 46.09 seconds. Image preparation fell from 38.76 seconds
to 10.20 seconds and repeated final preparation was eliminated. This is a
single representative diagnostic, not the release median.

A pure-core process prototype reached 2.14x with four workers but projected
only about 1.29x for the original complete workflow. After the retained
single-process improvements, multiprocessing is deferred: Blender datablocks
must remain on the main process, serialized coverage work would increase
memory and cancellation complexity, and no measured whole-workflow case clears
the 20 percent implementation threshold safely.

## Analyze responsiveness

Measured 2026-08-01 after retaining native `foreach_get` transfer while
processing at most 65,536 participating texels per step, changing the modal
timer from 20 ms to 1 ms, and checking a 12 ms target between polygons. One
warm-up was discarded and five runs were measured on the same machine.

| Tier | Previous cold | Current cold | Change |
| --- | ---: | ---: | ---: |
| Small | 0.723 s | 0.691 s | -4.4% |
| Typical | 8.538 s | 8.074 s | -5.4% |
| High | 82.812 s | 71.556 s | -13.6% |
| Large/tiled UV | 2.028 s | 1.917 s | -5.5% |

Peak working set was about 2.92 GiB, less than one percent above the previous
recorded peak. Full digest medians were 0.077 seconds at 1K, 0.308 seconds at
2K, 1.202 seconds at 4K, and 45.163 seconds at 8K. No matching established
metric regressed by the provisional 25 percent limit.

The anonymous private cadence model measured:

| Metric | Before | Current |
| --- | ---: | ---: |
| Estimated interactive Analyze | about 109.3 s | 51.544 s |
| Callback work | 55.032 s | 43.093 s |
| Maximum private image callback | 1.630 s | 0.0368 s |
| Maximum polygon callback | 0.279 s | 0.197 s |
| Generated 2K image callback | 0.385 s | 0.0109 s |
| Generated 4K image callback | not recorded | 0.0316 s |

The estimated interactive duration fell about 52.8 percent. It combines
measured callback work with the configured 1 ms timer interval; it is not a
foreground UI wall-clock measurement. The attempted isolated installed-ZIP
visual run could not be controlled because the Windows automation helper
rejected its own Blender window handle. A manual foreground timing remains
open.

The 12 ms face target is checked only after a complete polygon. It is not a
strict callback maximum: the measured worst indivisible polygon callback was
about 197 ms. Resumable per-polygon rasterization and multiprocessing remain
deferred.

## Vectorized image extraction

Measured 2026-08-12 on the same machine, in one session, before and after
replacing the per-value Python extraction loop with numpy. Blender 5.2.0 LTS
bundles numpy 2.3.4; the extension bundles none of its own. The bulk path now
transfers pixels with `foreach_get` into a contiguous `numpy.float32` buffer,
and the low-memory path converts each bounded `image.pixels[a:b]` slice into
numpy instead of iterating it. The same-session before-run is the comparison
baseline; it is slower than the 2026-08-01 figures on the same tiers, so the
percentages below are within-session and the absolute times are not directly
comparable to earlier sections.

| Tier | Before | After | Change |
| --- | ---: | ---: | ---: |
| Small | 0.735 s | 0.651 s | -11.4% |
| Typical | 10.333 s | 6.670 s | -35.5% |
| High | 80.239 s | 23.101 s | -71.2% |
| Large/tiled UV | 2.154 s | 1.888 s | -12.3% |

| Image | Digest before | Digest after | Change | Read path |
| --- | ---: | ---: | ---: | --- |
| 1K | 0.0796 s | 0.0045 s | -94.3% | bulk |
| 2K | 0.3282 s | 0.0246 s | -92.5% | bulk |
| 4K | 1.3588 s | 0.1034 s | -92.4% | bulk |
| 8K | 49.4403 s | 0.4232 s | -99.1% | bulk |

The 8K image now takes the bulk path instead of the complete-row fallback. Peak
process working set **fell** from 2.916 GiB to 2.875 GiB, so the anticipated
one-gigabyte increase did not occur and no baseline re-approval is needed: the
transient float32 transfer buffer is released as soon as extraction completes,
and it replaces the Python lists, `array("f")` copies, and per-value objects the
old path allocated. The provisional 25 percent regression rule is not breached
on any matching metric. Structural recheck (0.03616 s to 0.03578 s) and Apply
preflight (0.03579 s to 0.03577 s) are unchanged, as expected for paths that
digest zero image rows.

Correctness is gated by `tests/blender/test_image_data.py`, which holds a
scalar pure-Python oracle reproducing the original semantics and requires
byte-identical digests, mask bytes, metadata, and errors from both read paths
across component counts 1-4, `ALPHA`/`RED`/`GREEN`/`BLUE`/`LUMINANCE`,
non-finite inputs, threshold boundaries, and fifteen committed golden digests.
Two of the thresholds it exercises are ones a float32-narrowed comparison would
answer differently, so the float64 comparison is pinned by test rather than by
comment.

### Per-phase instrumentation

Analysis now records per-phase wall time in `AnalysisReport.metrics`. Phases
are timed at the analysis engine except image extraction and row-prefix
construction, which accumulate in module counters that the engine samples as
deltas. `phase_prefix_seconds` is nested inside `phase_classify_seconds`, so
counting cost is the difference. Measured overhead is about 0.65 percent of the
high tier: seven `perf_counter` calls and six counter updates per polygon.

High tier, 23.101 s cold, 150,544 polygons and 301,088 triangles:

| Phase | Seconds | Share |
| --- | ---: | ---: |
| Rasterization | 14.110 | 61.1% |
| Classification total | 4.813 | 20.8% |
| — row-prefix construction | 3.322 | 14.4% |
| — run counting | 1.491 | 6.5% |
| UV traversal | 1.076 | 4.7% |
| Coverage cache key | 0.261 | 1.1% |
| Image digest | 0.301 | 1.3% |
| Image read | 0.188 | 0.8% |
| Image mask | 0.064 | 0.3% |
| Image channel select | 0.043 | 0.2% |
| Coverage cache lookup | 0.055 | 0.2% |
| Coverage cache store | 0.027 | 0.1% |

Complete image extraction is now 0.596 s, about 2.6 percent of cold analysis,
down from roughly 52 s of the 80.239 s before-run. The remaining ~2.2 s outside
the table is input preparation, signature construction, polygon iteration, and
the instrumentation itself.

### Coverage-cache reuse is no longer a regression

The high tier reuse path measured 74.714 s against 80.239 s cold before this
change and 9.241 s against 23.101 s cold after it — 2.5x faster than cold, with
all 150,544 polygons hitting the cache. The reuse run pays 0.261 s of key
construction and 0.055 s of lookup to avoid 14.110 s of rasterization. The
2026-07-22 observation that high-tier reuse was slower than cold does not
reproduce on this machine in either the before-run or the after-run, so the
planned coverage-cache investigation has no defect to debug. Recorded as
resolved by measurement, not by redesign.

### Next measured bottleneck

Rasterization at 61.1 percent, then row-prefix construction at 14.4 percent.
Image extraction is no longer a meaningful target, and neither is the coverage
cache.

## Cross-section scanline rasterization

Measured 2026-08-12 on the same machine, in one session, before and after
replacing per-row Sutherland-Hodgman clipping with two height-sorted horizontal
cross-sections per scanline. Each row now reuses the cross-section the previous
row already computed at their shared boundary, so a triangle spanning *n* rows
evaluates *n+1* cross-sections instead of clipping a fresh polygon *n* times.
No numpy is involved: the win is removing per-row list allocation, closure
calls, and generator min/max, not vectorizing.

| Tier | Before | After | Change |
| --- | ---: | ---: | ---: |
| Small | 0.633 s | 0.352 s | -44.5% |
| Typical | 6.461 s | 4.268 s | -33.9% |
| High | 22.825 s | 14.612 s | -36.0% |
| Large/tiled UV | 2.065 s | 0.736 s | -64.4% |

Rasterization itself fell from 14.011 s to 5.526 s, -60.6 percent, which clears
the 20 percent keep threshold that the 2026-07-29 allocation-reduction candidate
missed. The tiled tier gains most because its triangles span the most rows.
High-tier `covered_texels`, `emitted_runs`, `union_runs`, `scanlines`, and
`degenerate_triangles` are all unchanged, and peak working set moved from
2.890 GiB to 2.891 GiB.

Structural recheck moved from 0.03506 s to 0.03694 s and Apply preflight from
0.03337 s to 0.03441 s, both within noise. Their ratios to cold analysis rose
to 10.23 and 9.53 percent only because cold analysis on that fixture fell from
0.647 s to 0.361 s; both acceptance targets still pass. Digest medians and
prefix builds are unchanged, as expected for a change that touches neither.

### Coverage is now tighter on some exactly-representable triangles

The replaced clipping code was not stable under vertex permutation: on 6,000
randomized boundary-snapped triangles, 15 produced different runs depending
only on which vertex was listed first. Bit-equality with it is therefore not a
definable contract, and the gate is the order-independent positive-area oracle
that `docs/algorithm.md` already specifies.

Across 14,000 randomized triangles in four coordinate families, the new
rasterizer never under-covers the oracle. On the exactly-representable quarter
grid it matches the oracle exactly in all 4,000 cases, where the old code
disagreed 18 times — every one of those emitting a cell whose intersection with
the triangle has zero area, which contradicted `rasterize_polygon`'s documented
"positive area" rule. Coverage is therefore slightly tighter than before on
such triangles. The dropped cells have no positive-area overlap, so the only
possible effect is fewer spurious alpha classifications; nothing moves toward
leaving a transparent face on an opaque material. On the benchmark fixtures the
coverage totals are identical.

`tests/unit/test_rasterization.py` gates this with a 27-case adversarial list
(vertices and edges on texel boundaries, flat-top and flat-bottom triangles,
near-horizontal and near-vertical edges and slivers, sub-texel and degenerate
triangles, edge-only and point-only contact, negative and multi-tile UVs, large
accepted coordinates, and coordinates near 1e7 with sub-ulp spacing) plus 2,800
randomized triangles and quads. Removing either the middle-vertex extremum or
the exact top-vertex substitution fails the gate.

### Next measured bottleneck

High tier, 14.612 s cold:

| Phase | Seconds | Share |
| --- | ---: | ---: |
| Rasterization | 5.526 | 37.8% |
| Classification total | 4.780 | 32.7% |
| — row-prefix construction | 3.321 | 22.7% |
| — run counting | 1.459 | 10.0% |
| UV traversal | 1.066 | 7.3% |
| Image digest | 0.303 | 2.1% |
| Coverage cache key | 0.254 | 1.7% |
| Image read | 0.186 | 1.3% |
| Image mask | 0.065 | 0.4% |
| Coverage cache lookup | 0.055 | 0.4% |
| Image channel select | 0.049 | 0.3% |
| Coverage cache store | 0.027 | 0.2% |

Row-prefix construction is now the largest single addressable phase at
22.7 percent, ahead of run counting at 10.0 percent.

## Vectorized row prefixes

Measured 2026-08-12 on the same machine, in one session, before and after
replacing the per-value Python accumulation loop in `_prefix` with
`numpy.cumsum`. The result is still converted to `array("I")` so callers keep
receiving plain Python ints; numpy scalars would otherwise reach report metrics
and JSON benchmark output. The MIRROR input builds its doubled row by slice
concatenation rather than an unpacked generator.

| Tier | Before | After | Change |
| --- | ---: | ---: | ---: |
| Small | 0.337 s | 0.314 s | -6.9% |
| Typical | 4.010 s | 3.451 s | -14.0% |
| High | 14.049 s | 11.342 s | -19.3% |
| Large/tiled UV | 0.730 s | 0.730 s | 0.0% |

Row-prefix construction fell from 3.317 s to 0.186 s, -94.4 percent, taking
classification as a whole from 4.734 s to 1.619 s. Standalone prefix builds fell
85.5 percent at 1K, 89.4 percent at 2K, 94.1 percent at 4K, and 94.0 percent at
8K, where 2.022 s became 0.122 s. Prefix reuse was already sub-millisecond and
is unchanged. The tiled tier is flat because its 1K image contributes almost no
prefix work.

High-tier `covered_texels`, `emitted_runs`, `union_runs`, and `scanlines` are
unchanged, coverage reuse improved from 9.278 s to 6.311 s, and peak working set
**fell** from 2.895 GiB to 2.874 GiB despite numpy temporaries, because the
`array("I")` prefix replaces a Python loop's intermediate objects. Structural
recheck (0.03578 s to 0.03604 s) and Apply preflight (0.03534 s to 0.03485 s)
are unchanged and both acceptance targets still pass.

The high tier improves 19.3 percent, marginally below the 20 percent keep
threshold that rejected the 2026-07-29 rasterizer candidate. It is kept anyway,
and the shortfall is recorded rather than rounded away. The reasoning differs
from that rejection in every respect that made the threshold useful: the
targeted phase fell 94.4 percent rather than 4.8, the change removes code
instead of adding it, peak memory improved, coverage reuse improved 32 percent,
and the 19.3 percent figure sits inside the run-to-run noise band visible in the
untouched rasterization phase, which moved 5.2 percent between these two runs.

### Accumulator width

`numpy.cumsum` is given an explicit `uint32` accumulator rather than the int64
default, matching the `array("I")` the row prefixes have always used. The bound
is proven: the mask holds one 0/1 byte per texel, so a prefix entry cannot
exceed its row width, and overflow would need a row of 4.29 billion texels. An
int64 accumulator would double the retained prefix cache against a tracked peak
working set metric with no reachable benefit.
`tests/unit/test_alpha_classification.py` compares prefix values against an
arbitrary-precision Python reference over empty, single-pixel, all-unaffected,
all-affected, alternating, random, and 8K-wide rows, each also in its doubled
MIRROR form, and separately checks that counts come back as `int`.

### Coverage-cache reuse, re-confirmed

High-tier reuse is now 6.311 s against 11.342 s cold, 1.8x faster than cold. The
2026-07-22 "reuse slower than cold" observation has not reproduced in any of the
six benchmark runs recorded on this machine since vectorization began. The
planned coverage-cache investigation stays closed.

### Next measured bottleneck

High tier, 11.342 s cold:

| Phase | Seconds | Share |
| --- | ---: | ---: |
| Rasterization | 5.597 | 49.3% |
| Classification total | 1.619 | 14.3% |
| — run counting | 1.433 | 12.6% |
| — row-prefix construction | 0.186 | 1.6% |
| UV traversal | 1.075 | 9.5% |
| Image digest | 0.291 | 2.6% |
| Coverage cache key | 0.250 | 2.2% |
| Image read | 0.181 | 1.6% |
| Image mask | 0.062 | 0.5% |
| Coverage cache lookup | 0.054 | 0.5% |
| Image channel select | 0.046 | 0.4% |
| Coverage cache store | 0.025 | 0.2% |

Rasterization is again the dominant cost at 49.3 percent, now as Python
per-row interval arithmetic rather than clipping. Run counting is 12.6 percent
and UV traversal 9.5 percent. About 2.1 s, 18.9 percent, remains outside the
instrumented phases as input preparation, signature construction, polygon
iteration, and the instrumentation itself.

Cumulative effect of the four landed changes on this machine: the high tier went
from 80.239 s to 11.342 s, and the typical tier from 10.333 s to 3.451 s. Those
endpoints come from different sessions and are not a single controlled
measurement; each stage's percentage above is same-session.

## GPU capability at scale

Measured 2026-08-12 with a discardable spike that is not committed. Blender
5.2.0 LTS, Windows 11, NVIDIA GeForce RTX 4080, driver 610.88, OpenGL backend
reporting 4.6.0. Device limits: 8 image slots, 32768 maximum texture size, work
group counts 2147483647/65535/65535, work group sizes 1024/1024/64. Headless
`gpu.init()` costs 0.357 s once.

### The only exact upload channel is R32F

`GPUTexture` exposes no write method, so the constructor's `data=` argument is
the only route from CPU memory into a texture, and it accepts nothing but a
`FLOAT` buffer: `Only Buffer of format 'FLOAT' is currently supported`. Feeding
that float buffer to a non-float texture does not reinterpret the bits, it
produces garbage.

| Texture format | A FLOAT buffer of 0..15 reads back as |
| --- | --- |
| `R32F` | `0.0 .. 15.0` — exact |
| `R32UI` | uninitialized integers |
| `R32I` | float32 values, the known broken `R32I` readback |
| `R8UI` | all zeros |

The float32 channel is exact for integers through 2^24; 16777215 and 16777216
survive, 16777217 collapses to 16777216 and 2147483647 to 2147483648. Any exact
integer payload sent this way must stay below 2^24, which a 0/1 mask and any row
prefix over a 32768-wide image both satisfy.

`gpu.texture.from_image()` is not an exact alternative. It returns `SRGB8_A8`
for byte images and `RGBA16F` — half precision — for float images, so it cannot
carry float image data without loss.

Output is exact in the other direction: `R32UI` written by the shader and read
through `GPUTexture.read()` matched numpy on every case at every size.

### Reduction at scale works, and synchronizes

Per-row affected counts over an `R32F` mask into a one-value-per-row `R32UI`
result, two of the eight image slots, one dispatch, median of five warm runs.

| Texels | Host f32 convert | Upload | Warm dispatch | Readback | GPU end to end | numpy row sum |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,048,576 | 0.0003 s | 0.0006 s | 0.00003 s | 0.0001 s | 0.0011 s | 0.0003 s |
| 4,194,304 | 0.0012 s | 0.0021 s | 0.00003 s | 0.0003 s | 0.0036 s | 0.0014 s |
| 16,777,216 | 0.0089 s | 0.0062 s | 0.00003 s | 0.0005 s | 0.0156 s | 0.0049 s |
| 67,108,864 | 0.0377 s | 0.0263 s | 0.00003 s | 0.0008 s | 0.0648 s | 0.0216 s |

Every result was exact with zero mismatches, including after twenty dispatches
were queued and the texture read immediately, so `GPUTexture.read()` does
synchronize even though no barrier is exposed. Shader creation is 0.0007 s warm
and 0.029 s for the first shader in a process.

The shape matters more than the totals. Dispatch costs about 30 microseconds at
every size, so compute is effectively free; upload runs at roughly 10 GB/s and
is the entire cost. numpy is about three times faster end to end at every size,
because the GPU pays for a host float32 conversion and a bus crossing the CPU
never makes. A GPU pass can therefore only pay when its input is already
resident or reused many times, or when it replaces far more CPU work than a
single reduction.

### `gpu.compute.dispatch` leaves the shader bound, and that crashes Blender

Reproducible `EXCEPTION_ACCESS_VIOLATION` reading `0xFFFFFFFFFFFFFFFF`, twice at
the same address, with this stack:

```
blender::GPU_shader_bind
blender::GPU_texture_update_mipmap_chain
blender::image_get_gpu_texture
blender::BKE_image_get_gpu_texture
blender::pygpu_texture_from_image
```

`gpu.compute.dispatch()` leaves the shader bound. If the `GPUShader` is then
released — a local going out of scope is enough — Blender still holds it as the
active shader, and the next operation that binds one dereferences freed memory.
An isolated probe confirms it: dispatching from inside a function and collecting
the shader crashes on the following `gpu.texture.from_image()`, and adding
`gpu.shader.unbind()` before the function returns makes the same script exit
cleanly. Any GPU code in this extension must unbind after dispatch; the failure
mode is a hard crash of the user's Blender, not an exception.

## GPU candidate ranking

Ranked against the 11.342 s high-tier profile above: 301,088 triangles,
4,469,760 scanline rows, 4,469,760 emitted runs unioned to 2,234,880, 36,782,080
covered texels, and 100.7 M texels across 4096, 4096, and 8192 images.

| Candidate | CPU | Share | Input volume | Output volume | Work items | Reuse | Exactness |
| --- | ---: | ---: | --- | --- | ---: | --- | --- |
| Rasterization | 5.597 s | 49.3% | 7.2 MB of f32 triangles | 4.47 M runs, or 150,544 counts if fused | 4.47 M rows | masks reused by every triangle | **hard** — needs f64 or 64-bit fixed point |
| Run counting | 1.433 s | 12.6% | 403 MB of f32 prefixes plus 36 MB of runs | 150,544 counts | 4.47 M runs | prefixes reusable per image | easy, integer subtraction |
| UV traversal | 1.075 s | 9.5% | Blender RNA | UV array | 602,176 loops | none | not GPU work; it is host marshalling |
| Row prefixes | 0.186 s | 1.6% | 100.7 M texels | 100.7 M prefixes | 12,288 rows | per image | easy |
| Image digest, cache key | 0.541 s | 4.8% | — | — | — | — | out of scope per the plan |

Row prefixes are rejected on Amdahl grounds, as anticipated: removing the phase
entirely buys 1.6 percent, and the measurement above shows the GPU would be
slower than the numpy it would replace. Run counting is exact and cheap to
express but needs 439 MB across the bus to save 1.433 s, and the reduction
measurement prices that crossing at roughly 0.05 s only after a host float32
conversion that costs more than the transfer.

Rasterization is the only phase large enough to clear a 20 percent
whole-workflow gate on its own. The oracle is exact positive-area coverage of
float64 UV triangles, and f32 has a 24-bit mantissa, so it cannot survive the
adversarial suite, which includes coordinates near 1e7 with sub-ulp spacing.

### Blender's shader interface does expose 64-bit types

An earlier revision of this section asserted that it does not, and that an exact
GPU rasterizer would therefore need 64-bit fixed point synthesized from paired
32-bit words. That assertion was untested and is wrong. Compiled through
`GPUShaderCreateInfo` and dispatched on the RTX 4080 / OpenGL configuration
above, computing `(2^24 + 1) - 2^24`:

| Shader type | Result | Verdict |
| --- | ---: | --- |
| `float` control | 0 | f32 loses the bit, as expected |
| `double` | 1 | exact |
| `double` with `GL_ARB_gpu_shader_fp64` | 1 | exact |
| `int64_t` with `GL_ARB_gpu_shader_int64` | 1 | exact |
| `uint64_t` | 1 | exact |
| `umulExtended` 32x32 to 64 | 2 | exact |

Exactness is therefore not the blocker it was recorded as. What remains is a
portability question rather than a correctness one, and it belongs to the claim
levels rather than to the ranking: Metal has no fp64, so a `double` shader is an
OpenGL and Vulkan path that cannot reach *Backend-portable*. 64-bit integers are
available in Metal Shading Language, so a fixed-point formulation may port where
`double` cannot, but nothing here tests Blender's cross-compilation of either.

### The rasterizer's untaken numpy vectorization, priced honestly

Before GPU work could be justified, the plan's own rule — take or explicitly
reject every remaining CPU improvement first — required pricing the obvious one.
Stage 3 rewrote `rasterize_polygon` in pure Python and deliberately did not
vectorize it, so the vectorization the stage is named for is still owed.

Computing the same height-sorted cross-sections for every triangle at once, with
`numpy.repeat` expanding triangles into their scanline rows, is **exact**: on
2,000 triangles at 4K scale producing 4,053,250 runs, and on 2,000 small
triangles producing 65,283 runs, the sorted run triples are identical to the
shipped rasterizer, not merely equivalent. It is the same float64 arithmetic in
the same order, so this is expected rather than lucky, but it is measured.

The speed, however, depends entirely on where the batch boundary is drawn.
`rasterize_polygon` is called once per polygon with two triangles, and the
analysis loop at `addon/adapters/analysis.py:1083` interleaves it with
per-polygon UV extraction, cache keying, cache lookup, and classification.
Measured on 150,544 polygons of 2 triangles each, 2,558,205 rows:

| Path | Seconds |
| --- | ---: |
| Shipped per-polygon Python | 2.955 |
| numpy inside the existing per-polygon call | 7.938 |
| Batched: cross-sections for all 301,088 triangles at once | 0.268 |
| Batched: vectorized union of overlapping runs | 0.628 |
| Batched: scatter back into 150,544 per-polygon `Coverage` rows | 1.282 |
| **Batched total** | **2.178** |

Vectorizing inside the per-polygon call is **2.7x slower** than the shipped
Python: array setup costs more than the ~17 rows it processes. That option is
rejected on measurement.

Batching every triangle is 11x on the cross-section arithmetic alone, but the
current architecture then charges 1.910 s to union the runs and rebuild the
150,544 `Coverage` objects the analysis loop consumes. Drop-in batching is
therefore **1.4x**, which turns the 5.597 s rasterization phase into roughly
4.1 s and improves the whole workflow about 13 percent — below the 20 percent
keep threshold, and rejected by Stage 3's own instruction to reject a change
whose complexity is not justified by measured whole-workflow improvement.

An earlier note in this document projected 45 percent from the 0.278 s figure.
That was wrong: it priced the cross-section arithmetic in isolation and ignored
both the union step and the per-polygon `Coverage` construction that the current
data model requires.

The 1.282 s scatter exists only because coverage crosses into classification as
a mapping of Python tuples. `AlphaGrid.count_coverage` then walks the same
2.03 M runs one Python method call at a time for another 1.433 s. Keeping
coverage in flat arrays through classification would remove both, taking
rasterization plus run counting from 7.03 s to roughly 1.7 s — about 47 percent
of the whole workflow — but it changes `Coverage`, the coverage cache payload,
and the classification path, so it is architectural work requiring its own
design and approval rather than a continuation of this branch.

### What the benchmark fixture does and does not represent

Every measurement in this document comes from the generated grid at
`tests/blender/run_benchmarks.py:96`, never from private assets. That fixture is
a flat 388x388 planar grid: identical quads, axis-aligned UVs covering exactly
[0,1] with no overlap or tiling outside the tiled tier, and images created by
`bpy.data.images.new(..., alpha=True)`, which fills alpha uniformly at 1.0.

For GPU ranking this cuts both ways and neither direction is negligible.
Uniform triangles spanning 11 or 21 rows are the best case for SIMT, with almost
no warp divergence, so the fixture flatters a GPU rasterizer relative to a real
mesh of mixed triangle sizes. Against that, it understates arithmetic intensity:
no UV tiling outside one tier, no overlapping shells, and no alpha structure.

Private characterization against an authorized local asset confirmed the fixture
is unrepresentative in five ways that all matter to this ranking, so the
`realistic` tier was added to reproduce them from generated, redistributable
data. Its parameters were tuned until its shape matched what the private asset
measured; the private numbers themselves stay out of this document per the
repository's private-input policy, but the tier's numbers are committable and
every figure below comes from it.

## Realistic tier

Same 150,544 polygons and 301,088 triangles as the high tier, but with unevenly
sized UV islands, multi-tile addressing throughout, half the polygons reusing a
shared island, five images at mixed square and non-square resolutions, a
collapsed UV quad every 83 polygons, and structured alpha instead of a uniformly
opaque fill. Cold 11.554 s, coverage reuse 7.025 s, reuse with a changed image
6.902 s, peak working set 2.887 GiB.

| Phase | Seconds | Share |
| --- | ---: | ---: |
| Rasterization | 4.711 | 40.8% |
| Classification | 2.982 | 25.8% |
| UV traversal | 1.301 | 11.3% |
| Coverage cache key | 0.233 | 2.0% |
| Image digest | 0.112 | 1.0% |
| Row-prefix construction | 0.067 | 0.6% |
| Image read | 0.064 | 0.6% |
| Coverage cache lookup | 0.039 | 0.3% |
| Image mask | 0.024 | 0.2% |
| Image channel select | 0.016 | 0.1% |
| Coverage cache store | 0.015 | 0.1% |
| Unattributed | 1.991 | 17.2% |

What separates it from the high tier, at a nearly identical 11.124 s cold:

| Characteristic | High complexity | Realistic |
| --- | ---: | ---: |
| Scanline rows per triangle | 14.8 | 37.2 |
| Unioned runs | 2,234,880 | 5,599,082 |
| Covered virtual texels | 36,782,080 | 305,101,168 |
| Coverage cache hit rate | 0% | 49.1% |
| Degenerate UV triangles | 0 | 3,628 |
| Classification share | 14.3% | 25.8% |

The two tiers take the same wall time and rank accelerators differently. On the
even grid, classification is 14.3 percent and was rejected; on a realistic
workload it is 25.8 percent and clears the 20 percent keep threshold on its own.
It is also the more reliably hot phase of the two, because the coverage cache
absorbs roughly half of rasterization while classification is paid for every
polygon. Rasterization plus classification is 66.6 percent of the tier.

Adding the tier changed no existing tier: `small`, `typical`, `high`, and
`large_tiled_uv` all produce byte-identical `triangles`, `scanlines`,
`emitted_runs`, `union_runs`, `covered_texels`, `degenerate_triangles`, and
`coverage_cache_misses` before and after, with cold times within noise.

### Candidate ranking, recomputed against the realistic tier

The ranking above is superseded by this one. Same candidates, same method,
11.554 s realistic profile instead of the 11.342 s high tier: 301,088 triangles,
11,198,164 scanline rows, 11,198,164 emitted runs unioned to 5,599,082,
305,101,168 covered texels, and 38.5 M texels across five images.

| Candidate | CPU | Share | Input volume | Output volume | Work items | Reuse | Exactness |
| --- | ---: | ---: | --- | --- | ---: | --- | --- |
| Rasterization | 4.711 s | 40.8% | 7.2 MB of f32 triangles | 11.2 M runs, or 76,647 counts if fused | 11.2 M rows | masks reused by every triangle | needs f64 or 64-bit fixed point, both available |
| Classification | 2.982 s | 25.8% | 154 MB of f32 prefixes plus 67 MB of runs | 150,544 counts | 5.6 M runs | prefixes reusable per image | easy, integer subtraction |
| UV traversal | 1.301 s | 11.3% | Blender RNA | UV array | 602,176 loops | none | not GPU work; it is host marshalling |
| Row prefixes | 0.067 s | 0.6% | 38.5 M texels | 38.5 M prefixes | 11,264 rows | per image | easy |
| Image digest, cache key | 0.345 s | 3.0% | — | — | — | — | out of scope per the plan |

Two rankings change materially against the grid fixture, and both change in the
same direction — toward classification:

- **Classification clears the keep threshold on its own.** 25.8 percent against
  14.3 percent on the grid, because real UV layouts tile and unevenly sized
  islands produce 2.5x the runs per triangle.
- **Rasterization is paid for half the polygons and classification for all of
  them.** The coverage cache hits 73,897 of 150,544 polygons, so the fused
  candidate's rasterization half is discounted by the hit rate while its
  classification half is not. On the grid fixture the hit rate is zero and this
  asymmetry is invisible.

Row prefixes fall further, to 0.6 percent, and are rejected more firmly than
before. UV traversal rises but remains host marshalling that no accelerator
addresses.

### Position of the Stage 6 gate

The gate does not close, but it does not proceed on this profile either.

Two of the three original rejections stand on their own measurements and are not
sensitive to workload complexity. Row prefixes are 0.6 percent of the realistic
workflow, so Amdahl caps them regardless of how fast the GPU is, and the
reduction spike measured the GPU slower than the numpy it would replace.
Classification as a standalone candidate needs 221 MB across the bus to save
2.982 s; it is worth more on a realistic workload than the grid fixture showed,
but it is bandwidth-bound in exactly the way the reduction spike measured.

The fused rasterize-and-classify candidate is the one that survives. Its
expensive input, the alpha mask, uploads once and is reused by every polygon
mapping to that image, so its arithmetic intensity is high and rises with mesh
complexity — the opposite of the bandwidth-bound reduction that was measured.
An earlier revision of this section claimed the reduction measurements already
priced this candidate's transfer costs above the work it saves. They do not; the
two have different dataflows, and no prototype of the fused candidate exists.

What blocks it is sequencing, not feasibility. The GPU candidate and the CPU
flat-array change need the same prerequisite: coverage must stop crossing into
classification as a mapping of Python tuples. That data-model change moves the
denominator every GPU number would be measured against, so prototyping the GPU
path first would measure it against a baseline that is about to change.

The 47 percent estimated for that change, and the 27 percent left for a perfect
GPU replacement afterwards, both come from microbenchmarks run at high-tier
scale — 2,558,205 rows, no cache hits, no degenerate triangles. The realistic
tier has 11.2 M rows and a 49.1 percent hit rate, so neither number transfers
and neither has been re-measured. What does transfer is the ordering: the two
phases the change targets are 66.6 percent of the realistic tier, more than the
61.9 percent they were on the grid.

## Flat-array coverage and batched counting

The prerequisite landed. Coverage no longer crosses into classification as a
mapping of Python tuples; it is one `(3, run_count)` int64 array of virtual row,
start, and half-open stop. `AlphaGrid` keeps row prefixes in a lazily-filled 2D
buffer a whole batch can gather from, and `AnalysisEngine.step` defers counting
to the end of its polygon chunk, counting each `(image, address mode)` group in
one pass.

Same-session, all five tiers. Every triangle, scanline, emitted-run, union-run,
covered-texel, degenerate-triangle and cache counter is identical before and
after:

| Tier | Before | After | Change |
| --- | ---: | ---: | ---: |
| Small | 0.311 s | 0.198 s | -36.2% |
| Typical | 3.327 s | 2.124 s | -36.2% |
| High complexity | 10.983 s | 6.963 s | -36.6% |
| Large tiled UV | 0.690 s | 0.347 s | -49.8% |
| Realistic | 11.604 s | 6.444 s | **-44.5%** |

Realistic tier phases, and the two secondary metrics:

| Phase | Before | After |
| --- | ---: | ---: |
| Rasterization | 4.744 s | 2.371 s |
| Classification | 3.036 s | 0.410 s |
| UV traversal | 1.298 s | 1.139 s |
| Row prefixes | 0.075 s | 0.053 s |
| Coverage reuse (whole run) | 7.075 s | 3.906 s |
| Peak working set | 2949.8 MiB | 2080.4 MiB |

### Why rasterization improved as well

The change was justified on classification alone, but rasterization halved too,
and that is a property of the container rather than a surprise. Measured over
150,544 constructions at 37 runs each, plus the chunk assembly a batched counter
needs:

| Per-polygon container | Build | Assemble | Total |
| --- | ---: | ---: | ---: |
| Dict of per-row tuples | 1.585 s | 0.637 s | 2.222 s |
| **One 2D int64 array** | **0.355 s** | **0.031 s** | **0.386 s** |
| Three 1D int64 arrays | 0.428 s | 0.076 s | 0.504 s |
| Three `array("q")` | 0.334 s | 0.178 s | 0.511 s |
| One interleaved `array("q")` | 0.595 s | 0.026 s | 0.620 s |

The replacement is cheaper to build than the representation it removes, so the
rasterizer stopped paying for a dict, a tuple per run, and two integer objects
per run. That also accounts for most of the 869.4 MiB drop in peak working set.

### What the estimates got right and wrong

The projection before implementation was 23 percent, from a scratchpad prototype
of batched counting alone against the realistic tier's real run distribution:
557 ns per run scalar against 59 ns batched, a 9.5x ratio on 5,599,082 runs.
That ratio held — classification landed at 0.410 s against a predicted 0.41 s.

The 23 percent was low because it priced only the counting phase. It did not
predict that the container replacing the dict would also be cheaper to build.

Two earlier figures in this document are now settled. The 47 percent attributed
to this change was measured at high-tier scale and did not transfer; the actual
result is 44.5 percent on the realistic tier and 36.6 percent on the high tier.
The 1.282 s scatter that made drop-in batched rasterization only 1.4x is gone,
because there is no longer a per-polygon dict to scatter into.

### Position of the Stage 6 gate, again

The gate stays open and the sequencing argument is discharged. Rasterization is
now 36.8 percent of a 6.444 s realistic tier and classification is 6.4 percent,
so the fused rasterize-and-classify candidate is worth at most 43.2 percent
rather than the 66.6 percent it was worth against the old baseline, and any
GPU prototype now has a stable denominator to measure against.

Unattributed time is 30.7 percent of the realistic tier, up from 17.2 percent,
because the phases around it shrank while it did not. It is the second largest
line in the profile and has never been attributed; that is the next thing worth
measuring, ahead of any accelerator.

## Attributing the unattributed remainder

Every earlier profile in this document timed the stepping loop and nothing else.
Engine construction ran before `AnalysisEngine.metrics` existed, so the work it
does — the structural and assignment signatures, then `_prepare` — was outside
every `phase_*` accumulator. On the realistic tier that was most of the missing
third.

Split with plain timers, before adding any instrumentation:

| Segment | Seconds | Share |
| --- | ---: | ---: |
| Construction | 1.428 | 22.6% |
| Stepping | 4.900 | 77.4% |
| Finish | 0.000 | 0.0% |
| Instrumented at the time | 4.383 | 69.3% |
| Unattributed at the time | 1.945 | 30.7% |

Construction was 1.428 s of the 1.945 s. `_structural_signature` was 0.816 s
`tottime` and 2.605 s cumulative under the profiler, calling `struct.pack`
4,670,047 times and `blake2b.update` 4,821,261 times — one pack and two updates
per vertex, edge, loop, polygon and UV.

Two timers now cover construction. `phase_signature_seconds` covers both
signatures; `phase_prepare_seconds` covers `_prepare` with the image phases it
nests subtracted, because those are already reported as their own deltas.

| Phase | Seconds | Share |
| --- | ---: | ---: |
| Rasterization | 2.403 | 37.2% |
| **Signatures** | **0.996** | **15.4%** |
| UV traversal | 0.975 | 15.1% |
| Classification | 0.548 | 8.5% |
| Cache key | 0.218 | 3.4% |
| **Prepare** | **0.215** | **3.3%** |
| Image digest | 0.112 | 1.7% |
| Image read | 0.070 | 1.1% |
| Row prefixes | 0.062 | 1.0% |
| Cache lookup, store | 0.062 | 1.0% |
| Image mask, select | 0.042 | 0.7% |
| Unattributed | 0.751 | 11.6% |

Unattributed fell from 30.7 percent to 11.6 percent. The two new phases total
1.211 s against the 1.194 s that went missing, so the attribution closes within
timer noise rather than merely shrinking.

The 11.6 percent that remains is the stepping loop's own interpreter overhead:
the parts of `_analyze_polygon` outside the timed regions, `_record_face`, and
16,015,537 `list.append` calls at 1.137 s under the profiler. It is diffuse, not
a phase, and no single change collects it.

### The signature is now the second largest phase

`_structural_signature` is 15.4 percent of the realistic tier, ahead of UV
traversal. Vectorizing it — `foreach_get` into arrays and one `blake2b.update`
per attribute instead of one per element — is the obvious shape. It was taken
in the next change, after establishing that the digest never leaves the process.

## Vectorized structural signature

### The digest is same-process only, which is what makes this safe

Changing how the signature is computed changes its value, so the question that
had to be answered first is whether any stored value is ever compared against a
freshly computed one.

It is not. `_structural_signature` is only compared to a same-process recompute,
in `validate_report_for_publication` and in the staleness check. It reaches
`analysis_id` through `_input_signature`, and `analysis_id` reaches
`report_json` and `expected_review_signature` — but `runtime.register_handlers`
attaches a `@persistent` clear to `load_post`, `undo_post` and `redo_post` that
blanks both. The digests that *are* written into the `.blend` —
`alpha_material_separator.source_fingerprint` and
`derived_fingerprint_at_creation` — come from `fingerprints.material_fingerprint`,
which the structural signature does not feed.

The version tag moved to `ALPHA_MATERIAL_SEPARATOR_STRUCTURAL_V2` to record that
the encoding changed even though nothing compares across versions.

### What changed

Five per-element loops became six whole-attribute reads: `foreach_get` into a
numpy array of explicit little-endian width, then one length-prefixed
`add_bytes` per attribute. `loop_start`, `loop_total` and `material_index` are
read separately rather than packed as interleaved triples; `loop_total` is
read-only in Blender 5.2 but still readable, and it derives from consecutive
`loop_start` offsets.

Framing is unchanged or better. Each block carries its own length prefix, so an
attribute's element count is now explicit in the digest where before it was
implied by a run of equally sized chunks.

### Result

Same-session, realistic tier, one discarded warm-up and the median of five
measured runs:

| | Before | After | Change |
| --- | ---: | ---: | ---: |
| Signature phase | 1.188 s | 0.120 s | -89.9% |
| Whole tier | 7.482 s | 6.491 s | -13.2% |
| Peak working set | 931.0 MiB | 916.4 MiB | -1.6% |

An independent pair run first, without the memory counter, measured 1.209 s to
0.118 s and 7.642 s to 6.518 s, so the phase ratio reproduces at about 10x and
the whole-tier figure at about 14 percent.

The signature falls from 15.4 percent of the tier to 1.8 percent. The 4,670,047
`struct.pack` calls and 4,821,261 `blake2b.update` calls the profile attributed
to it become six array reads and six updates per mesh.

### Below the keep threshold, and kept

13.2 percent is under the repository's 20 percent whole-workflow threshold, the
same situation as the row-prefix change at 19.3 percent. It is kept for a reason
that does not apply to most sub-threshold wins: the diff is smaller than what it
replaces. Fifteen lines of per-element packing became six lines of attribute
reads, and the threshold exists to stop complexity being added for small gains.
Here complexity went down.

### Regression added

`_structural_signature_sensitivity_test` in `tests/blender/test_analysis_preview.py`
mutates each hashed mesh array in turn — vertex `co`, edge `vertices`, loop
`vertex_index`, polygon `material_index`, polygon `loop_start`, a new UV layer,
and a UV coordinate — and requires each to produce a digest not seen before. The
revalidation matrix already covered vertex and UV edits; edges, loops and the
polygon fields had no coverage and are exactly what a whole-array read can
silently stop reading.

The test was confirmed non-vacuous before the change by deleting the edge loop
from the old implementation, which failed it with `edge_vertices did not change
the structural signature`.

## Batched rasterization, re-measured

The 1.4x that rejected drop-in batched rasterization was measured when the
rasterizer scattered runs into a per-polygon dict, and that 1.282 s scatter no
longer exists. The measurement was redone against the current implementation,
on the real triangle distribution: every `rasterize_polygon` input the realistic
tier issues, captured to an array — 76,647 calls, 153,294 triangles, exactly two
per polygon because the fixture is quads.

### The prototype is exact

A batched prototype reproduces the scalar rasterizer bit for bit: **0 of 76,647
polygons differ**, at every chunk size tested, with the same 2,811,456 union
runs. Exactness needs three details that are easy to get wrong.

The scalar loop carries `previous_long` and `previous_short` across rows, which
looks like a sequential dependency but is not: those are the cross-sections at
the row's lower boundary, which is the bottom vertex on a triangle's first row
and the integer scanline everywhere else. Computing them directly is equivalent.

The chained `if/elif` that narrows `minimum` and `maximum` is a plain min and
max of the four cross-sections, because a value below the running minimum is
necessarily below the running maximum.

The last band reassigns `upper` to `high_y`, so the middle-vertex straddle test
`row < mid_y < upper` compares against the clamped value, not `row + 1`.

### The three-key sort was most of the cost

The first prototype ran 1.69x — better than 1.4x but far short of what the
arithmetic suggested. The merge was 58 percent of it, and `numpy.lexsort` on
`(start, row, polygon)` was 0.732 s of the merge's 0.884 s.

One composite int64 key does the same ordering in 0.074 s, about 10x less. Row
and start ranges are offset to non-negative and packed with the polygon index
into a single sort key; the observed ranges need 46 bits, and anything that does
not fit in 62 falls back to lexsort.

### Chunk size matters more than expected

| Chunk | Seconds | Speedup |
| ---: | ---: | ---: |
| 128 | 0.392 | 6.39x |
| 192 | 0.348 | 7.13x |
| **256** | **0.339** | **7.41x** |
| 320 | 0.384 | 6.48x |
| 512 | 0.429 | 5.90x |
| 1024 | 0.500 | 5.07x |
| 2048 | 0.785 | 3.21x |
| 4096 | 0.757 | 3.37x |
| all 76,647 | 0.809 | 3.11x |

Batching everything at once is less than half the speed of batching 256
polygons. At 256 the intermediate arrays are about 19,000 rows, which stays in
cache; past that every pass re-reads from memory. This is the opposite of the
intuition that a bigger batch amortizes more overhead, and it is why the chunk
size is a measured constant rather than the analysis loop's step budget.

### What the prototype leaves out, priced

The prototype rasterizes and merges. Production also has to convert the UV
phase's Python tuples into an array and produce per-polygon `RasterStats`:

| | Seconds |
| --- | ---: |
| Batched rasterize and merge, chunk 256 | 0.339 |
| Tuple-to-array conversion, 153,294 triangles | 0.057 |
| Per-polygon stats via `bincount` | 0.033 |
| Total | 0.429 |
| Scalar reference on the same data | 2.500 |

That is **5.8x** all in. Against the measured 2.899 s rasterization phase it
projects to about 0.50 s, taking the realistic tier from 6.491 s to roughly
4.09 s, a 37 percent whole-workflow improvement — comfortably above the 20
percent keep threshold, unlike the last two changes.

Still unpriced, because they are correctness work rather than throughput: the
per-polygon `max_scanlines` and `max_run_emissions` budgets, which become
segment sums and a comparison rather than a raise mid-loop; `InvalidRasterInput`
for non-finite UVs; the `margin_texels` expansion; and splitting batch results
back to the per-polygon coverage cache. None of them changes the classification
a polygon receives, but all of them have to be reproduced before this can ship.

## Batched rasterization, implemented

`rasterize_batch` in `addon/core/raster.py` ships the measured prototype with
the four pieces of correctness work priced above. `_analyze_polygon` no longer
rasterizes; it defers a coverage-cache miss the same way it already deferred
counting, and `_flush_pending` rasterizes the whole step chunk before counting
it.

### The correctness work, as built

Budgets became segment sums. `_within_segment` recomputes each polygon's
running scanline and run totals with one `cumsum` and a per-segment subtraction,
and a polygon trips when its running total passes the budget. Resolving *which*
budget tripped needs the ordered semantics of the scalar loop, which checks the
scanline budget for a triangle before emitting that triangle's runs, so an equal
trip position reports scanlines. That resolution runs behind an `any()` guard:
budgets are pathological-input guards and the unbuffered `numpy.minimum.at`
scatter it needs is not worth paying for on every batch.

`InvalidRasterInput` became one `numpy.isfinite(...).all(axis=(1, 2))` test, and
the affected polygons are dropped before the shared arithmetic so a single NaN
cannot poison its neighbours' results.

`margin_texels` expands each merged run into `2m + 1` rows and merges a second
time, exactly as the scalar tail does, re-checking the run budget in between.

Splitting back is a slice, not a copy. Each polygon's `Coverage` is a view into
the chunk's merged span array; the array outlives the views, and since every
coverage in it is cached anyway, nothing is retained that would not have been.

### Result

Same-session, realistic tier, one discarded warm-up and the median of five
measured runs:

| | Before | After | Change |
| --- | ---: | ---: | ---: |
| Rasterization phase | 2.625 s | 0.672 s | -74.4% |
| Whole tier | 6.017 s | 3.962 s | -34.2% |
| Peak working set | 1061.4 MiB | 1042.6 MiB | -1.8% |
| Coverage reuse run | 3.952 s | 3.147 s | -20.4% |

All eight counters are identical before and after: 301,088 triangles, 3,628
degenerate triangles, 11,198,164 scanlines, 11,198,164 emitted runs, 5,599,082
union runs, 305,101,168 covered texels, 73,897 coverage-cache hits and 76,647
misses.

The phase improved 3.91x rather than the projected 5.8x, and the tier 34.2
percent rather than 37. The gap is the flattening of the UV phase's Python
tuples into one array per chunk, which the prototype measured on data that was
already an array, plus the per-chunk dictionary pass that deduplicates by
coverage key. Both are real and neither was avoidable.

### Two polygons, one coverage key, in the same chunk

Deferring the rasterization moves every lookup in a chunk ahead of every store,
so two polygons with identical UV triangles now both miss the cache where the
second used to hit it. On the realistic tier that is 3,970 of 150,544 polygons.

`_rasterize_pending` groups the misses by coverage key and rasterizes each key
once, so the work is unchanged, and it moves the duplicate from the miss counter
to the hit counter so the reuse metric keeps measuring reuse rather than lookup
ordering. Without that adjustment the same run reports 80,617 misses and 69,927
hits for exactly the same rasterization work.

### Chunk size, re-measured on the shipped function

The prototype's 256-polygon optimum survives the addition of per-polygon
`RasterStats` and `Coverage` construction, measured against the same 76,647
captured polygons:

| Chunk | Seconds | Speedup |
| ---: | ---: | ---: |
| 128 | 0.557 | 4.48x |
| **256** | **0.506** | **4.99x** |
| 512 | 0.616 | 4.05x |
| 1024 | 0.662 | 3.74x |

`_RASTER_BATCH_POLYGONS` is therefore a measured constant in
`addon/adapters/analysis.py`, deliberately independent of the analysis loop's
step budget, which the modal operator sets to 256 and the benchmark to 4,096.

### Regressions added

`BatchedRasterizationTests` in `tests/unit/test_rasterization.py` holds six
tests that require `rasterize_batch` to equal `rasterize_polygon` polygon for
polygon, including `stats`: on the 27 adversarial cases with and without a
margin, on 400 randomized quads, when one polygon in a batch trips a budget or
carries a non-finite UV, when the margin expansion itself trips the run budget,
on empty and all-degenerate input, and when the composite sort key overflows
into the `lexsort` fallback. The adversarial case list and the randomized-quad
generator were lifted to module scope so the batch and scalar tests share one
definition rather than two copies.

`_batched_rasterization_equivalence_test` in
`tests/blender/test_analysis_preview.py` runs a 600-triangle fixture — enough to
cross the 256-polygon seam — with scattered UVs and deliberate duplicate
coverage keys, and requires every face's `RasterStats` and all six aggregate
counters to equal an oracle built from the mesh with `rasterize_polygon`.

The oracle is built from the mesh rather than by swapping `rasterize_batch` for
a scalar shim underneath the adapter. That was the first version of this test
and it was worthless: an adapter bug corrupts both sides of such a comparison
equally and it still passes. Confirmed by sabotage — reversing the result-to-key
mapping, adding one to the margin, and assigning a deduplicated coverage to only
the first of its polygons all passed the shim version and all fail the current
one.

### Next measured bottleneck

UV traversal is now the largest phase of the 3.962 s tier at 32.5 percent, ahead
of rasterization at 16.9 percent and classification at 10.8 percent. It is the
per-loop Python read of `uv_layer.uv[i].vector` followed by a per-point
`uv_to_texel_edge` call, and it is a `foreach_get` away from being one array
operation — the same change the structural signature already took.

Unattributed time is 16.9 percent, but it did not grow: it is 0.669 s against
0.657 s before, essentially unchanged in absolute terms while the phase around
it shrank. That reinforces the earlier conclusion that it is diffuse interpreter
overhead in the stepping loop rather than an unmeasured phase.

## Vectorized UV traversal, implemented

The three phases the batched-rasterization profile left at the top — UV
traversal, cache-key construction and prepare — were all the same shape: a
Python loop over mesh elements, one attribute read at a time. Together they were
1.629 s of the 3.742 s realistic tier.

### What changed

`_prepare` no longer builds a dict of per-polygon triangle tuples. `_triangle_layout`
reads `loops` and `polygon_index` off `mesh.loop_triangles` with two
`foreach_get` calls, and a polygon's triangles become the `triangle_counts` rows
starting at `triangle_starts`. That slice replaces the dict lookup, so the
prepare phase stops paying for one tuple and one dict entry per triangle.

The slice is only valid because Blender emits loop triangles grouped by polygon
and ascending. Measurement says it does, on every mesh tried, but the layout
sorts when it does not: a stable `argsort` on an already-sorted array is cheap
enough that depending on the ordering would buy nothing.
`_loop_triangle_order_test` pins the assumption so a future Blender that breaks
it fails loudly rather than silently mis-slicing.

`_texel_grid` reads a UV map with one `foreach_get` and scales the whole array
to texel edges once per image size. It is keyed by `(map, width, height)`, not
by material slot: the realistic tier's sixteen slots share four distinct image
sizes, so that is four scaled arrays rather than sixteen. Both dictionaries fill
lazily, because a UV map no resolved material names is never read at all.
`_analyze_polygon` then indexes the grid with the polygon's loop slice, which
produces the `(triangles, 3, 2)` array `rasterize_batch` already wanted.

The cache key follows from that array. `AMS_COVERAGE_V2` hashes it with one
`tobytes()` instead of a `struct.pack("<2d", ...)` per point. The encoding is
native `float64` rather than an explicit `<f8`, because `foreach_get` writes
native C doubles and the coverage cache is a process-local dict — no stored key
is ever compared against one produced by another build.

### Non-finite UVs

`uv_to_texel_edge` validated finiteness per point and nothing in the stepping
loop catches what it raises, so today a single NaN UV aborts the whole analysis
with `ANALYSIS_FAILED`. Vectorizing removes that per-point call, so the abort is
reproduced deliberately: `_texel_grid` tests the whole array with
`numpy.isfinite` once and keeps a mask of the offending loops, and
`_analyze_polygon` raises the same `InvalidRasterInput` when a polygon touches
one. Converting it to a per-face `INVALID_UV` may well be an improvement, but it
is a behavior change and a separate decision. `_non_finite_uv_test` pins the
current behavior either way.

### Result

Same-session, realistic tier, one discarded warm-up and the median of five
measured runs:

| | Before | After | Change |
| --- | ---: | ---: | ---: |
| UV traversal phase | 1.220 s | 0.247 s | -79.7% |
| Cache-key phase | 0.211 s | 0.103 s | -51.2% |
| Prepare phase | 0.198 s | 0.051 s | -74.4% |
| Rasterization phase | 0.619 s | 0.474 s | -23.4% |
| Whole tier | 3.742 s | 2.412 s | -35.5% |
| Coverage reuse run | 2.971 s | 1.890 s | -36.4% |
| Peak working set | 995.9 MiB | 999.7 MiB | +0.4% |

All eight counters are identical before and after, and identical to the batched
rasterization measurement: 301,088 triangles, 3,628 degenerate triangles,
11,198,164 scanlines, 11,198,164 emitted runs, 5,599,082 union runs, 305,101,168
covered texels, 73,897 coverage-cache hits and 76,647 misses.

The three targeted phases went 1.629 s to 0.401 s, 4.07x, against the scratchpad
prototype's projected 4.44x. Rasterization improved as well without being
touched: `numpy.concatenate` replaced the comprehension that flattened Python
tuples into the batch array, which is exactly the cost the previous section
named as the gap between batched rasterization's projected 5.8x and its shipped
3.91x. It recovers 0.145 s of it.

Peak working set rose, which none of the earlier stages did. The scaled grids
are the reason: the resident cost per object is `loops * 16 * (1 + sizes)` bytes
per UV map, one raw array plus one scaled array per distinct image size. Four
megabytes here. Scaling at slice time instead would avoid it and was rejected on
measurement — a multiply per polygon costs more than the phase saves.

### Regressions added

Three tests in `tests/blender/test_analysis_preview.py`, all characterization
rather than RED, because a refactor that changes any value is a failure:

- `_loop_triangle_order_test` builds a triangle, a quad and a hexagon and
  requires `mesh.loop_triangles` to be ascending by `polygon_index` with one,
  two and four entries;
- `_uv_traversal_values_test` captures what actually reaches `rasterize_batch`
  through a wrapper and compares it to an oracle read loop by loop with
  `uv_to_texel_edge`, on a 40-polygon fixture with its duplicate coverage keys
  removed so every polygon appears in the batch exactly once;
- `_non_finite_uv_test` sets one loop's UV to NaN and requires
  `InvalidRasterInput` to propagate out of `step`.

### Next measured bottleneck

Rasterization is the largest phase again at 19.7 percent of the 2.412 s tier,
then classification at 16.0 and UV traversal at 10.2. Both of the top two are
already vectorized and neither has an untaken CPU idea behind it.

Unattributed time is now the largest single item at 31.1 percent, 0.751 s
against 0.681 s before. That is inside the run-to-run spread — the five cold
runs span 2.376 s to 2.484 s, and the phase totals come from one run while the
tier figure is a median of five — so it is best read as flat in absolute terms
while everything around it shrank, not as growth. It remains diffuse interpreter
overhead in the stepping loop: `_analyze_polygon` is still one Python call per
polygon, and 150,544 of them cost what they cost.

## Attributing the residual, and one wrong claim

The previous section called the 31.1 percent residual "diffuse interpreter
overhead in the stepping loop" that "would need the per-polygon loop itself
replaced, not a phase optimized." Measurement contradicts that. Eleven of those
points are a single named function.

### The hypothesis that failed first

The residual works out to 4.99 microseconds per polygon, and the visible
suspects in the stepping loop are RNA reads: `step()` builds a `MeshPolygon`
proxy per iteration and `_analyze_polygon` reads `.material_index` and `.index`
off it, then reads `material_slots[i].material`. Each line item was timed as its
own loop over the same 150,544 polygons, so the timer cost is paid once per loop
rather than once per statement:

| Statement | Seconds | Share of residual |
| --- | ---: | ---: |
| `_DeferredFace` construction | 0.0476 | 6.3% |
| `polygons[i]` proxy + `.material_index` + `.index` | 0.0350 | 4.7% |
| `material_slots[i].material` | 0.0269 | 3.6% |
| `material.as_pointer()` | 0.0148 | 2.0% |
| `resolutions.get` + `snapshots.get` | 0.0048 | 0.6% |
| one bound method call | 0.0038 | 0.5% |

Everything named sums to 0.134 s, 17.9 percent of the residual. Replacing the
RNA reads with `foreach_get` and a `tolist()` index saves 0.021 s — 2.8 percent
of the residual, 0.9 percent of the tier. The hypothesis was wrong and the
change is not worth making.

### Where it actually is

`_run_analysis` times engine construction, every `step()` call and `finish()`
together, so anything outside a phase accumulator in any of the three lands in
the residual. Timing the three separately, and adding one per-chunk timer around
the `_record_face` loop in `_flush_pending`:

| | Seconds | Share of a 2.480 s cold run |
| --- | ---: | ---: |
| Engine construction | 0.379 | 15.3% |
| Stepping | 2.083 | 84.0% |
| `finish()` | 0.011 | 0.4% |
| **`_record_face` loop** | **0.296** | **11.9%** |
| Residual after that timer | 0.480 | 19.4% |

`_record_face` runs once per polygon at the tail of `_flush_pending`, outside
`phase_classify_seconds` and outside everything else. It is the third-largest
cost in the analysis, behind rasterization and classification and ahead of UV
traversal, and no instrumentation on this branch has ever seen it.

Its statements, timed the same way:

| Statement | Seconds | Share of `_record_face` |
| --- | ---: | ---: |
| `metrics.update({6 keys})` | 0.1457 | 49.3% |
| `FaceAnalysis` construction and dict store | 0.0475 | 16.1% |
| `face_indices` append and `counts` increment | 0.0165 | 5.6% |
| `classified` attribute reads | 0.0079 | 2.7% |

Half of it is one statement, and that statement is pure aggregation: six raster
counters summed into a `Counter` through a freshly built dict literal, once per
face. Six plain `metrics[key] += value` increments instead measure 0.0730 s, and
accumulating into local integers and adding once per chunk removes essentially
all of it. That is roughly 0.13 s, 5.2 percent of the tier, for a change of a
few lines.

This run measured 2.480 s against the 2.412 s recorded for the same code in the
previous section. The two are separate sessions and the instrumented copy
carries an extra per-chunk timer, so the shares above are fractions of their own
run and the absolute figures are not comparable across the two.

### What is left

The residual after the `_record_face` timer is 0.480 s, and it splits roughly
0.21 s inside engine construction — which `phase_prepare_seconds` and
`phase_signature_seconds` cover only 0.165 s of, despite an earlier claim on
this branch that two timers now cover it — and about 0.25 s spread across the
stepping loop, which is where the failed hypothesis above says the money is not.

So the per-polygon loop removal has a much weaker case than the 31.1 percent
figure suggested. The genuinely diffuse part of the stepping loop is about 10
percent of the tier, not 31, and the named statements inside it total under 6.

## Per-chunk raster counters, implemented

The `metrics.update({6 keys})` measured at half of `_record_face` is pure
aggregation. `_flush_pending` now sums the six raster counters into local
integers across the chunk's record loop and adds them to `metrics` once, and
`_record_face` no longer touches `metrics` at all.

### Result

Same-session, realistic tier, run as two independent before/after pairs because
the first pair showed an unexplained movement in a phase nothing had touched:

| | Before | After | Change |
| --- | ---: | ---: | ---: |
| Whole tier, pair 1 | 2.415 s | 2.264 s | -6.2% |
| Whole tier, pair 2 | 2.430 s | 2.285 s | -6.0% |
| Coverage reuse, pair 1 | 1.884 s | 1.723 s | -8.6% |
| Coverage reuse, pair 2 | 1.890 s | 1.746 s | -7.6% |
| Peak working set | 1002.1 MiB | 996.6 MiB | -0.5% |

All eight counters are identical before and after. The measured saving is 0.145
to 0.147 s against 0.13 s predicted from the statement breakdown.

`phase_classify_seconds` rose 16 percent in the first pair, in a region the
change does not touch. It did not reproduce: the second pair moved it 1.1
percent. Across five benchmark invocations that phase reports either about
0.39 s or about 0.46 s, in both configurations, so it is bimodal per invocation
and phase-level comparisons of classification at that granularity are not
meaningful. The whole-tier figure, which is a median of five runs within each
invocation, is stable to about 0.2 percent between the two pairs.

At 6.1 percent this is well under the 20 percent keep threshold. It is kept on
the same argument as the signature vectorization: the diff is smaller than what
it replaces. One guard was added with it — a chunk in which nothing rasterizes
must not create the six keys at zero, because `report.metrics` is the whole
counter and that would change the report rather than only its timing.
`_raster_counters_absent_when_nothing_rasterizes_test` drives a polygon whose UV
triangle exceeds the scanline budget and requires the keys to stay absent; it
fails when the guard is removed.

### Engine construction was already attributed

The previous section said roughly 0.21 s of the 0.379 s engine construction was
unattributed, because `phase_prepare_seconds` and `phase_signature_seconds`
cover only 0.165 s of it. That subtraction was wrong. Construction also runs the
four image phases, which `_prepare` nests and reports as their own deltas
exactly as the comment above `phase_prepare_seconds` says. Signature 0.112 s,
prepare 0.053 s, image digest 0.112 s, image read 0.065 s, image mask 0.024 s
and image select 0.015 s total 0.382 s against 0.379 s measured. There is
nothing unattributed in construction and nothing to instrument.

The whole residual is therefore in the stepping loop, and always was.

### Where the tier stands

| Phase | Seconds | Share |
| --- | ---: | ---: |
| Rasterization | 0.482 | 21.3% |
| Classification | 0.456 | 20.2% |
| UV traversal | 0.250 | 11.1% |
| Image digest | 0.110 | 4.9% |
| Cache key | 0.104 | 4.6% |
| Structural signature | 0.097 | 4.3% |
| Everything else attributed | 0.242 | 10.7% |
| Unattributed | 0.518 | 22.9% |

Of the unattributed 0.518 s, about 0.15 s is what remains of `_record_face` —
`FaceAnalysis` construction and the dict and list bookkeeping, which the report
contract requires — leaving roughly 0.37 s genuinely diffuse across the stepping
loop. The statements named earlier in that loop total 0.134 s of it, and
replacing the largest of them was measured at 0.9 percent of the tier.

## Stage 6E, pricing the GPU dataflow before writing the rasterizer

The plan gates GPU work on measurement, and the measurement it demands is the
complete dataflow: preparation, upload, dispatch, execution, readback and
cleanup, with command submission never counted as completion. Three spikes
priced those pieces on the realistic tier before any rasterizer existed. Every
number below is one process, one fixture, medians of five.

### What a counts-returning kernel can actually replace

Not `phase_classify_seconds`. That phase is three things, and only the middle
one is GPU work:

| Part of classification | Seconds |
| --- | ---: |
| Grouping the chunk by image and address mode | 0.015 |
| `count_batch` prefix gather | 0.160 |
| `classify_counted` per polygon | 0.152 |

Grouping is Python bookkeeping over deferred faces and `classify_counted`
applies the settings per polygon; a kernel that returns counts leaves both
where they are. So the denominator is rasterization 0.482 s plus `count_batch`
0.160 s, or **0.642 s** of the 2.258 s tier — 28.4%, not the 41.6% that
rasterization plus the whole classification phase would suggest.

That matters for the keep gate. Twenty percent of the tier is 0.452 s, so the
GPU path has to finish the replaced work in **0.190 s or less**, inclusive of
everything. The margin is real but it is not generous.

### The transfer floor is 1.6%, because the mask packs 24 to a float

`R32F` is the only exact upload channel and only below 2^24, which sounds like
a severe constraint for an 87 MB boolean mask and turns out to be the opposite:
`numpy.packbits` puts 24 mask texels in each float32 exactly, so the mask
crosses as 3.6 MB. Doubles cross as three 22-bit chunks of the IEEE pattern,
each below 2^24 and so exact, reassembled in the shader.

| Step | Seconds |
| --- | ---: |
| Pack masks, 24 bits per float32 | 0.0029 |
| Pack triangles, three 22-bit chunks | 0.0075 |
| Upload masks | 0.0015 |
| Upload triangles | 0.0033 |
| Read 524,288 uint32 counts | 0.0001 |
| **Floor, excluding all compute** | **0.0153** |

One float32 per mask texel instead of packing costs 0.0102 s and 87 MB, so the
packing is worth its 3 ms. `gpu.init()` costs 0.364 s but once per process, not
per analysis.

### GLSL fp64 is exact only with `precise`

The plan says an f32 rasterizer that merely agrees on ordinary assets fails, so
the spike compared bit patterns, not values, on the tier's 301,088 real
triangles. It computed the long slope and one cross-section — `low_x + (y -
low_y) * slope`, the expression the whole rasterizer is built on — in fp64 and
returned both IEEE halves through `R32UI`.

| Shader | Slope | Cross-section |
| --- | ---: | ---: |
| Unqualified | 0 of 297,460 differ | **14 differ**, worst 1.137e-13 |
| `precise` | 0 differ | 0 differ |

The failure is multiply-add contraction: the compiler fuses the multiply and
the add, which is more accurate and therefore wrong here, because the CPU does
not. Fourteen triangles in 297,460 is exactly the shape of bug that survives
casual testing and produces a handful of misclassified faces on a real asset.
`precise` on every declaration that feeds a comparison is mandatory, not
advisory.

### Modal round trips cost 2.9 ms, not seconds

`step()` hands out 4,096 polygons at a time, so a GPU path dispatches per chunk
and must read counts back before it can classify — 37 chunks on this tier, each
dispatching once per image and address mode pair. Every readback is a pipeline
stall and stalls do not shrink with the work, so this was the structural risk.

| Shape | Seconds |
| --- | ---: |
| 185 dispatches, no readback | 0.0000 |
| 37 × (1 dispatch + readback) | 0.0022 |
| 37 × (5 dispatches + readback) | 0.0029 |

The first row is submission only and is reported as such; it is the number the
plan forbids calling acceleration. The readback rows were checked rather than
trusted: 8,022 of 8,022 values in the last chunk match the CPU bit for bit, so
`GPUTexture.read()` does synchronize and those timings include completion. A
readback stall is about 0.06 ms.

### Position after the spikes

The candidate is alive. Of the 0.190 s the gate allows, the transfer floor takes
0.015 s and the modal round trips 0.003 s, leaving **0.172 s for the rasterizer
itself** to do what the CPU does in 0.642 s. Nothing measured so far kills it,
and nothing measured so far is a speed claim: no rasterizer has been written.
