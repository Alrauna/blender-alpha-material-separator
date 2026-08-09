# Repository handoff

Updated: 2026-08-09

## Completed branch objective

`codex/ci-release-artifact-handoff-1.3.1` is based on refreshed `main` commit
`f39fafc72507c099dc4bf3af39ae497a1e8499a9`. Its bounded objective is complete:
replace the inaccessible draft-release handoff with a short-lived
workflow-artifact handoff so version 1.3.1 can receive build-provenance
attestation without granting release-write authority to the attestation action.

The workflow now has three release jobs:

- read-only `release_package` fetches exact `GITHUB_SHA` without credentials,
  builds and validates once, prepares the checksum, and uploads both files as
  `ams-release-package` for one day;
- `release_attestation` downloads that exact current-run artifact with
  `actions: read`, verifies the two-file set, checksum identity, and ZIP digest,
  then attests the verified ZIP without `contents: write`;
- protected `release_publish` independently downloads and verifies the same
  artifact, refuses an existing tag or release, creates the draft only after
  attestation, uploads the exact bytes, re-downloads and re-hashes the stored
  ZIP, then publishes. It has `contents: write` but executes no `uses:` action.

The only new action is the official upload action pinned to reviewed v7.0.1:

```text
actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
```

The existing attestation action remains pinned to:

```text
actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6
```

No `actions/download-artifact`, cache, setup action, package installer,
container, self-hosted runner, secret, external dependency, or network source
was added. Stable validation triggers, runners, names, Blender trust checks,
and version-independent ordinary ZIP discovery remain unchanged.

## Commits

- `22786ba` — approved release artifact handoff design checkpoint;
- `3ba925f` — approved RED/GREEN implementation plan checkpoint;
- `efa3448` — workflow artifact handoff and primary security contracts;
- `596adba` — permanent CI policy and operator documentation;
- `ce550d7` — review-driven exact permissions, file-set, and per-command
  repository contracts plus corrected upload-action wording;
- `df925ce` — per-step current-run artifact download binding contract.

The in-flight design and plan were removed at milestone closeout as required.
Git history retains both approved documents in `22786ba` and `3ba925f`.

## TDD and review evidence

Before the workflow edit, the upload-action allowlist contract failed because
the pinned action was absent. The expanded workflow module then failed five
new artifact-handoff contracts while all unrelated stable contracts continued
to pass. After implementation, all 22 workflow contracts and all 125 unit tests
passed.

The permanent documentation contract next failed because `docs/testing.md`
still described `release_draft`. After updating `AGENTS.md`, `PLAN.md`, and
`docs/testing.md`, the focused contract and all 125 unit tests passed.

Independent security review found no production-workflow defect, but used
in-memory mutations to prove four contract gaps. Before correction, tests
incorrectly accepted:

- removal of `--repo` from `gh release create`;
- disabling both exact two-file gates;
- adding `packages: write` to `release_publish`;
- removal of `--repo` specifically from the publisher's `gh run download`.

The first three mutations now each produce one focused test failure through
`ce550d7`; the fourth produces one focused failure through `df925ce`. The real
workflow remains 22/22 focused and 125/125 overall. Final focused re-review
reported no Critical or Important findings and assessed the branch ready for
closeout.

## Verification evidence

The fresh final local gate reported:

- workflow contract module: 22 passed;
- complete unit suite: 125 passed;
- complete headless Blender suite: exit 0 and
  `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`;
- Blender source validation: success;
- clean release build: exactly one
  `alpha_material_separator-1.3.1.zip`;
- archive size: 72,588 bytes;
- local archive SHA-256:
  `2f2f6d8e4de28cc5ed73776b4571ba9dbb0094824bddea889d3fab9bd51379bc`;
- Blender archive validation: success;
- `git diff --check`: no errors.

The archive is an ignored local verification output, not a release asset. Its
digest is not expected to equal an earlier build because Blender's extension
build is not byte-reproducible across fresh invocations.

Private-reference smoke, performance benchmarks, and installed interactive
material checks were not applicable because this branch changes no add-on
payload, resolver, rasterizer, classifier, cache, Preview, Apply, assignment,
or preservation behavior.

## Hosted state and recovery boundary

The failed hosted run `31306939906` and its unpublished draft remain untouched:

- release ID `367440347`;
- tag name `v1.3.1`, with no Git tag created;
- target `f39fafc72507c099dc4bf3af39ae497a1e8499a9`;
- ZIP asset ID `507365725`, 72,588 bytes, digest
  `sha256:45b8c37d18218e9d835d94399ccf8ce68dd742798be619135d0032c588657382`;
- checksum asset ID `507365726`, 101 bytes, digest
  `sha256:81feaeb17f72a6b049db11613fec78fc8feb08dfc88521234f46854bdf1e35dd`.

Nothing in this branch deletes that draft, creates a tag, or publishes a
release. Do not increment to 1.3.2 for this release-infrastructure failure.

## Next action

The branch is ready for pull-request preparation against `main`. After it
merges, separately obtain authorization to delete release ID `367440347`, then
dispatch 1.3.1. Hosted acceptance must confirm the artifact handoff,
attestation, exact-byte publication, and `gh attestation verify` against the
downloaded release ZIP. Do not claim hosted success before that run completes.
