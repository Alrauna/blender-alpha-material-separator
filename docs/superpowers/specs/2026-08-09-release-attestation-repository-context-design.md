# Release Attestation Repository Context Design

**Approved:** 2026-08-09

## Problem

Manual release run `31304598307` built version 1.3.1, created a draft release,
uploaded both assets, downloaded the stored ZIP in `release_draft`, and verified
its SHA-256. The separate `release_attestation` job then failed before invoking
`actions/attest`:

```text
failed to run git: fatal: not a git repository (or any of the parent directories): .git
```

The attestation job intentionally has no checkout. Its `gh release download`
command omitted `--repo`, so GitHub CLI tried to infer the repository from a
local Git remote that does not exist in that job.

## Approved correction

Pass the standard GitHub Actions repository identity explicitly:

```powershell
gh release download $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  --pattern $env:ARCHIVE_NAME `
  --dir $DownloadDirectory
```

Add a workflow contract that isolates the `release_attestation` section and
requires `--repo $env:GITHUB_REPOSITORY`. This reproduces the hosted failure as
a deterministic source contract before the workflow edit.

## Security and scope

- Keep the attestation job without a checkout.
- Keep its permissions exactly `contents: read`, `id-token: write`, and
  `attestations: write`.
- Keep the existing full-SHA `actions/attest` pin and exact ZIP digest check.
- Add no action, token, dependency, permission, trigger, or network source.
- Do not delete or publish the failed v1.3.1 draft in this branch. Recovery is
  separately authorized hosted work after the correction merges.
