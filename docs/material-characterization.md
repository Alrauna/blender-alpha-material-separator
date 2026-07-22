# Material graph characterization

## Checkpoint result

- Date: 2026-07-22
- Blender: 5.2.0 LTS
- Private reference files available: 0
- Private materials inspected: 0

No `.blend` references were present in `.local-references/`. The bounded survey
therefore completed without waiting for or downloading inputs. No claims about
real-world prevalence can be made from this checkpoint.

The guaranteed version 0.1 boundary remains:

- Direct Image Texture **Alpha** output to the Alpha input of the Principled
  BSDF directly connected to the active Material Output.
- Explicit image and UV-map overrides.
- Repeat, Extend, Clip, and Mirror addressing.

Additional patterns are proposed or deferred in
[`material-support.md`](material-support.md) and require approval before their
resolver behavior is frozen.

## Method

`scripts/characterize_materials.py` opens only `.blend` files already placed in
the ignored `.local-references/` directory. It produces one anonymous aggregate
under `.local-references/characterization/aggregate.json`.

The aggregate contains only:

- Number of files and materials inspected.
- Counts of materials exhibiting predefined structural features.
- A histogram of Image Texture node counts.

It intentionally omits file paths, datablock names, node labels, texture/image
data, per-material records, workflow guesses, and error paths. Nothing under
`.local-references/` is committed.

## Synthetic topology coverage

Synthetic, redistributable Blender graphs verify that the characterization code
recognizes the required graph families. These are structural tests, not
prevalence evidence.

| Synthetic graph family | Exercised |
| --- | --- |
| Direct Image Alpha to active Principled Alpha | Yes |
| Color image with alpha metadata | Yes |
| Separate base-color and mask images | Yes |
| Mapping node | Yes |
| Simple reroute | Yes |
| Node group presence | Yes |
| Multiplied image alphas | Yes |
| Ambiguous multiple images | Yes |
| Direct UV Map node | Yes |
| Direct Texture Coordinate UV | Yes |

The headless fixture creates ten generated materials and images entirely in
memory. Tests assert that the aggregate contains no synthetic names or path
fields.

## Limitations

- The checkpoint has no lawful real-world sample population.
- A graph being synthetically traceable does not demonstrate that it is common.
- Structural presence does not prove intended shader semantics.
- Material graph expansion beyond the guaranteed boundary remains blocked on
  explicit approval of the support matrix.
