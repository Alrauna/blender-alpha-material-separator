# Repository handoff

Updated: 2026-07-28

## Current objective

Finish the remaining installed-ZIP visual acceptance for the implemented
width-aware Material Details, shared panel, and Apply-confirmation text. The
production change, automated validation, source-registered visual checks, and
isolated ZIP installation are complete. Short sentences stay intact when space
permits, narrow layouts wrap at word boundaries, and the Apply dialog adapts
from 420 to 560 pixels or the smaller usable window width.

## Repository state

- Branch: `feat/alpha-material-separator-0.1`; configured upstream is `[gone]`.
- The completed simplification range is `4138236..3e5c0f2`, including cleanup
  commit `3b94172` and independent-review coverage commit `3e5c0f2`.
- Width-aware UI commits:
  - `ddef5fc docs: design width-aware UI wrapping`
  - `b9cca42 feat: add width-aware UI text wrapping`
  - `4029ce6 fix: adapt UI text to available width`
  - `5edc942 fix: wrap alpha source advisory heading`
- The user chose to keep this branch as-is. It was not merged, pushed, or
  cleaned up; no remote was changed.
- Completed one-off Superpowers plans/specifications were deleted; Git history
  remains their archive.
- `AGENTS.md` remains uncommitted pending user review. No production or test
  changes remain uncommitted after the cleanup boundary.

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

Archive validation passed. Ignored package:
`.packaged-releases/alpha_material_separator-0.1.0.zip`, 64,977 bytes,
SHA-256 `15721DE78D47E74BEB4C36F6969D1AE055AB4DB6C58D8587B9E8D6C0C1A4AA61`.

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

The rebuilt ZIP was installed and enabled successfully under ignored isolated
profile `.test-output/responsive-ui-profile`; `extension list` reported
`alpha_material_separator [installed]`. Windows UI targeting became unreliable
while distinguishing that session from the two source-registered sessions, so
the complete installed-ZIP dialog interaction was not counted as passed.

## Open failures and assumptions

- The private semantic lower bound still includes reference-alpha faces whose
  participating decoded A evidence classifies them `OPAQUE`.
- The isolated installed ZIP still needs a clean, unambiguous narrow/wide
  visual pass at 100%/150% scale. Automated contracts and source-registered
  100%/150% interaction pass.
- The generated interactive two-material partial-apply check and distinct
  final Apply-preflight timing remain open.
- Ordinary Unity material/submesh validation remains a release requirement.
  VRChat validation applies only to its exact tested stack.

## Remaining tasks

1. Complete the isolated installed-ZIP narrow/wide 100%/150% panel and
   Apply-dialog visual checklist; the ZIP is already installed in the ignored
   profile.
2. Review the uncommitted `AGENTS.md` clarification and commit it separately if
   accepted.
3. Investigate private `OPAQUE` lower-bound misses with ignored anonymized
   diagnostics and a generated failing regression before any production fix.
4. Complete the interactive partial-apply check and Apply-preflight timing.
5. Record user-performed ordinary Unity material/submesh acceptance.

## Recommended next action

Complete the isolated installed-ZIP responsive panel/dialog visual check.
