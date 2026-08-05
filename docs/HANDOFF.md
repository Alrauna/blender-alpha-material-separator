# Repository handoff

Updated: 2026-08-05

## Current objective

Complete the acceptance that cannot run headlessly for the 1.1.0
significance-settings fix, then decide how to integrate
`feat/blender-alpha-material-separator-1.1.0`.

## Completed work

- The CI/CD milestone is complete. Pull request
  [#2](https://github.com/Alrauna/blender-alpha-material-separator/pull/2)
  merged to `main` at `b8af812` on 2026-08-01, with both platform checks
  passing.
- Release `v1.0.0` was published from `b8af812` on 2026-08-01. The user
  approved and tested it.
- Pull request
  [#3](https://github.com/Alrauna/blender-alpha-material-separator/pull/3)
  merged at `aabb65a` on 2026-08-03, a Copilot Autofix setting
  `context.minimum_version` to TLS 1.2 in `quad9_addresses`. CodeQL alert 1 is
  `fixed`.
- Classic branch protection is applied to `main` with user approval. Both CI
  checks are required and bound to the GitHub Actions app (`app_id` 15368),
  force pushes and branch deletion are blocked, and administrators are
  included.
- The Expert significance-settings defect is fixed on
  `feat/blender-alpha-material-separator-1.1.0`. Root cause, design, plan, and
  four implementation commits are complete and locally verified.
- The seven Expert Analysis Settings tooltips are rewritten in artist-facing
  language, and the panel has a Reset to Default Values button backed by
  `ALPHA_MATERIAL_SEPARATOR_OT_reset_analysis_settings`. The reset uses
  `property_unset()` so no default value is duplicated, and it invalidates a
  completed analysis only when a value actually changes.
- Minimum Affected Pixels no longer offers a dead value. A face with no
  affected texels returns `OPAQUE` before the gate runs, so the gate can never
  see a count below 1, which made 0 and 1 behave identically. The RNA hard
  minimum is now 1 in both `addon/properties.py` and
  `addon/operators/analyze.py`. Classification is unchanged, and
  `AnalysisSettings` in the pure core still accepts 0 as "gate off".

## The significance-settings fix

Analysis, classification, and settings plumbing were all correct. A face below
either significance gate is classified `SUPPRESSED`, and
`build_assignment_plan` blocked the entire material group whenever a group
contained any suppressed face and `suppressed_policy` was
`CANCEL_SOURCE_MATERIAL`, which was the shipped default. A face that passed the
gate was therefore discarded because a sibling face did not. Because a face with
zero affected texels returns `OPAQUE` before the gates run, `min_affected_texels`
values of `0` and `1` can never suppress, so the setting moved straight from no
effect to cancelling a material group.

The default is now `KEEP_SOURCE` in `addon/properties.py`,
`addon/operators/assign_materials.py`, and `addon/operators/select_faces.py`.
`CANCEL_SOURCE_MATERIAL` remains selectable and still blocks.

## Important decisions and constraints

- The TLS autofix stays as it is, with no retroactive regression test, by
  explicit user decision.
- Because administrators are included in branch protection, `main` no longer
  accepts a direct push. Every change needs a pull request whose two CI checks
  pass.
- Documentation and feature commits stay local for now by explicit user
  decision. Do not push without separate approval.
- Deleting `docs/superpowers/` is approved in principle but deferred until
  after this rework, by explicit user decision. Delete it during the milestone
  cleanup, including the two documents added for this change.
- `addon/api_contract.py` carries `EXTENSION_VERSION` independently of the
  manifest. A release bump must change both; `tests/unit/test_api_contract.py`
  cross-checks them.
- Do not push, merge, tag, release, or change repository settings without
  explicit approval.

## Files changed and why

- `addon/properties.py`, `addon/operators/assign_materials.py`,
  `addon/operators/select_faces.py`: default `suppressed_policy` to
  `KEEP_SOURCE` and move the conservative-default description to match.
- `addon/presentation.py`: name the policy that restores a blocked group.
- `addon/properties.py`: artist-facing descriptions for the seven analysis
  settings, plus `ANALYSIS_SETTING_NAMES` as the single source of truth for
  which settings the Expert Analysis Settings panel owns.
- `addon/operators/ui_actions.py`, `addon/registration.py`, `addon/panel.py`:
  the Reset to Default Values operator, its registration, and its button.
- `addon/api_contract.py`, `addon/blender_manifest.toml`: version `1.1.0`.
- `tests/unit/test_alpha_classification.py`: gate boundary, no-op, and margin
  characterization.
- `tests/blender/test_significance_settings.py`, `tests/blender/run_all.py`:
  the sibling-face regression, the resolved defaults, and the end-to-end
  default assignment outcome.
- `tests/blender/test_assignment_policies.py`,
  `tests/blender/test_simplification_contracts.py`,
  `tests/unit/test_api_contract.py`, `tests/unit/test_presentation.py`:
  expectations updated for the new default and version.
- `README.md`, `docs/algorithm.md`: describe the new default action, the
  Chebyshev margin, and the strict gate comparison.
- `CLAUDE.md`: point Claude Code at the shared `AGENTS.md` policy.

## Validation commands and results

Run on 2026-08-05 with Blender 5.2.0 LTS and its bundled Python 3.13.13.

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Results: 95 unit tests passed; the headless suite exited 0 with every
completion marker including the new
`ALPHA_MATERIAL_SEPARATOR_SIGNIFICANCE_TESTS_OK`; source validation succeeded;
`alpha_material_separator-1.1.0.zip` built and validated; and the diff check
reported no whitespace errors.

## Known failures, warnings, and unverified assumptions

- No known failures. Local `main` matches `origin/main`. Unpushed work is on
  `docs/post-release-state` and `feat/blender-alpha-material-separator-1.1.0`,
  which contains the former plus the four fix commits.
- The design spec originally claimed no existing test relied on the shipped
  default. That was wrong; two did. The spec's risk section records the
  correction.
- The private `.local-references/default-example/` acceptance was run with the
  ignored helper in that directory, against both this branch and the
  pre-change `main`. Both runs succeeded and produced an identical aggregate
  summary, which is the expected result: the default `min_affected_texels` of 1
  never suppresses a face, so the new `KEEP_SOURCE` default has nothing to act
  on until a significance gate is deliberately raised. Faces whose UVs fall
  outside the base tile were analyzed rather than rejected. Aggregate counts,
  raw output, and any identifying detail are deliberately not recorded here.
- `docs/superpowers/plans/2026-08-01-github-actions-ci-cd.md` still has
  unchecked boxes for steps that the merge history and hosted runs show were
  executed.
- Three earlier plans still show unchecked installed-ZIP interactive
  acceptance steps whose completion is unverified.
- The local recovery branch `feat/alpha-material-separator-0.1` no longer
  exists. Its history is contained in `main`.
- The git policy in `AGENTS.md` still directs work to `ci/automation`, which is
  merged and stale.
- Expected local output includes LF-to-CRLF Git notices.

## Remaining tasks in priority order

1. Perform installed-ZIP interactive acceptance in a clean Blender 5.2
   configuration, including Analyze → Preview → Tab to Object Mode → Apply, and
   confirm that a below-significance face now reports under `Faces kept by
   policy` rather than blocking its group. Also hover each of the seven Expert
   analysis settings to check the rewritten tooltips at the panel's width, and
   press Reset to Default Values with an existing analysis to confirm the panel
   reports that inputs changed. Confirm that Minimum Affected Pixels will not go
   below 1 and that 2 still filters as expected.
3. Decide how to integrate `feat/blender-alpha-material-separator-1.1.0`. It
   needs a pull request because `main` is protected.
4. Delete `docs/superpowers/` during this milestone's cleanup.

## Recommended next action

Run the private before/after smoke and the installed-ZIP acceptance. Both need
the user; neither can run headlessly.
