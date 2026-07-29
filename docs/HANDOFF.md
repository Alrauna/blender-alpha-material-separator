# Repository handoff

Updated: 2026-07-29

## Current objective

Finish the remaining isolated installed-ZIP visual matrix. Context-aware
wrapping for Blender's bottom-left Adjust Last Operation HUD is implemented,
tested, packaged, and confirmed at its normal width. Narrowing and widening the
native HUD could not be exercised because Blender did not respond to the
attempted resize interaction.

## Repository state

- Branch: `feat/alpha-material-separator-0.1`; configured upstream is `[gone]`.
- The completed simplification range is `4138236..3e5c0f2`, including cleanup
  commit `3b94172` and independent-review coverage commit `3e5c0f2`.
- Width-aware UI commits:
  - `ddef5fc docs: design width-aware UI wrapping`
  - `b9cca42 feat: add width-aware UI text wrapping`
  - `4029ce6 fix: adapt UI text to available width`
  - `5edc942 fix: wrap alpha source advisory heading`
- Context-aware HUD design commit:
  - `8f960d5 docs: design context-aware HUD wrapping`
- Context-aware HUD implementation commit:
  - `fa1d6c1 fix: wrap assignment summary for Blender HUD`
- The test-first implementation plan is
  `docs/superpowers/plans/2026-07-29-context-aware-adjust-last-operation-wrapping.md`.
- The user chose to keep this branch as-is. It was not merged, pushed, or
  cleaned up; no remote was changed.
- Completed one-off Superpowers plans/specifications were deleted; Git history
  remains their archive.
- `AGENTS.md` remains uncommitted pending user review. No production, test, or
  documentation changes from the HUD milestone remain uncommitted.

## Completed simplification

- Added generated characterization for public API 1.2 operator IDs, public
  Analyze arguments, registered policy defaults, and material-group counts.
- Kept policy EnumProperty declarations local: their labels, order, callbacks,
  visibility, and unsupported defaults intentionally differ. A shared policy
  module would add indirection or alter registered RNA.
- Shared Apply validation, report lookup, authoritative revalidation,
  assignment-plan creation, and exact-review comparison without changing
  confirmation or mutation boundaries.
- Removed the parallel per-material count `Counter`; public group counts now
  derive from authoritative face-index lists.
- Centralized API status publication in `api_contract.publish_status()`.
- Removed unused private WindowManager image/UV/channel properties while
  preserving the public Analyze operator arguments.
- Removed tests that parsed `panel.py` and `assign_materials.py` source text;
  observable presentation, dialog, cancellation, and README contracts remain.
- Independent review added real panel-draw coverage for stale/no-source/
  already-separated copy, native disclosure binding/icons, and public counts.
- Rebuilt the ignored extension ZIP. No private helper, asset, raw result,
  package, or test output was committed.
- Replaced fixed 34- and 52-character wrapping with a pure width-aware
  presentation helper.
- Routed shared panel messages through the active sidebar-region width.
- Made the Apply confirmation retain an adaptive requested width from 420 to
  560 pixels, capped to the usable Blender window.
- Added generated narrow/ordinary/wide wrapping, first-line icon, dialog-width,
  and invoke/draw-equivalence coverage.
- Made assignment drawing use Blender's positive native `HUD` region width,
  with a 220-pixel fallback for a HUD whose width is unavailable. Confirmation
  and non-HUD draws retain the adaptive saved dialog width.
- Added a generated Blender regression proving HUD, fallback, non-HUD, and
  missing-context behavior without introducing another wrapping abstraction.

## Validation executed

All commands used Blender 5.2.0 LTS and `--disable-autoexec` where applicable.

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

Results: 51/51 unit tests passed; the complete headless Blender suite passed,
including analysis/preview, assignment, policy, identity, FBX, preservation,
UX, revalidation, characterization, lifecycle, and simplification contracts;
source validation passed.

For the HUD correction, the complete headless Blender suite was first run
against the generated regression and failed at
`tests/blender/test_assignment_policies.py:322` because the HUD draw ignored
the 220-pixel region width. After the production change, the same complete
suite passed with `ASSIGNMENT_POLICY_TESTS_OK` and `BLENDER_TESTS_OK`.

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
  .local-references\default-example\before.blend
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
  .local-references\default-example\after.blend
```

Both private smokes passed their established aggregate checks: all 48 selected
meshes analyzed, 65,773 face changes were planned, 23 unresolved groups were
left unchanged, and zero objects or material groups were blocked/skipped.
Neither private file was saved.

```powershell
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate $Archive
Get-FileHash -Algorithm SHA256 $Archive
```

Archive validation passed. Current ignored package:
`.packaged-releases/alpha_material_separator-0.1.0.zip`, 65,100 bytes,
SHA-256 `568B2F1FDF0D6C478D96947E9A522FDF4FE8DEDD950D4B113CBB57C0DE201B2E`.

`git diff --check` passed throughout. Expected noise was limited to Blender's
bundled Grease Pencil brush-path warning, the deliberately exercised
stale-input warning, and Git LF-to-CRLF working-copy notices.

Temporary factory-startup, source-registered Blender 5.2 sessions completed
Analyze → Preview → warning confirmation at 100% and 150% UI scale. The 100%
session covered narrow and wide panel layouts; the alpha-source advisory
wrapped only at the narrow width. The 150% panel and 560-pixel confirmation
remained readable, with only the long final safety sentence wrapping. Both
confirmations were canceled before assignment and neither private file was
saved. Automated sidebar resizing was unreliable in the 150% session, so that
specific narrow-layout combination remains open.

The rebuilt ZIP was reinstalled and enabled successfully under ignored
isolated profile `.test-output/responsive-ui-profile`; `extension list`
reported `alpha_material_separator [installed]`. The lawful private
`before.blend` was opened with auto-execution disabled and all 48 eligible mesh
objects completed Analyze → Preview → Apply. The adaptive warning confirmation
was readable. The normal-width native `Assign Alpha Materials` HUD showed all
sentences without ellipses, and its 65,773 moved faces, 28 added slots, 57,731
mixed faces, 2,577 uncertain faces, and 23 unresolved groups agreed with the
sidebar. `Ctrl+Z` removed the derived slot visible on the inspected object.
No save action was performed. The isolated Blender session remains open with
unsaved transient UI/selection state so the private file is not overwritten.

An attempted drag did not resize the native HUD, so reduced wrapping when
widened and increased wrapping when narrowed were not counted as visually
verified. The generated Blender test covers positive 220-pixel HUD width, zero
width fallback, non-HUD width isolation, and missing context.

## Open failures and assumptions

- The private semantic lower bound still includes reference-alpha faces whose
  participating decoded A evidence classifies them `OPAQUE`.
- The isolated installed ZIP still needs a narrow/wide native-HUD resize check
  and the remaining 100%/150% panel matrix. Normal-width installed-ZIP
  confirmation, HUD readability, fact equivalence, and undo passed.
- The generated interactive two-material partial-apply check and distinct
  final Apply-preflight timing remain open.
- Ordinary Unity material/submesh validation remains a release requirement.
  VRChat validation applies only to its exact tested stack.

## Remaining tasks

1. Complete the isolated installed-ZIP narrow/wide 100%/150% panel and
   Apply-dialog visual checklist; the ZIP is already installed in the ignored
   profile. Include a native-HUD resize check if Blender exposes a workable
   resize interaction.
2. Review the uncommitted `AGENTS.md` clarification and commit it separately if
   accepted.
3. Investigate private `OPAQUE` lower-bound misses with ignored anonymized
   diagnostics and a generated failing regression before any production fix.
4. Complete the interactive partial-apply check and Apply-preflight timing.
5. Record user-performed ordinary Unity material/submesh acceptance.

## Recommended next action

Complete the remaining isolated installed-ZIP narrow/wide 100%/150% visual
matrix, including native-HUD resize behavior if Blender permits resizing it.
