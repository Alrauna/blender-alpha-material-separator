# Public integration API

- API version: `1.2`
- Extension version: see `version` in `addon/blender_manifest.toml`

API 1.2 is additive over 1.1. Existing API 1.0/1.1 callers keep the same
operator IDs, existing arguments, scripted defaults, and classifications.
One intentional status correction is documented below: an unresolved-only
selection is now a successful no-change result instead of a global assignment
failure. The current build implements:

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

Each `objects[].groups[]` record uses these concrete fields:

| Field | Values/meaning |
| --- | --- |
| `material` | Current Blender material name for diagnostics. |
| `supported` | Whether an authoritative alpha source was resolved. |
| `image`, `uv_map`, `channel`, `address_mode` | Resolved participating inputs. |
| `source_kind` | Stable resolver method code. |
| `source_method` | Compatibility alias of `source_kind`. |
| `counts` | Face counts keyed by the five public classifications. |
| `unsupported_reasons` | Internal reason-code counts. |
| `unsupported_scopes` | Counts keyed by `FACE_LOCAL`, `MATERIAL_SOURCE`, or `DATA_SAFETY`. |
| `default_disposition` | `SPLIT`, `LEAVE_UNCHANGED`, `REVIEW_REQUIRED`, or `NO_CHANGES`. |
| `default_planned_action` | Default Simple-mode group action. |

`UNIQUE_BASE_COLOR_IMAGE_ALPHA` means the resolver found one supported Image
Texture Color authority feeding active Principled Base Color while Principled
Alpha was unlinked. It does not mean the material contains only one Image
Texture node; ancillary image nodes are ignored for classification.

API 1.2 additionally exposes:

- Report validation state: `CLEAN`, `RECHECK_PENDING`, or confirmed `STALE`.
- Pending component scopes when Blender has emitted a relevant update hint.
- Unsupported reason scope: `FACE_LOCAL`, `MATERIAL_SOURCE`, or `DATA_SAFETY`.
- Per-material disposition and planned action, including material groups that
  will remain unchanged rather than veto independent safe groups.
- Capability flags for component revalidation and reason-scoped unsupported
  assignment.

Assignment preflight data contains `dispositions[]`. Each entry identifies the
`object`, `material`, `action`, `reason`, `total_faces`, `faces_to_alpha`,
`faces_left_source`, `face_local_unsupported`,
`material_source_unsupported`, `uncertain_to_alpha`, and
`retained_by_policy`. Current `action` values are:

- `MOVE_TO_ALPHA`
- `MOVE_UNCERTAIN_TO_ALPHA`
- `PARTIAL_MOVE_KEEP_POLICY`
- `LEAVE_UNCHANGED_NO_ALPHA_SOURCE`
- `LEAVE_UNCHANGED_BY_POLICY`
- `SKIP_GROUP`
- `NO_CHANGES_NEEDED`
- `ALREADY_SEPARATED`
- `REASSIGN_DERIVED_VARIANT`

Top-level preflight totals include `faces_to_reassign`,
`planned_additional_slots`, `skipped_object_count`,
`skipped_material_groups`, `unchanged_material_groups`,
`partial_material_groups`, and `retained_faces_by_policy`.

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
than an exception crossing the operator boundary. The UI uses the exact-plan
review token to decide whether confirmation is mandatory. It does not gate
direct scripted assignment: scripts still supply the expected analysis ID, and
assignment performs authoritative stale-input validation.

## Assignment return and status behavior

| Situation | Operator return | `last_status_code` |
| --- | --- | --- |
| Reviewed actionable groups changed | `FINISHED` | `ASSIGNMENT_COMPLETE` or `ASSIGNMENT_COMPLETE_WITH_SKIPS` |
| Everything is already separated | `FINISHED` | `ASSIGNMENT_NO_CHANGES` |
| Only material-wide unresolved groups exist | `FINISHED` | `ASSIGNMENT_NO_CHANGES`; those groups remain untouched |
| No actionable group and a safety/metadata policy blocks it | `CANCELLED` | `ASSIGNMENT_BLOCKED` |
| Report inputs changed | `CANCELLED` | `STALE_ANALYSIS` |
| Guided-UI plan changed after Preview | `CANCELLED` | `REVIEW_CHANGED` |
| Warning preflight changed while its dialog was open | `CANCELLED` | `PREFLIGHT_CHANGED` |
| Unexpected execution error | `CANCELLED` | `ASSIGNMENT_FAILED`; transactional rollback is attempted and failures are reported |

The unresolved-only `ASSIGNMENT_NO_CHANGES` result is the API 1.2 semantic
correction. API 1.0/1.1 integrations that treated any non-actionable unresolved
material as a hard error should use capability
`partial_material_assignment` and inspect the disposition totals.

Future CATS integration must feature-detect the capability operator. If it is
absent or incompatible, integration is a harmless no-op. This extension never
imports, detects, or depends on CATS.
