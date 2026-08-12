# Coverage algorithm contract

The material-support checkpoint is approved and the pure-Python implementation
follows this contract.

For each original polygon, Blender's loop triangulation supplies UV triangles
without modifying topology. The pure core:

1. Convert `(u, v)` to texel-edge coordinates `(u * width, v * height)`.
2. Intersect each triangle with unit-height scanline strips, taking the
   horizontal cross-sections at the strip boundaries and the middle vertex.
3. Emit every integer texel-column run with positive-area intersection.
4. Union runs across the polygon's triangles.
5. Apply optional Chebyshev texel margin.
6. Apply Repeat, Extend, Clip, or Mirror addressing to virtual cells.
7. Count below-threshold cells through image row prefixes.
8. Classify as opaque, alpha-affected, mixed, suppressed, or unsupported.

Edge/corner-only contact does not count. Individual degenerate triangles may be
skipped with a warning; an all-degenerate polygon is unsupported. Budget
failures are unsupported and never trigger sparse sampling.

The optional Chebyshev margin dilates the unioned coverage by the configured
number of texels in every direction. It exists so that alpha texels just outside
the exact UV footprint still count, which matches the bilinear filtering and
mipmap bleed that occur at render time. A margin also raises the covered texel
count with texels that usually fall outside the shape and are usually opaque, so
it lowers the affected fraction and can reclassify a fully alpha-affected face
as mixed.

A face is suppressed when its affected texel count or affected fraction falls
below the configured minimum. The comparison is strict, so a face whose evidence
equals the minimum is not suppressed. A suppressed face stays on its source
material by default and does not prevent its siblings from being assigned.

The optimized interval output is compared with a slow positive-area
triangle/cell clipping oracle over fixed-seed randomized cases.
