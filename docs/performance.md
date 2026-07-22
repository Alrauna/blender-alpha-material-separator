# Performance characterization plan

No absolute speed claim is made before implementation is measured.

## Tiers

- Small: about 5,000 polygons and one 1K image.
- Typical avatar: about 50,000 polygons and several 2K-4K images.
- High complexity: about 150,000 polygons, many materials, and an 8K image.
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

Full pixel digests remain authoritative when Blender invalidation is uncertain.
Cross-operation reuse is allowed only for mutation paths shown by Blender 5.2
tests to emit reliable invalidation. `Image.is_dirty` or file timestamps alone
are insufficient.

After the first baseline is approved, an unexplained same-machine time or peak
memory regression over 25% blocks release.
