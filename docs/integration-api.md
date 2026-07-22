# Public integration API

- API version: `1.0`
- Extension version: `0.1.0`

The checkpoint build currently implements:

- `bpy.ops.alpha_material_separator.query_capabilities`
- `bpy.ops.alpha_material_separator.clear_results`

Analysis, preview, and assignment operator IDs are reserved but their capability
flags remain `false` until those milestones pass.

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
