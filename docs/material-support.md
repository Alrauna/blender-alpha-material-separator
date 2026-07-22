# Version 0.1 material-support matrix

Status: **awaiting approval**. Analysis/resolver implementation must not proceed
beyond the guaranteed rows until this matrix is reviewed.

## Status meanings

- **Guaranteed**: required for version 0.1 regardless of private survey inputs.
- **Proposed**: deterministic and synthetically characterized; add only after
  this checkpoint is approved.
- **Deferred**: remain unsupported in version 0.1 unless separately approved.
- **Unsupported**: intentionally rejected rather than guessed.

## Alpha-source resolution

| Pattern | Status | Planned behavior |
| --- | --- | --- |
| Image Texture Alpha directly connected to active Principled Alpha | Guaranteed | Resolve that exact image. Other image nodes do not make it ambiguous because the alpha link is authoritative. |
| Explicit image and UV-map overrides | Guaranteed | Use the selected raw UV layer and image; do not infer or evaluate the shader graph. |
| Separate mask texture whose **Alpha** output is directly connected to active Principled Alpha | Guaranteed | Same direct-alpha rule as above. |
| Simple reroute between Image Alpha and active Principled Alpha | Proposed | Trace only pass-through reroutes; reject cycles, branching, muted ambiguity, or non-reroute processing. |
| Color image contains alpha but its Alpha output is not connected | Deferred | Image alpha presence alone does not prove that the material intends to use it. Use an explicit override. |
| Separate mask **Color** output connected to Principled Alpha | Deferred | Channel/luminance semantics require an explicit, tested rule. Use an override only when raw image alpha is the intended channel. |
| Image alphas multiplied or otherwise combined | Deferred | Multiple images, dimensions, transforms, and operations require a separate multi-source design. |
| Alpha source inside a node group | Deferred | Group interfaces, nested graphs, cycles, defaults, and library data require separate characterization. |
| Multiple images without one authoritative direct alpha path | Unsupported | Report `AMBIGUOUS_IMAGE`; never select an image by node order or name. |
| Procedural, animated, arbitrary shader evaluation | Unsupported | Report a stable unsupported reason. |

## UV/vector resolution

| Pattern | Status | Planned behavior |
| --- | --- | --- |
| Explicit UV-map override | Guaranteed | Use the named per-loop UV map exactly. |
| Image vector unlinked, using active render UV | Proposed | Resolve the active-render layer, require it to exist, and include active/render selection in cache signatures. |
| Direct UV Map node to Image Vector | Proposed | Use the named UV layer; missing/blank names are unsupported. |
| Direct Texture Coordinate UV to Image Vector | Proposed | Use the active-render UV layer. |
| Mapping node between UV and Image Vector | Deferred | Do not ignore translation, rotation, scale, vector type, or animated values. |
| Generated/Object/Normal/Reflection coordinates | Unsupported | The version 0.1 polygon UV rasterizer cannot reproduce them. |
| Non-FLAT Image Texture projection | Unsupported | Report `UNSUPPORTED_PROJECTION`. |

## Addressing and images

| Input | Status | Planned behavior |
| --- | --- | --- |
| Repeat, Extend, Clip, Mirror | Guaranteed | Honor the resolved node mode; explicit image override defaults to Repeat unless overridden. |
| Static FILE, packed, GENERATED image | Guaranteed baseline adapter scope | Read current in-memory pixels; malformed/unreadable images are unsupported. |
| TILED/UDIM, movie, sequence, viewer/render result | Deferred | No arbitrary tile/frame/source selection in version 0.1. |

## Approval question

The recommended version 0.1 matrix is:

1. Keep every **Guaranteed** row.
2. Approve the four synthetically deterministic additions:
   - active-render UV for an unlinked vector;
   - direct UV Map;
   - direct Texture Coordinate UV;
   - pass-through reroutes in the alpha path.
3. Keep Mapping nodes, node groups, color-channel masks, combined masks, and
   implicit alpha-bearing color images deferred.
4. Keep ambiguous multiple-image graphs explicitly unsupported.
