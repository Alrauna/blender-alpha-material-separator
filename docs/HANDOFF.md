# Repository handoff

Updated: 2026-08-01

## Current objective

Restore the Windows and Linux validation jobs on draft pull request
[#2](https://github.com/Alrauna/blender-alpha-material-separator/pull/2).

## Completed work

- The version-banner correction was pushed on `ci/automation` at `8d741b6`.
- Hosted run
  [30701872660](https://github.com/Alrauna/blender-alpha-material-separator/actions/runs/30701872660)
  verified and extracted the fixed Blender archives on both platforms, then
  rejected Blender's official `Blender 5.2.0 LTS` version banner.
- Commit `8d741b6` corrected that banner check.
- Hosted run
  [30702303585](https://github.com/Alrauna/blender-alpha-material-separator/actions/runs/30702303585)
  then passed all unit and Blender tests on both platforms, but ZIP creation
  failed because `${{ runner.temp }}/release` did not exist.
- The local test-first correction now creates that directory before both the
  validation and release ZIP builds.
- Commit `7a3b044` contains the focused workflow and regression-test change.

## Important decisions and constraints

- Keep the version check exact. Do not replace it with prefix or loose regex
  matching.
- Existing checksum consensus, committed SHA-256 anchors, safe extraction,
  and least-privilege workflow controls remain unchanged.
- Do not merge, tag, release, publish, or change repository settings without
  explicit approval.

## Files changed and why

- `scripts/ci.py`: validate Blender's exact official 5.2.0 LTS banner.
- `tests/unit/test_ci.py`: generated regression for accepted and rejected
  version banners.
- `.github/workflows/ci.yml`: create each temporary ZIP output directory before
  invoking Blender.
- `tests/unit/test_ci_workflow_contract.py`: require both build steps to create
  their output directory first.
- `docs/HANDOFF.md`: record the current failure, local correction, and next
  hosted verification.

## Validation commands and results

### Hosted failure

Both `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2` failed in
`Verify and extract Blender 5.2.0` with:

```text
ValueError: unexpected Blender version: 'Blender 5.2.0 LTS'
```

### RED

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_blender_version_requires_official_lts_banner `
  -v
```

Result: failed because `require_blender_version` did not exist.

### GREEN

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_blender_version_requires_official_lts_banner `
  -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Result: focused test passed, all 87 unit tests passed, and diff check reported
no whitespace errors.

The local executable independently reported:

```text
Blender 5.2.0 LTS
```

### ZIP output directory RED/GREEN

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_build_steps_create_their_output_directory_first `
  -v
```

RED result: both build-step subtests failed because no directory creation
preceded Blender.

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_build_steps_create_their_output_directory_first `
  -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

GREEN result: the focused test and all 88 unit tests passed. A real local
Blender invocation built and validated
`alpha_material_separator-1.0.0.zip` in a newly created ignored output
directory.

## Known failures, warnings, and unverified assumptions

- The output-directory correction is committed locally but has not been pushed.
- Windows and Linux hosted packaging remain unverified until the corrected
  branch is pushed and rerun.
- Expected local output includes LF-to-CRLF Git notices.

## Remaining tasks in priority order

1. Obtain push authorization, push `ci/automation`, and observe both hosted
   validation jobs.
2. Address only any newly demonstrated hosted failure.

## Recommended next action

Push `ci/automation` after explicit authorization, then observe both hosted
validation jobs.
