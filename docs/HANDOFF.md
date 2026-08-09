# Repository handoff

Updated: 2026-08-09

## Current objective

`codex/ci-release-attestation-1.3.1` is a topic branch from refreshed `main` at
`fb80d9d8e8b793e239a9b879172ae2dbe165000a`. Its bounded objective is to add
least-privilege GitHub build-provenance attestation for the exact extension ZIP
stored on a draft release and to prepare version 1.3.1.

The user approved the three-job security design in conversation:

1. a protected write-authorized job creates, uploads, downloads, and re-hashes
   the draft release ZIP without executing an action;
2. a read-only attestation job independently downloads and hashes that ZIP,
   then runs the full-SHA-pinned `actions/attest` action with only
   `contents: read`, `id-token: write`, and `attestations: write`;
3. a protected write-authorized job publishes only after attestation succeeds,
   without executing an action.

The written design is
`docs/superpowers/specs/2026-08-09-release-artifact-attestation-design.md`.
The user approved it, and the test-first implementation plan is
`docs/superpowers/plans/2026-08-09-release-artifact-attestation.md`. The plan is
awaiting explicit user review before execution. No CI or version file has been
changed.

Plan self-review corrected one documentation inconsistency without changing the
approved security architecture: permanent testing documentation will discover
exactly one `alpha_material_separator-*.zip` for `gh attestation verify` rather
than hardcoding 1.3.1. The manifest and README remain the only permanent
version-bearing product files.

## Verified repository state

Before branch creation on 2026-08-09:

- the worktree was clean on `main`;
- local `main` and refreshed `origin/main` both pointed to `fb80d9d`;
- pull request #15 was merged and its remote topic branch was deleted;
- GitHub reported v1.3.0 as the latest release, with v1.2.0 also published;
- the previous handoff's claims that PR #15 was open, main was older, and
  versions 1.2.0/1.3.0 were unpublished were stale and were not used as facts;
- the complete Blender-Python unit baseline passed 117 tests.

The current workflow remains unchanged on this design checkpoint. It has one
protected Windows release job with `contents: write`, native unauthenticated
exact-SHA Git fetch, draft-first asset upload, stored-ZIP download and hash
verification, and final publication. Existing workflow contract tests
deliberately reject any additional action and therefore must change test-first
with the approved job split.

## Approved constraints

- Attest only the downloaded extension ZIP, not `SHA256SUMS.txt` or routine CI
  builds.
- Pin `actions/attest` v4.2.2 to
  `1e69f48acb82d1966a394da916b4c1698aa569d6`.
- Never run the action in a job with `contents: write`.
- Keep default workflow permissions at `contents: read` and keep `GH_TOKEN`
  scoped to individual native `gh` steps.
- Preserve manual dispatch, `main` and public-repository guards, the protected
  `release` environment, exact-source fetch, draft-first behavior, hash
  verification, and stable Windows/Linux/macOS validation jobs.
- Change the extension version from 1.3.0 to 1.3.1 only in
  `addon/blender_manifest.toml` and `README.md`; API 1.3 remains unchanged.
- Do not publish, tag, push, create a pull request, or change repository
  settings without separate authorization.

## Hosted uncertainties

The first separately authorized manual release dispatch must prove that a job
whose token has only `contents: read` can download the private draft-release
asset. It must also record whether the two write-authorized jobs referencing
the protected `release` environment require one or multiple approvals. These
cannot be established by pull-request validation.

If either assumption fails, return to design review. Do not move the attest
action into a `contents: write` job or introduce a long-lived release token as
an unreviewed workaround.

## Next action

The user should review and explicitly approve the test-first implementation
plan. After approval, invoke `superpowers:executing-plans` and execute it inline
with its RED/GREEN checks and commit boundaries. Do not edit the workflow,
tests, manifest, or README before plan approval.
