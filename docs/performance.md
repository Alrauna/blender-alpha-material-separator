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

- Full authoritative hashing is the dominant 8K cost and remains mandatory
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
