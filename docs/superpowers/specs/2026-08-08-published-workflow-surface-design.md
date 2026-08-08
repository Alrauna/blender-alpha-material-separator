# Published workflow surface design

Date: 2026-08-08
Status: approved, not implemented
Branch: `fix/stale-analysis-privacy`
API impact: 1.2 → 1.3, additive

## Problem

`Alrauna/Cats-Blender-Plugin` drives this extension as an external dependency.
It never imports extension code; it reads published operator IDs and the
`WindowManager.alpha_material_separator_api` RNA group. Its Overdraw Prevention
panel must decide when to offer Analyze, Preview, and Apply.

The published surface cannot express that decision. The extension computes it in
`workflow_view()` and discards the result after drawing. A consumer therefore
guesses, and every guess drifts from the extension it is mirroring.

## Investigation

Read against `e696c4e`. Six gaps were reported; four are defects, one is correct
behavior with an incorrect comment, and one is a misreading. A seventh defect
was found during investigation.

### Confirmed defects

**The assignment plan is unreachable before assignment.** `actionable` is
`bool(self.mutations or self.metadata_refreshes)` in
`AssignmentPlan.actionable`, and `presentation.workflow_view()` gates both
`can_preview` and `can_apply` on it. The plan payload that would let a consumer
derive it reaches the public surface only from `assign_materials`:

| Publication point | carries plan payload |
| --- | --- |
| `analyze` → `ANALYSIS_COMPLETE` | no; `report=payload` only |
| `select_faces` → `PREVIEW_COMPLETE` | no |
| `assign_materials` → every code | yes |

`actionable` is in fact derivable from `AssignmentPlan.public_payload()` —
mutations are appended only with non-empty face tuples, so it equals
`bool(faces_to_reassign or metadata_refreshes)` — but that payload becomes
visible only after the consumer has already committed to applying. A report with
nothing to separate leaves a consumer offering Preview and Apply where the
extension correctly disables them.

**The review signature is unreachable.** The reported gap was that `reviewed`
and `running` live on the private UI property group. `running` is a genuine but
minor omission. `reviewed` is not a term in `can_apply`
(`has_report and actionable and not running and not stale`); it selects the
`REVIEWED` state name, the "Preview is optional" hint, and the
"Faces have not been previewed." confirmation line.

The consequential hole is `expected_review_signature`, a blake2b over
`(analysis_id, four policies, plan_payload)` in `presentation.review_signature`.
A consumer cannot compute it, so it passes an empty string, and
`assign_materials.invoke` reads
`previewed = not self.expected_review_signature or ...`. An empty signature
therefore means *previewed*, and the consumer's Apply silently loses both the
not-previewed warning and `REVIEW_CHANGED` protection. This is a correctness
divergence, not a cosmetic one.

**`RESULT_STALE` has no guidance entry.** `presentation._GUIDANCE` has
`STALE_ANALYSIS` but not `RESULT_STALE`, so `guidance_for("RESULT_STALE")`
returns the unknown-code default. This is invisible today only because
`_draw_status_problem` lists the code in its `normal` set and returns early.

**Severity is private and closed-world.** `_draw_status_problem`'s `normal` set
is a severity table. Consumers reimplement it by hand. The consumer currently
carries `frozenset({"RESULT_STALE", "STALE_ANALYSIS"})` and already diverges:
the extension treats `RESULT_STALE` as normal and `STALE_ANALYSIS` as an error.
`docs/HANDOFF.md` records the maintenance trap — a new status code must be added
to the `normal` set or to `_GUIDANCE`, and nothing couples the two.

### Correct behavior, incorrect comment

**`RECHECK_PENDING` publishes no status, and should not.** The publish guard in
`runtime._sync_public_validation_state` is `_VALIDATION_STATE == VALIDATION_STALE`.
That is right: the extension's own panel gates on
`stale = bool(runtime.dirty_reason())`, which is confirmed-stale only, so it
ignores `RECHECK_PENDING` too, and `adapters/analysis.py` reuses the cached
analysis when it can prove that is safe. Widening the guard would hide buttons
on harmless selection and mode changes. `docs/integration-api.md` already states
"`RECHECK_PENDING` is not stale" correctly.

Only the comment in `runtime._sync_public_validation_state` overclaims. "A
consumer must never have to read validation_state to discover that
ANALYSIS_COMPLETE is false" is true of stale transitions and false as a blanket
statement. Correct the comment; keep the guard.

### Deliberate design

**The status channel and the panel deliberately differ on staleness.**
`RESULT_STALE` sits in the `normal` set so the panel renders nothing for it,
because the Review box already renders "Inputs Changed — Analyze Again" from
`runtime.dirty_reason()`. `docs/HANDOFF.md` records that including the code
drew "This input needs review" directly above the correct copy. The panel copy
is the user-facing authority; the status `message` is machine-facing. The only
real fault on this path is the missing `_GUIDANCE` entry above.

### Misreading

**Release detection already works.** `extension_version` is published both as
`capability_payload()["extension_version"]` and as `state.extension_version`,
written by `query_capabilities`, derived from `blender_manifest.toml`. The field
predates 1.1.0. A consumer can enforce a 1.2.0 minimum today by running
`query_capabilities` and comparing version tuples. What is missing is a
documented minor-bump policy and a worked example, not a field.

### Found during investigation, out of scope

`report_json`'s `default_planned_action` is stale relative to shipped defaults.
`AnalysisReport.public_payload` returns `SKIP_GROUP` for any group holding
`SUPPRESSED` faces, but the shipped `suppressed_policy` has been `KEEP_SOURCE`
since 1.1.0, which produces `PARTIAL_MOVE_KEEP_POLICY`. It is the only
plan-shaped data a consumer receives after analyze, and it misreports. This
needs its own reproduction and branch.

## Design

### Architecture

A new `addon/workflow.py` holds one public function, `snapshot(context) -> dict`.
It contains the computation that currently lives inline in `panel.draw()`:
eligible objects, `runtime.report`, the assignment plan, `review_matches`,
`already_separated_tooltip`, and `workflow_view`.

Two callers share it, so the drawn state and the published state cannot drift:

- `panel.draw()` calls it and draws from the result. `_plan` and
  `_policy_signature` remain in `panel.py`; the Expert policy panel still uses
  `_plan` independently.
- `ALPHA_MATERIAL_SEPARATOR_PG_api_state.workflow_json`, a read-only
  `StringProperty(get=...)`, serializes it. The getter imports `workflow` lazily
  inside the function body, matching the existing `_settings_changed` pattern in
  `properties.py` and avoiding an import cycle through `adapters.assignment`.

A pull-based getter is required rather than a value refreshed at status
transitions. Two of the inputs — selected objects and the four policy enums —
change with no extension operator running, which is exactly when
`can_preview` and `can_apply` flip. A pushed value would be stale precisely when
it matters. `report_json` is rejected as the home for the same reason, and
because workflow gating is not analysis data.

The getter must be total. Any exception returns the degraded snapshot —
`stale: true`, every `can_*` false — mirroring the existing `except` in
`panel.draw()` that already sets `stale = True` when `_plan` raises. A `get=`
callback that raises during draw would break the panel that reads it.

No memoization in the first implementation. The panel already builds a plan per
redraw; a consumer read makes it two. A `ponytail:` comment records the upgrade
path — a module-level snapshot memo keyed on
`(analysis_id, hint generation, policies, selection)` — gated on the measured
redraw benchmark in the testing section rather than on assumption.

### Published payload

`workflow_json` on the api state group, named for consistency with
`capabilities_json`, `report_json`, and `pending_scopes_json`:

```json
{
  "api_version": "1.3",
  "state": "READY_TO_REVIEW",
  "can_analyze": true,
  "can_preview": true,
  "can_apply": true,
  "running": false,
  "stale": false,
  "reviewed": false,
  "actionable": true,
  "already_separated": false,
  "eligible_object_count": 2,
  "analysis_id": "…",
  "validation_state": "CLEAN",
  "expected_review_signature": "…"
}
```

`state` is one of the eight values `workflow_view` produces: `RUNNING`,
`STALE`, `COMPLETED`, `NO_CHANGE`, `REVIEWED`, `READY_TO_REVIEW`,
`READY_TO_ANALYZE`, `IDLE`.

Three fields earn their place beyond the raw gating booleans.
`already_separated` lets a consumer say "no change needed" rather than only
greying buttons. `eligible_object_count` disambiguates the two causes of
`can_analyze: false`. `expected_review_signature` is passed unchanged to
`assign_materials`, which gives a consumer's Apply identical `REVIEW_CHANGED`
and not-previewed behavior.

`stale` is published alongside `validation_state` deliberately. It is the
confirmed-stale boolean the panel gates on, so a consumer never has to decide
for itself whether `RECHECK_PENDING` counts.

### Status severity

`api_contract.STATUS_SEVERITIES` lists only the non-error codes. Unknown codes
default to `ERROR`, reproducing the current closed-world behavior of the
`normal` set exactly.

- `OK` — `NOT_QUERIED`, `OK`, `ANALYSIS_COMPLETE`, `PREVIEW_COMPLETE`,
  `ASSIGNMENT_COMPLETE`, `ASSIGNMENT_NO_CHANGES`, `CLEARED`
- `INFO` — `ASSIGNMENT_COMPLETE_WITH_SKIPS`, `RESULT_STALE`
- `ERROR` — everything else

`status_payload()` gains a `"severity"` key. `_draw_status_problem` drops its
private set for `if severity_for(code) in {"OK", "INFO"}: return`, which is
byte-identical to today's rendering for every existing code. `WARNING` is
deliberately omitted; no current code needs a fourth level.

Two coupled corrections ride here. `RESULT_STALE` gains a `_GUIDANCE` entry
reusing the panel's own "Inputs Changed — Analyze Again" wording, so the
code-to-copy table has no hole. A unit test asserts that every key in
`STATUS_SEVERITIES` returns real guidance rather than the unknown-code default,
which is the coupling `docs/HANDOFF.md` records as absent.

### Versioning

`API_VERSION` becomes `(1, 3)`.

`docs/integration-api.md` states the policy: the API minor bumps whenever the
published surface gains a field, property, status code, or operator;
`extension_version` distinguishes builds within a minor. The document also
records plainly that under this policy 1.2.0's `RESULT_STALE` should have bumped
the minor and did not. That omission is the cause of the reported
version-detection difficulty, and `extension_version` is the remedy for builds
already released.

### Compatibility

Nothing in this design is breaking.

- `workflow_json` is a new property; existing readers are unaffected.
- `severity` is a new key in `last_status_json`; `api_contract.dumps` already
  sorts keys, so the serialization convention is unchanged.
- No existing field changes meaning or type.
- Panel rendering is unchanged for every existing status code.

The only consumer this could disturb is one comparing `last_status_json` by
exact string equality, which the document does not sanction.

## Scope

One branch, two commits: the workflow surface, then status severity. The
objective states in one sentence — make the published API sufficient for an
external panel to mirror the extension's workflow — and both halves share the
1.3 bump and one documentation file. Splitting them would force a contrived
1.3/1.4 ladder over the same `API_VERSION` line. The `runtime` comment
correction rides along as part of the first commit.

Explicitly excluded, each requiring its own branch:

- `default_planned_action` staleness in `report_json`.
- Manual alpha source usability, already recorded in `docs/HANDOFF.md` as the
  unstarted 1.1.1 objective with a diagnosed dead-end flow and candidate fixes.
- The two missing PEP 8 blank lines in `runtime.py`.

## Testing

Layers from the repository test pyramid that apply:

1. **Pure Python.** Snapshot shape, key set, and JSON stability. The severity
   table and its default. The guidance-coupling assertion. `workflow_view`
   itself already has coverage in `tests/unit/test_presentation.py`.
2. **Headless Blender.** Read `workflow_json` after analyze, after a mesh edit,
   while `RECHECK_PENDING`, after Preview, and while an analysis runs; assert it
   equals what the panel computes from the same snapshot. Include a permanent
   regression that `RECHECK_PENDING` keeps `can_preview` and `can_apply` true,
   so the publish guard cannot later be widened without failing a test.
3. **Equivalence.** The snapshot's `expected_review_signature`, passed to
   `assign_materials`, produces no `REVIEW_CHANGED`, matching a panel-driven
   Apply.
4. **Preservation.** Repeated `workflow_json` reads leave `runtime.snapshot()`
   identical, with zero rasterization and zero participating-image digest work.
   This is the assertion that catches an accidental validation side effect
   inside the getter.
5. **Performance.** Redraw-path plan builds measured before and after in one
   session on one machine, blocking an unexplained regression over 25 percent.

Installed-ZIP interactive acceptance is user-performed and cannot be driven by
an agent. It remains pending, and the specific unconfirmed interaction is a
consumer panel gating correctly against an installed build.

## Open questions

None. The three design decisions — pull-based getter, gating plus review
signature, severity on each status payload — were settled before this document
was written.
