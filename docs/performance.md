# Performance characterization

No arbitrary speed promise is made. This page records the first local baseline
and the repeatable method used to detect regressions.

## Tiers

- Small: about 5,000 polygons and one 1K image.
- Typical avatar: about 50,000 polygons, two 2K images, one 4K image, and ten
  materials.
- High complexity: about 150,000 polygons, two 4K images, one 8K image, and
  sixteen materials.
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
whole-workflow gate on its own, and it is the one with the worst exactness
story. The oracle is exact positive-area coverage of float64 UV triangles.
f32 has a 24-bit mantissa and cannot survive the adversarial suite, which
includes coordinates near 1e7 with sub-ulp spacing; GLSL exposes no 64-bit
integers through Blender's shader interface, so an exact formulation means
synthesizing 64-bit fixed point from paired 32-bit words with 128-bit
intermediates for the cross products.

### The rasterizer has an untaken numpy vectorization worth more than any GPU path

Before that work could be justified, the plan's own rule — take or explicitly
reject every remaining CPU improvement first — required pricing the obvious one.
Stage 3 rewrote `rasterize_polygon` in pure Python and deliberately did not
vectorize it. Computing the same height-sorted cross-sections for every triangle
at once, with `numpy.repeat` to expand triangles into their scanline rows,
measures as follows on 301,088 triangles shaped like the high tier's, 8.5 rows
each:

| Path | Seconds |
| --- | ---: |
| Shipped Python, projected from a 20,000-triangle sample | 4.588 |
| numpy, whole batch | 0.278 |

That is 16.5x, and the runs are **identical**, not merely equivalent: on 2,000
triangles at 4K scale producing 4,053,250 runs, and on 2,000 small triangles
producing 65,283 runs, the sorted run triples match the shipped rasterizer
exactly. The formulation is the same float64 arithmetic in the same order, so
this is expected rather than lucky, but it is measured rather than assumed.

Scaled to the benchmark's 4,469,760 rows that predicts about 0.49 s for a phase
now costing 5.597 s, a saving near 5.1 s, or roughly 45 percent of the whole
workflow — against a GPU rasterizer that would need 64-bit fixed-point emulation
to reach the same oracle and whose measured transfer costs are already the
dominant term.

The Stage 6 gate therefore does not proceed to a dataflow prototype on this
profile. The ranking is recomputed after the CPU vectorization lands, because
every share in the table above is a share of a workflow that is about to get
much smaller.
