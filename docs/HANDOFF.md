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
- The local test-first correction now validates that exact banner while
  continuing to reject other versions and arbitrary suffixes.

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

## Known failures, warnings, and unverified assumptions

- The corrected branch has been pushed, but its Windows and Linux hosted
  validation results have not yet been observed.
- Expected local output includes LF-to-CRLF Git notices.

## Remaining tasks in priority order

1. Observe both hosted validation jobs for `8d741b6`.
2. Address only any newly demonstrated hosted failure.

## Recommended next action

Observe the Windows and Linux hosted validation jobs.
