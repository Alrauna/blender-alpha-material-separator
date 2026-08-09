# Repository handoff

Updated: 2026-08-09

## Current objective

`codex/ci-release-artifact-handoff-1.3.1` is a topic branch from refreshed
`main` at `f39fafc72507c099dc4bf3af39ae497a1e8499a9`. Its bounded objective is to
replace the failed draft-release handoff with a short-lived workflow-artifact
handoff so version 1.3.1 can be attested without giving release-write authority
to the attestation action.

The user approved the architecture in conversation. The written design is in
`docs/superpowers/specs/2026-08-09-release-artifact-handoff-design.md`. No
workflow implementation has begun; the next lifecycle gate is user review of
that committed spec, followed by a test-first implementation plan.

## Hosted evidence and root cause

Manual release run `31306939906` used main commit
`f39fafc72507c099dc4bf3af39ae497a1e8499a9`:

- all ordinary validation and protected package/draft work passed;
- the release job built and validated the 1.3.1 ZIP, created a draft, uploaded
  both assets, re-downloaded the ZIP, and verified SHA-256
  `45b8c37d18218e9d835d94399ccf8ce68dd742798be619135d0032c588657382`;
- the separate attestation job selected the repository explicitly but
  `gh release download` still returned `release not found`;
- publication was skipped as designed.

The failure is an authorization boundary, not another repository-selection
bug. GitHub draft releases are visible to Write, Maintain, and Admin roles, but
the attestation job intentionally has only `contents: read`. Giving it write
authority would undo the least-privilege separation.

## Approved design

Build the release package once in a read-only `release_package` job and upload
the ZIP and checksum as a one-day workflow artifact named
`ams-release-package`. A read-only `release_attestation` job and the protected
write-authorized `release_publish` job independently download that exact
current-run artifact with native `gh run download` and verify the producer's
ZIP digest. Publication uploads those exact bytes, re-downloads the stored ZIP,
and verifies the digest again before publishing.

Add only the official upload action, pinned to v7.0.1 commit:

```text
actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
```

Do not add `actions/download-artifact`. The protected publication job must
continue to execute no `uses:` actions. Its native artifact download receives
`GH_TOKEN` only on that individual step. No draft is created until attestation
has succeeded.

This intentionally replaces the old rule that the publication job rebuilds
from main. The read-only package job builds once from exact `GITHUB_SHA`, and
both consumers verify and use the same workflow-artifact bytes.

## Current hosted state

Run `31306939906` left a second unpublished draft:

- release ID `367440347`;
- tag name `v1.3.1`, with no Git tag created;
- target `f39fafc72507c099dc4bf3af39ae497a1e8499a9`;
- ZIP asset ID `507365725`, 72,588 bytes, digest
  `sha256:45b8c37d18218e9d835d94399ccf8ce68dd742798be619135d0032c588657382`;
- checksum asset ID `507365726`, 101 bytes, digest
  `sha256:81feaeb17f72a6b049db11613fec78fc8feb08dfc88521234f46854bdf1e35dd`.

This branch must not mutate that draft. Its deletion requires separate explicit
authorization after the correction merges and before the next 1.3.1 dispatch.
Do not increment to 1.3.2 for this release-infrastructure failure.

## Validation state

The branch began from a clean `main`, and the unchanged baseline unit suite
passed all 121 tests. The design checkpoint changes documentation only. Its
placeholder/consistency review and `git diff --check` passed before commit.

Implementation must follow the approved design test-first. The final gate must
include focused workflow contracts, the full unit suite, complete headless
Blender suite, source validation, and a clean single-ZIP build/archive
validation. Hosted acceptance after merge must confirm artifact handoff,
attestation, publication, and `gh attestation verify` against the downloaded
release ZIP.

## Next action

Ask the user to review the committed written design. If approved, invoke the
writing-plans phase and prepare a detailed RED/GREEN implementation plan for
separate approval. Do not edit the workflow before both gates are complete.
