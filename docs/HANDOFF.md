# Repository handoff

Updated: 2026-07-28

## Current objective

Continue release hardening for Blender Alpha Material Separator 0.1 on
`feat/alpha-material-separator-0.1`. The approved count-only **Apply Material
Separation** confirmation is implemented and automated/private verification
passes. Its one remaining acceptance item is an installed-ZIP visual check at
narrow/wide layouts and 100%/150% UI scale, including Cancel, Apply, and Undo.
After that, the next classification objective remains explaining private
before/after lower-bound faces that the extension classifies `OPAQUE`, without
broadening the approved resolver, changing raster margin zero, or adding
private-example heuristics.

## Completed work

- Preserved the existing branch, remote, prior commits, and pending UV,
  documentation, presentation, and testing work.
- Added and committed generated coverage proving positive-area UV faces outside
  0–1 use Repeat, Extend, Clip, and Mirror instead of becoming unsupported.
- Reproduced the resolver defect with a generated Base Color image plus
  connected normal, roughness, emission, and disconnected image nodes before
  changing production code.
- Changed automatic resolution to use the single supported active Base Color
  authority rather than requiring one Image Texture in the entire material.
- Preserved precedence: per-material override, supported Principled Alpha image
  path, then stored A from the supported Base Color image only when Alpha is
  genuinely unlinked.
- Distinguished genuinely unlinked sockets from dangling/cyclic/ambiguous
  reroute paths. Connected unsupported Alpha processing remains explicit and
  recoverable through a manual source.
- Split classification authority from assignment-only material state.
  Ancillary-image pixel changes perform no participating-image digest work;
  unrelated source-graph changes retain analysis but clear exact-plan review.
- Added deterministic plan fingerprints covering current source state, derived
  decisions, object identity, and exact face sets.
- Characterized decoded stored A for Blender-generated RGB-style/RGBA images,
  fully opaque A, missing images, and `STRAIGHT`, `PREMUL`, `CHANNEL_PACKED`,
  and `NONE` alpha modes without changing image-decoding semantics.
- Updated README, panel remedies, support matrix, integration API, testing,
  performance, PLAN, and durable contributor guidance.
- Added state-aware hover text to the disabled Preview and Apply buttons when
  selected meshes are already separated: “All faces on the selected meshes are
  optimally assigned. No faces need to be moved.” Other disabled states retain
  the normal operator descriptions.
- Corrected the rerun predicate after reproducing the user's real partial-apply
  workflow: already-separated groups now receive the contextual tooltip when
  no actionable moves remain, even if unresolved groups were safely left
  unchanged. A purely unresolved plan still retains its normal tooltip.
- Reproduced the Edit Mode Analyze failure with the exact
  `bpy_prop_collection[index]: index 0 out of range, size 0` status and fixed
  the shared synchronous/modal start boundary to enter Object Mode before
  constructing the analysis engine.
- Replaced the always-expanded material cards with one Blender-native
  **Material Details (N)** disclosure. It automatically collapses only after a
  successfully published analysis; canceled replacement analysis preserves the
  previous report, review token, and disclosure state.
- Added one informational box above the disclosure when deduplicated material
  results lack an automatic alpha source. Singular/plural copy is generated
  from the same card list the disclosure renders, and all existing manual-source
  actions remain inside it.
- Added unit and Blender regressions for card deduplication, advisory copy,
  successful reset, cancellation preservation, and review-token stability.
- Rebuilt and validated the ignored local extension ZIP with this UI change.
- Replaced the unbounded assignment warning with a native 420-pixel
  **Apply Material Separation** dialog whose positive action is **Apply**.
  Its copy contains at most seven aggregate outcome rows and never lists
  object, material, image, UV, or destination names.
- Added exact `mixed_faces_to_alpha` and `suppressed_faces_to_alpha` plan
  counts, including zeroing them when derived-material preflight blocks a
  group. The dialog therefore describes the actual mutation plan rather than
  broad analysis totals.
- Added a real-plan cancellation-boundary regression proving that native-dialog
  cancellation changes neither polygon material indices nor material slots.
- Updated README and testing guidance so detailed identities remain under
  **Review → Material Details**, while the confirmation reports only aggregate
  outcomes.
- Upgraded the ignored private helper to validate every mesh, semantic
  before/after roles, multi-image Base Color resolution, out-of-range UVs,
  exact Preview/Apply equivalence, derived destinations, source/image/mesh/rig
  preservation, and immutable reference files.
- Created the implementation commits covered by this handoff:
  - `0527dc1 test: cover UV coordinates outside the base tile`
  - `f9d15f2 fix: resolve base color alpha with ancillary textures`
  - `b7f74f7 docs:design-already-separated-button-tooltips`
  - `8f2dd87 fix:explain-already-separated-workflow-actions`
  - `041c4cc fix:show-rerun-tooltip-after-partial-apply`
  - `7a48eb0 fix:analyze-selected-meshes-from-edit-mode`
  - `b6087aa docs:design-collapsible-material-details`
  - `2c75c6f feat:collapse-material-review-details`
  - `b62ae03 docs:design-compact-apply-confirmation`
  - `db4ca47 docs:plan-compact-apply-confirmation`
  - `f74012d feat:compact-the-apply-confirmation`
- Nothing was pushed.

## Important decisions and constraints

- Version remains `0.1.0`; public API remains `1.2`; operator IDs and public
  classifications are unchanged.
- `UNIQUE_BASE_COLOR_IMAGE_ALPHA` means one supported Base Color authority,
  not one Image Texture node globally.
- Explicit overrides and supported Principled Alpha paths retain precedence.
- A connected unsupported Alpha path blocks automatic Base Color fallback.
- Automatic Base Color scope is direct Image Texture Color, optionally through
  simple reroutes, to active Principled Base Color.
- Mix, Math, Mapping, arbitrary groups, multiple authorities, cycles, and
  non-image Base Color terminals remain unsupported.
- Blender transparency/render/shadow settings do not control whether stored
  Base Color A is analyzable.
- Raw decoded `Image.pixels` A remains authoritative; a readable fully opaque A
  channel is a valid opaque result.
- Repeat, Extend, Clip, and Mirror remain valid outside 0–1. Margin remains
  zero and `MIXED` remains conservatively routed to alpha.
- The private after example is a human-tuned lower bound. Extra conservative
  alpha assignments are valid; missed lower-bound faces remain an explicit
  failure.
- Private files, helper, names, paths, raw graph dumps, face sets, measurements,
  and assets remain ignored and uncommitted.
- No topology changes, shader rewriting, arbitrary graph evaluation, network
  access, dependency installation, CATS dependency, push, or publication.

## Files changed and why

- `addon/adapters/material_resolver.py`: authority-based Base Color fallback and
  explicit invalid-reroute handling.
- `addon/adapters/analysis.py`: classification-focused structural signatures,
  participating-image-only state, and separate assignment-plan invalidation.
- `addon/adapters/assignment.py`: current source fingerprints and exact plan
  fingerprinting, plus exact mixed/suppressed-to-alpha outcome counts.
- `addon/presentation.py`: actionable automatic/manual alpha-source remedies,
  the state-specific already-separated tooltip copy, and the pure deduplicated
  material-card/advisory presentation rules, plus bounded count-only assignment
  confirmation copy.
- `addon/operators/select_faces.py`, `addon/operators/assign_materials.py`:
  transient contextual Blender operator descriptions and the bounded native
  count-only assignment dialog.
- `addon/panel.py`: supplies contextual button descriptions and renders the
  material advisory plus one native disclosure around existing cards.
- `addon/properties.py`: transient, non-saved disclosure Boolean.
- `addon/operators/analyze.py`: synchronizes Edit Mode changes before
  authoritative reads and collapses material details after successful report
  publication.
- `tests/blender/test_analysis_preview.py`: resolver precedence, ancillary
  images, reroutes, unsupported paths, overrides, decoded A modes, opaque and
  missing images, out-of-range UV integration, and multi-object Edit Mode
  Analyze.
- `tests/blender/test_revalidation_matrix.py`: ancillary pixel/digest behavior,
  assignment-only review invalidation, and classification-relevant shader
  staleness.
- `tests/unit/test_alpha_classification.py`: Repeat/Extend/Clip/Mirror coverage
  outside 0–1.
- `tests/unit/test_presentation.py`,
  `tests/unit/test_readme_contract.py`: preserved and extended UX/documentation
  contracts, including count adaptation, privacy, zero-clause omission, and
  removal of unbounded dialog content.
- `tests/blender/test_assignment_policies.py`: exact mixed/suppressed plan
  outcomes and native-dialog cancellation with zero mutation.
- `tests/blender/test_ux_overrides.py`: operator-description coverage and
  disclosure state-transition/review-preservation coverage.
- `README.md`, `docs/material-support.md`, `docs/integration-api.md`,
  `docs/testing.md`, `docs/performance.md`, `PLAN.md`: implemented behavior,
  testing boundary, performance comparison, and remaining acceptance gate.
- `AGENTS.md`: durable plugin-coordination, private-smoke, and handoff rules
  requested earlier in the worktree.
- `.local-references/default-example/_validate_analysis.py`: ignored private
  acceptance helper; never commit it or its output.
- `.local-references/default-example/_diagnose_rerun_tooltip.py`: ignored
  aggregate smoke helper extended locally with material-card, advisory,
  collapsed-state, count-only confirmation privacy, and exact-plan assertions;
  never commit it or its output.
- `docs/superpowers/specs/2026-07-28-collapsible-material-details-design.md`,
  `docs/superpowers/plans/2026-07-28-collapsible-material-details.md`: approved
  design and test-first implementation record.
- `docs/HANDOFF.md`: this current continuation record.

## Validation commands and results

All commands used Blender 5.2.0 LTS from
`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.

1. Baseline:

   ```powershell
   python -m unittest discover -s tests/unit -t . -v
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   ```

   Result before production changes: 42 unit tests passed; the complete
   headless Blender suite passed.

2. Resolver red test:

   ```powershell
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   ```

   Expected result before the fix: failed in the generated ancillary-texture
   case because resolution returned `NO_AUTHORITATIVE_ALPHA_IMAGE`.

3. Cache/review red test:

   The same Blender command then failed as expected with `INPUTS_CHANGED` after
   an assignment-only Normal Map setting edit.

4. Final generated verification:

   ```powershell
   python -m unittest discover -s tests/unit -t . -v
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   ```

   Result: 42/42 unit tests passed; all analysis/preview, assignment, policy,
   identity, FBX, preservation, override, revalidation, characterization, and
   lifecycle Blender tests passed.

5. Source, archive, and install:

   ```powershell
   & $Blender52 --factory-startup --command extension validate addon
   .\scripts\build_extension.ps1 -Blender $Blender52
   & $Blender52 --factory-startup --command extension validate `
     .\.packaged-releases\alpha_material_separator-0.1.0.zip
   ```

   Result: source validation passed; the ignored ZIP built successfully;
   archive validation passed. The ZIP was then installed into an isolated
   Blender profile and `tests/blender/verify_installed_zip.py` passed
   capability, disable, enable, and re-enable checks.

   Rechecked on 2026-07-26 after the milestone commits: the archive remains at
   `.packaged-releases/alpha_material_separator-0.1.0.zip`, is 63,471 bytes,
   has SHA-256
   `AAEDBDBB2F7D84CFF4E355DC6861AB50755FD3C22DE8E0447C98659B20BC98FC`,
   and Blender 5.2 source parsing succeeds.

6. Performance:

   ```powershell
   .\scripts\run_benchmarks.ps1 -Blender $Blender52
   ```

   Result: all tiers completed. Cold medians changed by approximately 0%,
   +1.98%, +1.92%, and -20.23% for small, typical, high, and tiled tiers.
   High-tier peak memory remained within 5%. Structural revalidation remained
   0.0345 seconds with zero image-digest rows and zero rasterized polygons.
   No matching metric exceeded the provisional 25% regression limit.

7. Private smoke:

   ```powershell
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 `
     --python .local-references\default-example\_validate_analysis.py -- `
     .local-references\default-example\before.blend `
     .local-references\default-example\after.blend
   ```

   Result: expected nonzero exit because the semantic lower-bound still has
   missed faces. The resolver, multi-image authority, out-of-range UV,
   exact-plan Preview → Object Mode → Apply, derived-role, preservation, and
   immutable-reference assertions all passed first. Remaining misses are
   classified `OPAQUE`; no unresolved-authority lower-bound group remains.

8. Repository checks:

   ```powershell
   git diff --check
   git status --short --branch
   ```

   Result before this handoff commit: no whitespace errors. Git emitted only
   expected LF-to-CRLF working-copy warnings. The branch upstream is marked
   `[gone]`; the remote was not altered.

9. Subsequent-run Preview diagnosis:

   ```powershell
   rg -n -C 6 "Preview Faces to Move|can_preview|actionable|ALREADY_SEPARATED|NO_CHANGES_NEEDED" addon/panel.py addon/presentation.py addon/adapters/assignment.py
   ```

   Result: Preview is intentionally disabled when the rebuilt assignment plan
   has no mutations or metadata refreshes. Previously generated materials are
   recognized through AMS metadata, not merely the `__AMS_ALPHA` name suffix;
   the panel reports “Already separated — no additional changes.”

10. Already-separated tooltip implementation:

   ```powershell
   C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe `
     -m unittest discover -s tests/unit -t . -v
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   & $Blender52 --factory-startup --command extension validate addon
   & $Blender52 --factory-startup --command extension build `
     --source-dir addon --output-dir .packaged-releases
   & $Blender52 --factory-startup --command extension validate `
     .packaged-releases\alpha_material_separator-0.1.0.zip
   git diff --check
   ```

   Result: the unit test first failed because the tooltip helper was absent;
   the Blender suite then failed because both operators lacked dynamic
   descriptions. Final diff review added a second red/green case proving that
   a selection containing skipped groups cannot claim that every face is
   optimally assigned. After implementation, 43/43 unit tests and the complete
   Blender suite passed. Source and rebuilt archive validation passed. The
   final ignored archive is 63,770 bytes with SHA-256
   `1174AF14BC4FAB9017DAC4ACAFF48819DAC9E27C69BF78662E4E5631A65BC778`.

11. Partial-apply rerun tooltip diagnosis:

   ```powershell
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 `
     --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
     .local-references\default-example\before.blend APPLY_FIRST
   ```

   Result before the correction: the second analysis had no actionable moves
   and contained both already-separated and unresolved groups, but the
   contextual tooltip was absent because `has_skips` suppressed it. The same
   complete Analyze → Preview → Apply → Analyze diagnostic passed after the
   correction with the contextual tooltip present. Only anonymized aggregate
   state was emitted; the ignored helper and private files remain uncommitted.
   The corrected ignored archive is 63,751 bytes with SHA-256
   `743AC91A8377DCC34ED024E3A0686D34BB50A5C088D2615F80209D43E754C466`.

12. Edit Mode Analyze regression:

   ```powershell
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   ```

   Result before the fix: the generated multi-object Edit Mode call returned
   `ANALYSIS_FAILED` with
   `bpy_prop_collection[index]: index 0 out of range, size 0`. After the shared
   start-boundary fix, the complete Blender suite passed and the test confirmed
   both selected meshes were in Object Mode after successful analysis. An
   ignored private smoke then started all eligible meshes in the messy
   before-example in multi-object Edit Mode; analysis completed across all 48
   selected meshes and every mesh ended in Object Mode. Only anonymized
   aggregate state was emitted and the reference file was not saved. The
   rebuilt ignored archive is 63,880 bytes with SHA-256
   `4CF330C8588BFB07B81FF945C6A79B30D483D32C493D48FBB8513DE53218CB84`.
   Final verification also passed all 43 unit tests, source validation, archive
   validation, and `git diff --check`.

13. Collapsible material-details TDD and package:

   ```powershell
   $Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
   & $Python52 -m unittest tests.unit.test_presentation -v
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   & $Python52 -m unittest `
     tests.unit.test_readme_contract.ReadmeContractTests.test_material_results_use_one_native_disclosure -v
   & $Python52 -m unittest discover -s tests/unit -t . -v
   & $Blender52 --factory-startup --command extension validate addon
   & $Blender52 --factory-startup --command extension build `
     --source-dir addon --output-dir .packaged-releases
   & $Blender52 --factory-startup --command extension validate `
     .packaged-releases\alpha_material_separator-0.1.0.zip
   git diff --check
   ```

   Result: the unit RED check failed because `review_material_cards` and
   `alpha_source_advisory` were absent. The Blender RED check failed because a
   successful analysis left `show_material_details` true. The panel contract
   then failed because the native disclosure was absent. After the minimal
   implementation, all 46 unit tests and the complete Blender suite passed.
   Source and rebuilt archive validation passed. The ignored archive is 64,403
   bytes with SHA-256
   `2C4E8B5FDB3CCC920EA61EA39C2B910A3867546D2595A05CF14527DD030FB227`.
   `git diff --check` reported only the repository's existing LF-to-CRLF
   checkout warnings.

14. Private material-details smoke:

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

   Result: both files analyzed all 48 selected mesh objects and published with
   Material Details collapsed. The before example produced 33 deduplicated
   cards and one advisory covering 15 unresolved cards; the after example
   produced 37 cards and the same single-advisory behavior. Both had zero
   skipped objects and retained actionable supported groups. Only anonymized
   aggregate counts were emitted; neither private file was saved.

15. Compact assignment-confirmation TDD, private smoke, and package:

   ```powershell
   $Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
   & $Python52 -m unittest tests.unit.test_presentation -v
   & $Python52 -m unittest discover -s tests/unit -t . -v
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 --python tests/blender/run_all.py
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 `
     --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
     .local-references\default-example\before.blend
   & $Blender52 --factory-startup --background --disable-autoexec `
     --python-exit-code 1 `
     --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
     .local-references\default-example\after.blend
   & $Blender52 --factory-startup --command extension validate addon
   & $Blender52 --factory-startup --command extension build `
     --source-dir addon --output-dir .packaged-releases
   & $Blender52 --factory-startup --command extension validate `
     .packaged-releases\alpha_material_separator-0.1.0.zip
   Get-FileHash -Algorithm SHA256 `
     .packaged-releases\alpha_material_separator-0.1.0.zip
   git diff --check
   ```

   RED evidence: the Blender policy suite first failed because the plan payload
   lacked `suppressed_faces_to_alpha`; the focused presentation test then
   failed because `assignment_confirmation_lines` did not exist; and the source
   contract/Blender imports failed because the bounded-dialog helper and
   constants did not exist. After the minimal implementation, 50/50 unit tests
   and the complete Blender suite passed. Both private files analyzed all 48
   selected meshes and passed exact-plan/count-only privacy checks with four
   semantic summary rows, 65,773 faces to reassign, 23 unchanged groups, and
   zero skipped groups/objects. Only anonymized aggregates were emitted and
   neither file was saved. Source and archive validation passed. The ignored
   archive is 64,549 bytes with SHA-256
   `F86BE735CC4D121D4F010A6CA8B40DD95D06519F3420D928FB449C60FE2C74BA`.
   `git diff --check` reported only expected LF-to-CRLF working-copy warnings.

## Known failures, warnings, and unverified assumptions

- Release acceptance remains open because the private semantic lower-bound has
  faces classified opaque by the current decoded A evidence.
- The helper's semantic role match uses source-graph equality and a private
  slot-change fallback only when role identity is ambiguous. That fallback
  should be audited while investigating the remaining opaque set.
- Blender emitted harmless warnings about bundled Grease Pencil brush paths in
  generated tests.
- The generated stale-input tests intentionally emit an “Analysis inputs
  changed” warning.
- Benchmarks emit Blender's existing warning that `Material.use_nodes` is
  expected to change in Blender 6.0; Blender 5.2 remains the target.
- Git reports the configured branch upstream as `[gone]`. No remote change or
  push was attempted.
- Preview and Apply are intentionally disabled after rerunning a genuinely
  already-separated or safely partial-applied selection with no remaining
  actionable moves. Both now explain this on hover. If either is disabled while
  new eligible source faces remain, capture the panel state and treat it as a
  separate plan-construction defect.
- The 150% UI-scale pass, generated two-material interactive partial-apply
  checklist item, and ordinary Unity material/submesh validation remain
  unverified release gates.
- The rebuilt ZIP has not yet received the visual disclosure check in narrow
  and wide 3D View sidebars. Automated tests prove state/copy contracts but do
  not prove Blender's actual layout, wrapping, or click target.
- The rebuilt ZIP has not yet received the compact confirmation check at
  narrow/wide layouts and 100%/150% UI scale. Automated tests prove exact
  counts, privacy, bounded prose, cancellation safety, and the native dialog
  options, but not Blender's rendered wrapping or click targets.
- VRChat validation remains optional evidence for the exact tested stack only.

## Remaining tasks in priority order

1. Install the rebuilt ZIP in a clean Blender 5.2 configuration and visually
   verify the compact confirmation at narrow/wide layouts and 100%/150% UI
   scale. Cancel with zero mutation, reopen and Apply the exact reviewed plan,
   then verify Ctrl+Z undo.
2. Complete any still-unverified wide-sidebar and 150% UI-scale checks for the
   accepted **Material Details (N)** disclosure during the same session.
3. Investigate the remaining private `OPAQUE` lower-bound faces by comparing
   their supported authority, resolved UV/address mode, positive-area coverage,
   addressed texels, and decoded A values. Keep diagnostics ignored and
   anonymized.
4. If a genuine general defect is found, reproduce it with a generated failing
   test before changing production code. Do not change resolver scope or margin
   merely to match the private after file.
5. Complete the generated two-material interactive partial-apply checklist and
   150% UI-scale pass.
6. Have the user perform ordinary Unity material/submesh acceptance and record
   the result.
7. Rerun the complete gate for any production follow-up. Do not push without
   separate approval.

## Recommended next action

Install the rebuilt ZIP in a clean Blender 5.2 configuration and perform the
compact confirmation's narrow/wide, 100%/150%, Cancel, Apply, and Undo visual
acceptance. Do not mark the checklist complete until those interactions have
actually been observed.
