# Optional Preview with Confirmation Design

**Status:** Proposed for user review
**Date:** 2026-07-29

## Goal

Allow users to apply a valid, actionable material-separation plan immediately
after analysis without first entering face-preview Edit Mode. Preserve Preview
as the recommended visual inspection tool, and require an explicit confirmation
whenever the current exact assignment plan has not been previewed.

## Current behavior and cause

The panel enables **Apply Material Separation** only when
`workflow_view(...).can_apply` receives `reviewed=True`. A matching review token
is created only by an exact assignment-plan preview using **Preview Faces to
Move**.

This is a guided-UI policy rather than a mutation-safety requirement. Apply
already performs authoritative report validation, rebuilds the assignment plan,
compares the expected plan signature, checks confirmation preflight stability,
and executes the mutation transactionally.

## Approved behavior

### Button availability

After a successful analysis:

- Enable **Apply Material Separation** whenever the report is current and the
  assignment plan is actionable.
- Do not require a matching preview token merely to enable the button.
- Keep Preview and Apply disabled while analysis is running, when the report is
  known stale, or when no safe action exists.
- Keep **Preview Faces to Move** available as before.

### Confirmation rules

Use the existing **Apply Material Separation** confirmation dialog.

- If the current exact assignment plan has not been previewed, always open the
  dialog before mutation.
- Add the sentence: **Faces have not been previewed.**
- Retain the existing aggregate plan summary, no-topology-change statement, and
  undo guidance.
- If the plan was previewed, preserve the current behavior:
  - clean supported plans apply immediately;
  - mixed, suppressed, unsupported, skipped, blocked, conflicting, or partial
    plans still open the warning dialog.
- Confirmation cancellation performs no mutation and retains the analysis.

An old token does not count. The preview must match the current analysis ID,
policies, exact face set, source/derived-material decisions, and complete
assignment-plan fingerprint.

### State transitions

- Analysis succeeds with an actionable plan:
  - Preview enabled.
  - Apply enabled.
  - The Apply section says that Preview is optional and allows inspection before
    assignment.
- Exact Preview succeeds:
  - Record the existing matching review token.
  - Apply may proceed under the existing warning-only confirmation rules.
- Policy or assignment-only preflight changes:
  - Clear or invalidate the matching review token.
  - Keep a still-valid analysis and actionable Apply button.
  - Applying now requires confirmation because the revised plan was not
    previewed.
- Classification-authority changes:
  - Mark the report stale as before.
  - Disable both Preview and Apply until reanalysis.
- Selection or Object/Edit Mode changes with unchanged authoritative inputs:
  - Retain the analysis and any matching review token.

### Safety and compatibility

Apply continues to:

- switch temporarily to Object Mode when required;
- validate the expected analysis ID;
- authoritatively validate current mesh, UV, material, image, and settings
  inputs;
- rebuild the assignment plan;
- compare the panel-provided expected plan signature;
- verify that warning-dialog preflight did not change while open;
- perform one undoable transactional mutation.

Direct scripted operator behavior remains compatible:

- `execute()` does not require a UI preview token.
- Existing scripted arguments and API version `1.2` remain unchanged.
- A scripted `invoke()` that does not provide the guided UI's expected review
  signature retains the current confirmation rules.

No new public operator, preference, RNA setting, dialog type, or persistent
state is added.

## Minimal implementation shape

1. Change `workflow_view().can_apply` so review is not part of button
   availability.
2. In the panel, replace the mandatory-preview instruction with concise
   optional-preview guidance.
3. When the guided UI invokes Apply, use the existing expected review signature
   and `runtime.review_matches()` result to decide whether confirmation is
   mandatory.
4. Extend the existing confirmation-line builder with the unpreviewed sentence;
   do not create a second confirmation presentation path.
5. Preserve the existing plan-signature, stale-report, and transactional
   assignment code.

## Test-first verification

Add failing generated tests before production edits.

### Pure-Python presentation tests

- An actionable, current, unpreviewed report enables both Preview and Apply.
- Running, stale, and non-actionable states still disable Apply.
- The unpreviewed confirmation contains exactly one
  **Faces have not been previewed.** sentence.
- Existing compact confirmation output remains unchanged for a reviewed plan.

### Headless Blender tests

- An unpreviewed clean plan opens confirmation instead of mutating immediately.
- Canceling that dialog produces zero changes to faces, slots, materials, and
  metadata.
- Confirming the same unpreviewed plan performs the intended assignment.
- A matching exact Preview permits a clean plan to apply immediately.
- Existing warning conditions still open the dialog after Preview.
- A policy or assignment-preflight change invalidates review but leaves Apply
  enabled and forces confirmation.
- A stale classification input disables Apply and blocks mutation.
- Preview/plan, confirmation/plan, and executed face sets remain identical.
- Direct scripted `execute()` remains compatible without a preview token.

Run the unit suite, complete headless Blender suite, source validation, package
build/validation, and installed-ZIP interaction. The private default example is
required because this changes preview and assignment workflow behavior.

## Documentation changes

Update the README and testing documentation so they state:

- Preview is recommended but optional.
- Apply without Preview always asks for confirmation.
- Previewing the exact current plan can allow a clean plan to apply immediately.
- Any stale classification input still requires reanalysis.
- Assignment-only plan changes require confirmation, not another full analysis.

## Non-goals

- No automatic face preview hidden inside Apply.
- No user preference controlling the requirement.
- No removal of Preview, review tokens, or plan fingerprints.
- No change to classification, rasterization, material resolution, assignment
  policies, or mutation scope.
- No topology or shader changes.
