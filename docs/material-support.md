# Version 0.1 material-support matrix

Status: **approved and implemented for version 0.1**.

## Status meanings

- **Guaranteed**: required for version 0.1 regardless of private survey inputs.
- **Supported**: approved deterministic resolver behavior.
- **Deferred**: remain unsupported in version 0.1 unless separately approved.
- **Unsupported**: intentionally rejected rather than guessed.

## Alpha-source resolution

| Pattern | Status | Version 0.1 behavior |
| --- | --- | --- |
| Image Texture Alpha directly connected to active Principled Alpha | Guaranteed | Resolve that exact image. Other image nodes do not make it ambiguous because the alpha link is authoritative. |
| Explicit image and UV-map overrides | Guaranteed | Use the selected raw UV layer and image; do not infer or evaluate the shader graph. |
| Separate mask texture whose **Alpha** output is directly connected to active Principled Alpha | Guaranteed | Same direct-alpha rule as above. |
| Simple reroute between Image Alpha and active Principled Alpha | Supported | Trace only pass-through reroutes; reject cycles, branching, muted ambiguity, or non-reroute processing. |
| One Image Texture Color path directly or simply rerouted to active Principled Base Color while Principled Alpha is unlinked | Supported | Use that Base Color image's decoded stored A channel, regardless of Blender transparency settings. Normal, roughness, emission, and disconnected image nodes do not compete with this authority path. |
| Other color image contains alpha but is not the supported active Base Color authority | Deferred | An unconnected or ancillary image does not prove intent. Use an explicit override. |
| Separate mask **Color** output connected to Principled Alpha | Manual path | Select that image and the intended red, green, blue, alpha, or luminance channel through the override controls. |
| Image alphas multiplied or otherwise combined | Manual path | Bake the intended result to an image, then select the baked image/channel/UV override. The extension does not guess shader math. |
| Alpha source inside a node group | Deferred | Group interfaces, nested graphs, cycles, defaults, and library data require separate characterization. |
| Multiple images without a supported direct Alpha or Base Color authority path | Unsupported | Report `NO_AUTHORITATIVE_ALPHA_IMAGE`; never select an image by node order or name. |
| Procedural, animated, arbitrary shader evaluation | Unsupported | Report a stable unsupported reason. |

## UV/vector resolution

| Pattern | Status | Version 0.1 behavior |
| --- | --- | --- |
| Explicit UV-map override | Guaranteed | Use the named per-loop UV map exactly. |
| Image vector unlinked, using active render UV | Supported | Resolve the active-render layer, require it to exist, and include active/render selection in cache signatures. |
| Direct UV Map node to Image Vector | Supported | Use the named UV layer; missing/blank names are unsupported. |
| Direct Texture Coordinate UV to Image Vector | Supported | Use the active-render UV layer. |
| Mapping node between UV and Image Vector | Deferred | Do not ignore translation, rotation, scale, vector type, or animated values. |
| Generated/Object/Normal/Reflection coordinates | Unsupported | The version 0.1 polygon UV rasterizer cannot reproduce them. |
| Non-FLAT Image Texture projection | Unsupported | Report `UNSUPPORTED_PROJECTION`. |

## Addressing and images

| Input | Status | Version 0.1 behavior |
| --- | --- | --- |
| Repeat, Extend, Clip, Mirror | Guaranteed | Honor the resolved node mode; explicit image override defaults to Repeat unless overridden. |
| Static FILE, packed, GENERATED image | Guaranteed baseline adapter scope | Read current in-memory pixels in bounded complete-row chunks; malformed/unreadable images are unsupported. |
| TILED/UDIM, movie, sequence, viewer/render result | Deferred | No arbitrary tile/frame/source selection in version 0.1. |

## Decision record

The four proposed deterministic patterns were approved on 2026-07-22. The
supplied private example then established the narrow, unique Base Color
authority fallback as expected default behavior. The stable source code
`UNIQUE_BASE_COLOR_IMAGE_ALPHA` means one supported Base Color authority path,
not one Image Texture node in the entire material. User direction also established
per-material image, UV, channel, and addressing records as the non-seamless
escape hatch for separate masks and more substantial Blender workflows.
Materials without a record continue to use automatic detection, so a manual
source for one material cannot accidentally replace sources for the rest of the
selection. An explicitly connected but unsupported Principled Alpha path is
reported instead of silently ignored; a manual image/channel record can still
select the Base Color image's A channel. Mix, Math, Mapping, groups, arbitrary
combined masks, and Base Color paths without one supported image terminal remain
unsupported rather than guessed.
