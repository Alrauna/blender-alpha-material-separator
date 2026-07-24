# Public integration API

- API version: `1.2`
- Extension version: `0.1.0`

API 1.2 is additive over 1.1. Existing API 1.0/1.1 callers keep the same
operator IDs, existing arguments, scripted defaults, classifications, and
status behavior. The current build implements:

- `bpy.ops.alpha_material_separator.query_capabilities`
- `bpy.ops.alpha_material_separator.analyze`
- `bpy.ops.alpha_material_separator.select_faces`
- `bpy.ops.alpha_material_separator.assign_materials`
- `bpy.ops.alpha_material_separator.clear_results`

## Analysis and material-specific overrides

`analyze` accepts the optional `material_overrides_json="[]"` argument. It is a
JSON list whose entries have this form:

```json
{
  "material_name": "Body",
  "image_name": "BodyMask",
  "image_channel": "RED",
  "uv_map_name": "UVMap",
  "address_mode": "AUTO"
}
```

Each target material may appear once. Valid channels are `ALPHA`, `RED`,
`GREEN`, `BLUE`, and `LUMINANCE`; valid addressing values are `AUTO`, `REPEAT`,
`EXTEND`, `CLIP`, and `MIRROR`. An empty image name keeps automatic image
detection and may override only the UV or addressing. Materials absent from the
list remain automatic. Invalid, duplicate, or unused records are rejected
instead of ignored.

The selection-wide `image_name`, `image_channel`, and `uv_map_name` arguments
remain available for API 1.0 compatibility and are now considered legacy.
Combining a selection-wide image override with material-specific records is
rejected as `OVERRIDE_CONFLICT`. Combined or procedural alpha still must be
baked to an image; the extension never approximates arbitrary shader math.

## Status and report data

Machine-readable JSON strings are exposed through
`WindowManager.alpha_material_separator_api`:

- `capabilities_json`
- `last_status_code`
- `last_status_json`
- `report_json`
- `analysis_id`
- `validation_state`
- `pending_scopes_json`
- API and extension versions

API 1.1 reports add resolved image, UV, channel, addressing, source method,
per-material counts, unsupported reasons, suppressed-gate details, and planned
assignment actions. Existing report fields remain unchanged.

API 1.2 additionally exposes:

- Report validation state: `CLEAN`, `RECHECK_PENDING`, or confirmed `STALE`.
- Pending component scopes when Blender has emitted a relevant update hint.
- Unsupported reason scope: `FACE_LOCAL`, `MATERIAL_SOURCE`, or `DATA_SAFETY`.
- Per-material disposition and planned action, including material groups that
  will remain unchanged rather than veto independent safe groups.
- Capability flags for component revalidation and reason-scoped unsupported
  assignment.

`assign_materials.unsupported_policy` additively accepts `TO_ALPHA`. It routes
only face-local uncertainty inside an otherwise resolved material to the alpha
variant. It never turns a material-wide resolver failure into an alpha variant.
The operator's existing scripted default remains `CANCEL_SOURCE_MATERIAL`;
Simple UI explicitly supplies `TO_ALPHA`.

Dependency-graph events are hints. `dirty_reason` is populated only after a
component mismatch confirms a stale report. Selection and Object/Edit Mode
changes that leave component fingerprints equal retain the same analysis ID and
review token. Assignment synchronously drains any pending recheck before its
mutation boundary.

Callers must query capabilities, check the API major, and avoid unavailable
operations. Expected incompatibility is reported as `API_INCOMPATIBLE` rather
than an exception crossing the operator boundary. The UI's mandatory preview
review token intentionally does not change direct scripted assignment behavior:
scripts must still supply the reviewed `expected_analysis_id`, and assignment
performs its authoritative stale-input validation.

Future CATS integration must feature-detect the capability operator. If it is
absent or incompatible, integration is a harmless no-op. This extension never
imports, detects, or depends on CATS.
