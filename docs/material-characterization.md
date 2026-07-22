# Material graph characterization

## Checkpoint result

- Date: 2026-07-22
- Blender: 5.2.0 LTS
- Private reference files initially available: 0
- Later private before/after pairs inspected: 1

No `.blend` references were present at the initial checkpoint, so it completed
without waiting for or downloading inputs. A later lawful private before/after
pair was inspected after approval. No identifying names, paths, assets, graph
dumps, or raw results are retained here, and no prevalence claim is made from a
single pair.

The guaranteed version 0.1 boundary remains:

- Direct Image Texture **Alpha** output to the Alpha input of the Principled
  BSDF directly connected to the active Material Output.
- Explicit image and UV-map overrides.
- Repeat, Extend, Clip, and Mirror addressing.

Approved and deferred patterns are recorded in
[`material-support.md`](material-support.md).

The anonymous pair confirmed an unchanged mesh, topology, UV set, rigging data,
and modifier structure; its expected result added one graph-equivalent material
section and reassigned only affected source faces. It also demonstrated a unique
base-color image whose stored alpha was not connected to Blender's shader Alpha
input, motivating the approved narrow fallback. The committed algorithm remains
the exact positive-area rasterizer, so the manually authored face set is treated
as a directional workflow reference rather than an exact golden oracle.

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

- The checkpoint has no representative real-world sample population.
- A graph being synthetically traceable does not demonstrate that it is common.
- Structural presence does not prove intended shader semantics.
- Unsupported material graphs remain explicit rather than guessed.
