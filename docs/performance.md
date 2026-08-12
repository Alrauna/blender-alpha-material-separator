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
