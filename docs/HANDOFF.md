# Repository handoff

Updated: 2026-07-28

## Current objective

Continue Blender Alpha Material Separator 0.1 release hardening. The approved
repository-simplification pass is complete and locally verified. The next
immediate decision is user review of the remaining uncommitted `AGENTS.md`
clarification; the next product check is installed-ZIP visual acceptance.

## Repository state

- Branch: `feat/alpha-material-separator-0.1`; configured upstream is `[gone]`.
- No remote was changed and nothing was pushed or published.
- Simplification commits:
  - `4138236 test: characterize repository simplification contracts`
  - `9383f31 refactor: share assignment preflight validation`
  - `9379449 refactor: remove redundant analysis and status state`
  - `d1a690c refactor: remove unused legacy UI settings`
  - `f330192 test: remove brittle source implementation contracts`
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

## Validation executed

All commands used Blender 5.2.0 LTS and `--disable-autoexec` where applicable.

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

Results: 50/50 unit tests passed; the complete headless Blender suite passed,
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
`.packaged-releases/alpha_material_separator-0.1.0.zip`, 64,444 bytes,
SHA-256 `121244DB669666802B0FCE3228B65EEED7E5CEB9ECEFE9FA95192EC847ED0924`.

`git diff --check` passed throughout. Expected noise was limited to Blender's
bundled Grease Pencil brush-path warning, the deliberately exercised
stale-input warning, and Git LF-to-CRLF working-copy notices.

## Open failures and assumptions

- The private semantic lower bound still includes reference-alpha faces whose
  participating decoded A evidence classifies them `OPAQUE`.
- Compact confirmation and Material Details still need installed-ZIP visual
  checks at narrow/wide layouts and 100%/150% UI scale.
- The generated interactive two-material partial-apply check and distinct
  final Apply-preflight timing remain open.
- Ordinary Unity material/submesh validation remains a release requirement.
  VRChat validation applies only to its exact tested stack.

## Remaining tasks

1. Review the uncommitted `AGENTS.md` clarification and commit it separately if
   accepted.
2. Complete installed-ZIP visual checks, including Cancel, Apply, and Ctrl+Z.
3. Investigate private `OPAQUE` lower-bound misses with ignored anonymized
   diagnostics and a generated failing regression before any production fix.
4. Complete the interactive partial-apply check and Apply-preflight timing.
5. Record user-performed ordinary Unity material/submesh acceptance.

## Recommended next action

Review `AGENTS.md`; if accepted, commit that guidance as its own documentation
boundary before starting another product change.
