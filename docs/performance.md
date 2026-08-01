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
  is at most 384 MiB. Larger images and unavailable native reads retain the
  complete-row chunked path. Both paths produce the same participating-channel
  digest and threshold grid.
- Full authoritative hashing remains the dominant 8K cost and remains mandatory
  when Blender cannot prove that pixels are unchanged.
- Coverage reuse is valuable for small, typical, and large/tiled inputs. It is
  not currently a speedup for the high tier because full validation still
  hashes all images and the very large coverage cache has material lookup and
  retention overhead. This is a recorded optimization target, not a hidden
  failure or a reason to weaken correctness.
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
