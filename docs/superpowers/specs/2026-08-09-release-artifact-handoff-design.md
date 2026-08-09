# Release Artifact Handoff Design

**Approved in conversation:** 2026-08-09

## Objective

Publish version 1.3.1 with GitHub build-provenance attestation while keeping
`actions/attest` outside every job that has release-write permission. Pass one
validated ZIP byte-for-byte from packaging through attestation and publication
without relying on read-only access to an unpublished GitHub release.

## Hosted evidence and root cause

Manual release run `31306939906` used `main` commit
`f39fafc72507c099dc4bf3af39ae497a1e8499a9` and established this boundary:

- Windows, Linux, macOS, release-input, and protected package/draft validation
  passed.
- The write-authorized job created the v1.3.1 draft, uploaded the ZIP and
  checksum, re-downloaded the stored ZIP, and verified SHA-256
  `45b8c37d18218e9d835d94399ccf8ce68dd742798be619135d0032c588657382`.
- The separate attestation job used the same repository, tag, archive name,
  and digest with `contents: read`, but `gh release download` returned
  `release not found`.
- GitHub's permission model allows Write, Maintain, and Admin roles to view
  draft releases; Read and Triage cannot. Explicit repository selection does
  not change that authorization boundary.

The current unpublished draft is release ID `367440347`, targeted at that main
commit, with no published release or v1.3.1 tag. Source work must not mutate it.
Deletion remains a separate hosted recovery action after the correction merges.

## Alternatives considered

### Selected: workflow-artifact handoff

Build once in a read-only job, upload the ZIP and checksum as a short-lived
workflow artifact, attest that exact ZIP in a read-only job, then have the
protected write job natively download and publish the same artifact. Verify the
ZIP digest after every transfer and again after release-asset storage.

This adds one reviewed action and an artifact boundary, but preserves the core
security property: no third-party or GitHub JavaScript action executes with
`contents: write`.

### Rejected: give attestation `contents: write`

This would expose release-write authority to `actions/attest`, undoing the
least-privilege objective that motivated the job split.

### Rejected: independent rebuilds

The add-on contents did not change between the first and second hosted release
attempts, yet their ZIP digests differed. The current Blender build is not
byte-reproducible across fresh checkouts, so independent build and publication
jobs cannot prove they handled the same bytes.

### Rejected: PAT or long-lived release token

Draft visibility still requires write-level authority, and a stored credential
would add secret rotation and compromise risk without improving isolation.

## Approved dependency

Add exactly one action:

```text
actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
```

This is official `actions/upload-artifact` v7.0.1. GitHub reports the pinned
commit as signature-verified. Its action manifest identifies GitHub as the
author and uses Node 24. The fixed hosted runners in this workflow support it.

Configure the upload with:

- constant artifact name `ams-release-package`;
- exact paths for the one version-derived AMS ZIP and `SHA256SUMS.txt`;
- `if-no-files-found: error`;
- `retention-days: 1`;
- `compression-level: 0` because the extension ZIP is already compressed;
- no overwrite and no hidden files.

Do not add `actions/download-artifact`. Both consumers use the already
installed GitHub CLI:

```powershell
gh run download $env:GITHUB_RUN_ID `
  --repo $env:GITHUB_REPOSITORY `
  --name $env:RELEASE_ARTIFACT_NAME `
  --dir $DownloadDirectory
```

The explicit run ID prevents selecting an artifact from another workflow run.

## Job architecture

### `release_package`: read-only producer

- Guard on manual dispatch, `main`, and public repository visibility.
- Depend on `validate` and `release_gate`.
- Run on `windows-2025` with `contents: read` only.
- Retain the unauthenticated native Git fetch of exact `GITHUB_SHA`, fixed
  Blender acquisition verification, fresh extension build, archive validation,
  strict release identity, and checksum generation.
- Expose validated version, tag, archive name, and lowercase ZIP SHA-256 as job
  outputs.
- Upload only the ZIP and checksum through the pinned action.
- Do not create a tag, draft, release, or release asset.

### `release_attestation`: read-only consumer

- Repeat the manual/main/public guards.
- Depend on `release_package`.
- Run on `windows-2025` with exactly `actions: read`, `contents: read`,
  `id-token: write`, and `attestations: write`.
- Give `GH_TOKEN` only to the native `gh run download` step.
- Download `ams-release-package` from exact `GITHUB_RUN_ID` and repository.
- Require the expected ZIP and checksum, reject unexpected extra AMS ZIPs, and
  verify the ZIP SHA-256 against the package job output.
- Run the existing full-SHA-pinned `actions/attest` with the verified ZIP as
  its sole subject.
- Never receive `contents: write` and never access a draft release.

### `release_publish`: protected write consumer

- Repeat the manual/main/public guards.
- Depend on both `release_package` and `release_attestation`.
- Run on `windows-2025` in the protected `release` environment with exactly
  `actions: read` and `contents: write`.
- Execute no `uses:` action.
- Give `GH_TOKEN` only to individual native `gh` steps.
- Download the exact current-run artifact with `gh run download`, then verify
  the ZIP SHA-256 and checksum identity before any release mutation.
- Refuse any existing v1.3.1 tag or release.
- Create the draft targeted at exact `GITHUB_SHA`, upload the handed-off ZIP
  and checksum, re-download the stored ZIP, and verify the same digest.
- Publish only after every earlier job and stored-asset check succeeds.

This job remains on Windows so the existing PowerShell release operations move
without a cross-platform rewrite.

## Data and failure flow

```text
validated main SHA
  -> release_package builds ZIP + checksum
  -> workflow artifact upload
  -> release_attestation downloads + hashes + attests ZIP
  -> release_publish downloads + hashes same ZIP
  -> create draft + upload exact ZIP/checksum
  -> download stored ZIP + hash again
  -> publish
```

No draft exists when packaging or attestation fails. A failure after draft
creation leaves an unpublished draft. No failure path publishes without a
successful attestation and matching digest.

## Policy change

Replace the old permanent rule that publication rebuilds from `main`. The new
rule is:

> The read-only release-package job builds once from the exact validated main
> commit. Attestation and protected publication independently download the same
> current-run workflow artifact and verify its producer-reported SHA-256.
> Publication uploads those exact bytes, re-downloads the stored ZIP, and
> verifies the same digest before publishing.

All other CI/CD security invariants remain unchanged.

## Tests and validation

Change workflow contracts test-first to prove:

- the action allowlist adds only the exact upload-artifact SHA;
- the producer is read-only and is the only job using upload-artifact;
- artifact name, exact paths, failure behavior, retention, and compression are
  fixed;
- both consumers use native `gh run download` with exact run ID, repository,
  name, and step-local token;
- both consumers have `actions: read` and no broader Actions permission;
- the attestation job retains its exact identity/attestation permissions and
  lacks `contents: write`;
- the protected write job contains no `uses:` action;
- release creation occurs only after attestation in the dependency/data flow;
- ZIP digest checks occur after both artifact downloads and after stored-release
  download;
- stable validation jobs, triggers, action pins, Blender trust checks, and
  ordinary version-independent archive discovery remain unchanged.

Run the focused workflow contracts RED then GREEN, all unit tests, full
headless Blender tests, source validation, and a clean single-ZIP build/archive
validation. Update permanent testing/security documentation and `docs/HANDOFF.md`.

Hosted acceptance after merge remains required: delete the failed draft with
separate authorization, dispatch 1.3.1, confirm artifact download and
attestation, confirm publication, and verify the downloaded release ZIP with
`gh attestation verify`.
