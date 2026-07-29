# Compact Apply Confirmation

## Goal

Replace the unbounded warning dialog shown after **Apply Material Separation**
with a short, entirely count-based confirmation. The dialog must tell the user
what the reviewed assignment plan will change, what exceptional content will
remain unchanged or be skipped, and how to undo it without repeating the
detailed Review and Material Details content.

## Context

The existing dialog repeats:

- every unresolved material name;
- every source-to-derived material destination;
- every object/material face count;
- broad analysis counts that do not necessarily describe the final assignment
  outcome;
- zero-valued skip categories; and
- four separate safety and undo statements.

On a large avatar this produces a screen-height list after the user has already
analyzed the meshes, reviewed the summary, expanded Material Details when
needed, and previewed the exact faces. The confirmation should validate the
consequences of that reviewed plan, not reproduce the review.

## Content boundary

The popup is entirely count-based. It contains no object, material, image, UV,
or destination names. Those details remain available in Review and Material
Details before the user clicks Apply.

The popup keeps only:

- total reviewed faces that will move to alpha materials;
- additional material slots that will be added;
- mixed faces actually moving to alpha;
- below-significance faces actually moving to alpha;
- face-local uncertain faces actually moving to alpha;
- reviewed faces retained on source materials by policy;
- unresolved material groups remaining unchanged;
- material groups and objects actually skipped;
- the no-topology/no-source-shader guarantee; and
- Blender Undo guidance.

It removes:

- the raw report-level `UNSUPPORTED` face count;
- material and object names;
- destination pairs;
- per-object and per-material face rows;
- individual skip/conflict explanations;
- zero-valued categories;
- the duplicate “Review warnings before material assignment” heading; and
- repeated creation, slot, topology, shader, and undo boilerplate.

The detailed panel remains the remedy location. The confirmation does not add
a disclosure, search, pagination, examples, or a link back to individual
materials.

## Layout and adaptive copy

Use Blender 5.2's native property dialog with:

- `width=420`;
- `title="Apply Material Separation"`; and
- `confirm_text="Apply"`.

The standard Cancel action remains available. No persistent UI state is added.

A representative dialog is:

```text
Apply Material Separation

Move 65,775 reviewed faces to alpha materials and add 29 material slots.

This includes 57,731 mixed faces and 2,577 uncertain faces.
23 unresolved material groups will remain unchanged.

Only material slots and face assignments change—no topology or source
shader changes. Ctrl+Z to undo.
```

Copy is generated from the exact plan:

1. The first sentence reports moved faces and added slots. If either count is
   zero, omit that clause rather than displaying zero.
2. Combine mixed and uncertain moved-face counts into one “This includes…”
   sentence when both are nonzero. Use a single-category sentence otherwise.
3. Report below-significance faces moving to alpha only when nonzero.
4. Report reviewed faces retained on source materials by policy only when
   nonzero.
5. Report unresolved material groups remaining unchanged only when nonzero.
6. Report skipped material groups and skipped objects in one sentence, omitting
   either zero-valued clause.
7. End with one compact safety and undo statement.

All nouns use correct singular/plural forms and all counts use thousands
separators. Sentences remain separate labels so the dialog is quickly scannable
without bullets. Long safety text may wrap to a second visual line, but the
number of semantic rows is bounded by the categories above and never by the
number of selected objects or materials.

## Authoritative count semantics

Every number describes an actual assignment-plan consequence. The dialog must
not infer actions from broad report totals.

The plan payload already exposes:

- `faces_to_reassign`;
- `planned_additional_slots`;
- `face_local_unsupported_to_alpha`;
- `retained_faces_by_policy`;
- `material_source_groups_left_unchanged`;
- `skipped_material_groups`; and
- `skipped_object_count`.

Add only the outcome counts not currently available:

- `mixed_faces_to_alpha`; and
- `suppressed_faces_to_alpha`.

These are accumulated while the assignment plan selects exact face indices.
They count only faces included in the mutation plan under the active policies.
A mixed or suppressed face in an unresolved, blocked, skipped, or retained
group must not appear as moving to alpha.

The additive fields do not change operator arguments, API major/minor,
classifications, policies, or existing payload fields. Version remains `0.1.0`
and public API remains `1.2`.

A pure presentation helper consumes the plan payload and returns the ordered
tuple of display sentences. The Blender operator only draws those sentences;
it does not reconstruct, recount, or interpret face outcomes.

## Interaction and safety

The existing confirmation trigger remains unchanged:

- a clean supported plan applies immediately after the mandatory Preview;
- plans involving mixed, suppressed, unsupported, skipped, blocked, conflict,
  or partial-success conditions open the confirmation;
- a plan with nothing safely actionable does not open the confirmation; and
- scripted operator behavior remains backward compatible.

Before opening the dialog, the operator stores the exact plan fingerprint.
When the user presses Apply, the existing synchronous validation and preflight
comparison run again. If mesh, material, image, policy, metadata, destination,
or exact face-plan state changed while the dialog was open, assignment cancels
with the existing safe status and performs no mutation.

Cancel performs no mutation. Successful assignment remains one atomic undoable
operation. No topology, source shader, source material, image, UV, rigging, or
unselected-object behavior changes.

## Test-first acceptance

Generated unit tests must fail before production changes and cover:

- the exact representative copy;
- singular and plural forms;
- thousands separators;
- omission of every zero-valued category;
- moved faces with zero added slots when an existing slot is reused;
- mixed-only, uncertain-only, and combined mixed/uncertain sentences;
- suppressed-to-alpha and retained-by-policy sentences;
- unresolved, skipped-material, and skipped-object combinations;
- a bounded maximum semantic-row count for plans containing many objects and
  materials; and
- absence of object, material, image, UV, and destination names.

Generated Blender tests must cover:

- exact mixed and suppressed plan-outcome counts;
- report totals containing faces that are blocked or unchanged without
  inflating the moved counts;
- a clean plan bypassing the dialog;
- a warning plan opening the dialog;
- the native title, Apply confirmation text, and requested width contract;
- confirmation cancellation with zero mutation;
- preflight changes while the dialog is open blocking assignment;
- Preview and Apply using the same exact plan;
- partial success;
- undo/redo;
- idempotent reruns; and
- registration/unregistration.

The complete unit, headless Blender, source validation, build, and archive
validation gates remain required.

The ignored private before/after smoke must analyze all eligible meshes and
assert only anonymized aggregate facts:

- the summary contains no private names;
- its semantic-row count stays within the fixed category bound despite the
  large object/material selection;
- displayed moved/unchanged/skipped counts match the exact plan; and
- neither private file is saved or modified.

Manual installed-ZIP acceptance must inspect the popup at narrow and wide
layouts and at 100% and 150% Blender UI scale. It must confirm readable copy,
visible Apply/Cancel controls, no unnecessary scrolling for the representative
large plan, cancellation without mutation, successful Apply, and Ctrl+Z Undo.

## Non-goals

- No change to analysis, rasterization, material resolution, classification, or
  assignment policy.
- No material or object names in the confirmation.
- No expandable details or per-material remediation inside the confirmation.
- No change to the Review panel or Material Details disclosure.
- No new persistent properties, preferences, operators, dependencies, or
  network behavior.
- No topology changes, shader rewriting, Unity automation, or CATS integration.
