# Coverage algorithm contract

The material-support checkpoint is approved and the pure-Python implementation
follows this contract.

For each original polygon, Blender's loop triangulation supplies UV triangles
without modifying topology. The pure core:

1. Convert `(u, v)` to texel-edge coordinates `(u * width, v * height)`.
2. Clip each triangle against unit-height scanline strips.
3. Emit every integer texel-column run with positive-area intersection.
4. Union runs across the polygon's triangles.
5. Apply optional Chebyshev texel margin.
6. Apply Repeat, Extend, Clip, or Mirror addressing to virtual cells.
7. Count below-threshold cells through image row prefixes.
8. Classify as opaque, alpha-affected, mixed, suppressed, or unsupported.

Edge/corner-only contact does not count. Individual degenerate triangles may be
skipped with a warning; an all-degenerate polygon is unsupported. Budget
failures are unsupported and never trigger sparse sampling.

The optimized interval output is compared with a slow positive-area
triangle/cell clipping oracle over fixed-seed randomized cases.
