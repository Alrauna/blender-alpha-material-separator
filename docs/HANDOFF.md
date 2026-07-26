# Repository handoff

Updated: 2026-07-26

## Current objective

Continue release hardening for Blender Alpha Material Separator 0.1 on
`feat/alpha-material-separator-0.1`. The main Base Color stored-A fallback
milestone is implemented. The immediate open objective is to explain the
remaining private before/after lower-bound faces that the extension classifies
`OPAQUE`, without broadening the approved resolver, changing raster margin
zero, or adding private-example heuristics.

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
- Upgraded the ignored private helper to validate every mesh, semantic
  before/after roles, multi-image Base Color resolution, out-of-range UVs,
  exact Preview/Apply equivalence, derived destinations, source/image/mesh/rig
  preservation, and immutable reference files.
- Created the implementation commits covered by this handoff:
  - `0527dc1 test: cover UV coordinates outside the base tile`
  - `f9d15f2 fix: resolve base color alpha with ancillary textures`
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
  fingerprinting.
- `addon/presentation.py`: actionable automatic/manual alpha-source remedies.
- `tests/blender/test_analysis_preview.py`: resolver precedence, ancillary
  images, reroutes, unsupported paths, overrides, decoded A modes, opaque and
  missing images, plus out-of-range UV integration.
- `tests/blender/test_revalidation_matrix.py`: ancillary pixel/digest behavior,
  assignment-only review invalidation, and classification-relevant shader
  staleness.
- `tests/unit/test_alpha_classification.py`: Repeat/Extend/Clip/Mirror coverage
  outside 0–1.
- `tests/unit/test_presentation.py`,
  `tests/unit/test_readme_contract.py`: preserved and extended UX/documentation
  contracts.
- `README.md`, `docs/material-support.md`, `docs/integration-api.md`,
  `docs/testing.md`, `docs/performance.md`, `PLAN.md`: implemented behavior,
  testing boundary, performance comparison, and remaining acceptance gate.
- `AGENTS.md`: durable plugin-coordination, private-smoke, and handoff rules
  requested earlier in the worktree.
- `.local-references/default-example/_validate_analysis.py`: ignored private
  acceptance helper; never commit it or its output.
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
- The 150% UI-scale pass, generated two-material interactive partial-apply
  checklist item, and ordinary Unity material/submesh validation remain
  unverified release gates.
- VRChat validation remains optional evidence for the exact tested stack only.

## Remaining tasks in priority order

1. Investigate the remaining private `OPAQUE` lower-bound faces by comparing
   their supported authority, resolved UV/address mode, positive-area coverage,
   addressed texels, and decoded A values. Keep diagnostics ignored and
   anonymized.
2. If a genuine general defect is found, reproduce it with a generated failing
   test before changing production code. Do not change resolver scope or margin
   merely to match the private after file.
3. Complete the generated two-material interactive partial-apply checklist and
   150% UI-scale pass.
4. Have the user perform ordinary Unity material/submesh acceptance and record
   the result.
5. Rerun the complete gate for any production follow-up. Do not push without
   separate approval.

## Recommended next action

Run an ignored diagnostic pass over only the remaining private opaque
lower-bound faces, recording anonymized counts for resolved source kind,
address mode, UV coverage, sampled alpha range, and semantic-role ambiguity.
Use that evidence to decide whether the next task is a raster/addressing defect,
an image-decoding issue, or a difference between the human-tuned after file and
the extension's unopinionated visual-equivalence rule.
