# Version 0.1 material-support matrix

Status: **approved and implemented for version 0.1**.

## Status meanings

- **Guaranteed**: required for version 0.1 regardless of private survey inputs.
- **Supported**: approved deterministic resolver behavior.
- **Deferred**: remain unsupported in version 0.1 unless separately approved.
- **Unsupported**: intentionally rejected rather than guessed.

## Alpha-source resolution

| Pattern | Status | Planned behavior |
| --- | --- | --- |
| Image Texture Alpha directly connected to active Principled Alpha | Guaranteed | Resolve that exact image. Other image nodes do not make it ambiguous because the alpha link is authoritative. |
| Explicit image and UV-map overrides | Guaranteed | Use the selected raw UV layer and image; do not infer or evaluate the shader graph. |
| Separate mask texture whose **Alpha** output is directly connected to active Principled Alpha | Guaranteed | Same direct-alpha rule as above. |
| Simple reroute between Image Alpha and active Principled Alpha | Supported | Trace only pass-through reroutes; reject cycles, branching, muted ambiguity, or non-reroute processing. |
| Exactly one Image Texture feeds active Principled Base Color, with no competing alpha/image path | Supported | Use that image's stored alpha. This low-touch fallback is the pattern in the supplied anonymous before/after reference. |
| Other color image contains alpha but its Alpha output is not connected | Deferred | Multiple or unconnected images do not prove intent. Use an explicit override. |
| Separate mask **Color** output connected to Principled Alpha | Manual path | Select that image and the intended red, green, blue, alpha, or luminance channel through the override controls. |
| Image alphas multiplied or otherwise combined | Manual path | Bake the intended result to an image, then select the baked image/channel/UV override. The extension does not guess shader math. |
| Alpha source inside a node group | Deferred | Group interfaces, nested graphs, cycles, defaults, and library data require separate characterization. |
| Multiple images without one authoritative direct alpha path | Unsupported | Report `AMBIGUOUS_IMAGE`; never select an image by node order or name. |
| Procedural, animated, arbitrary shader evaluation | Unsupported | Report a stable unsupported reason. |

## UV/vector resolution

| Pattern | Status | Planned behavior |
| --- | --- | --- |
| Explicit UV-map override | Guaranteed | Use the named per-loop UV map exactly. |
| Image vector unlinked, using active render UV | Supported | Resolve the active-render layer, require it to exist, and include active/render selection in cache signatures. |
| Direct UV Map node to Image Vector | Supported | Use the named UV layer; missing/blank names are unsupported. |
| Direct Texture Coordinate UV to Image Vector | Supported | Use the active-render UV layer. |
| Mapping node between UV and Image Vector | Deferred | Do not ignore translation, rotation, scale, vector type, or animated values. |
| Generated/Object/Normal/Reflection coordinates | Unsupported | The version 0.1 polygon UV rasterizer cannot reproduce them. |
| Non-FLAT Image Texture projection | Unsupported | Report `UNSUPPORTED_PROJECTION`. |

## Addressing and images

| Input | Status | Planned behavior |
| --- | --- | --- |
| Repeat, Extend, Clip, Mirror | Guaranteed | Honor the resolved node mode; explicit image override defaults to Repeat unless overridden. |
| Static FILE, packed, GENERATED image | Guaranteed baseline adapter scope | Read current in-memory pixels in bounded complete-row chunks; malformed/unreadable images are unsupported. |
| TILED/UDIM, movie, sequence, viewer/render result | Deferred | No arbitrary tile/frame/source selection in version 0.1. |

## Decision record

The four proposed deterministic patterns were approved on 2026-07-22. The
supplied private example then established the narrow, unique base-color-image
fallback as expected default behavior. User direction also established explicit
image, UV, and channel selection as the non-seamless escape hatch for separate
masks and more substantial Blender workflows. Mapping nodes, groups, arbitrary
combined masks, and ambiguous multiple-image graphs remain unsupported rather
than guessed.
