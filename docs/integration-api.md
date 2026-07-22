# Public integration API

- API version: `1.0`
- Extension version: `0.1.0`

The current build implements:

- `bpy.ops.alpha_material_separator.query_capabilities`
- `bpy.ops.alpha_material_separator.analyze`
- `bpy.ops.alpha_material_separator.select_faces`
- `bpy.ops.alpha_material_separator.assign_materials`
- `bpy.ops.alpha_material_separator.clear_results`

Capability flags report the implemented operations. The analysis operator also
accepts `image_channel` (`ALPHA`, `RED`, `GREEN`, `BLUE`, or `LUMINANCE`) as an
optional backward-compatible argument in addition to the approved API fields.
Together with `image_name` and `uv_map_name`, this is the documented escape
hatch for packed masks and alpha sources the automatic resolver cannot trace.
Combined or procedural alpha must first be baked to an image; the extension
never silently approximates shader math.

Machine-readable JSON strings are exposed through
`WindowManager.alpha_material_separator_api`:

- `capabilities_json`
- `last_status_code`
- `last_status_json`
- API and extension versions

Callers must query capabilities, check the API major, and avoid unavailable
operations. Expected incompatibility is reported as `API_INCOMPATIBLE` rather
than an exception crossing the operator boundary.

Future CATS integration must feature-detect the capability operator. If it is
absent or incompatible, integration is a harmless no-op. This extension never
imports, detects, or depends on CATS.
