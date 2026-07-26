# Already-Separated Button Tooltips

## Goal

Explain why **Preview Faces to Move** and **Apply Material Separation** are
disabled after the selected meshes have already been separated successfully.

## Behavior

When the current assignment plan has no actionable changes because its material
groups are already recognized as AMS-derived, both disabled buttons show:

> All faces on the selected meshes are optimally assigned. No faces need to be moved.

The message is state-aware. It appears when the plan contains already-derived
AMS groups and has no actionable moves, including a partial-apply rerun where
other unresolved groups remain safely unchanged. It must not appear when
analysis inputs are stale, analysis is running, no report exists, a review is
still required, actionable moves remain, or a plan is purely blocked or
unresolved without any already-separated group.

All other tooltip text and all analysis, preview, assignment, operator, and API
behavior remain unchanged.

## Implementation

Reuse the existing Preview and Apply operators. Give each button an internal,
panel-provided tooltip value and let the operator return that value through
Blender's dynamic operator-description hook, falling back to its existing
description when no contextual value is supplied.

No new operator, panel, property group, persistent state, or public API field is
needed.

## Verification

Add a focused Blender regression proving:

- both buttons receive the exact message in the already-separated state;
- both operators retain their normal description without a contextual tooltip;
- actionable and purely unresolved disabled states do not receive the
  already-separated message.

Then run the ordinary unit and headless Blender suites.
