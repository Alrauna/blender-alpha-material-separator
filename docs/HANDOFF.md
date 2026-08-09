# Repository handoff

Updated: 2026-08-09

## Current objective

`codex/fix-release-attestation-repo-context` is a topic branch from refreshed
`main` at `0e47fbad0bfa838c01d7f3af5aaa4a3b2d19ad34`. Its bounded objective is to
correct missing GitHub repository context in the no-checkout v1.3.1 release
jobs without changing the approved permissions or three-job architecture.

PR #16 merged the 1.3.1 attestation workflow into `main`. Manual release run
`31304598307` then established the first hosted result:

- all Windows, Linux, and macOS validation jobs passed;
- `release_draft` fetched the exact main commit, built and validated the ZIP,
  created an unpublished v1.3.1 draft, uploaded both assets, downloaded the
  stored ZIP, and verified its SHA-256;
- `release_attestation` failed in `Download and verify stored ZIP` before
  `actions/attest` ran;
- `release_publish` was skipped as designed.

## Root cause and correction

The attestation job intentionally has no checkout. Its command was:

```powershell
gh release download $env:RELEASE_TAG `
  --pattern $env:ARCHIVE_NAME `
  --dir $DownloadDirectory
```

Without `--repo`, GitHub CLI tried to infer the repository from a local Git
remote and reported:

```text
failed to run git: fatal: not a git repository (or any of the parent directories): .git
```

The test-first attestation correction adds only:

```powershell
--repo $env:GITHUB_REPOSITORY `
```

The runner-provided value identifies the current `owner/repository`; it enters
PowerShell through the environment rather than expression interpolation. The
change adds no checkout, action, dependency, token, permission, trigger, runner,
artifact transfer, or network source. Attestation permissions remain exactly
`contents: read`, `id-token: write`, and `attestations: write`.

Independent review then found that `release_publish` is also a no-checkout job
and its `gh release edit` command had the same implicit Git dependency. The
user approved expanding the plan before another hosted attempt. Publication now
also supplies:

```powershell
--repo $env:GITHUB_REPOSITORY `
```

The permanent regression requires both no-checkout release sections to remain
checkout-free and to pass this explicit repository selector.

Branch commits before closeout:

- `041be6d` — approved design and test-first implementation plan;
- `b5f23d1` — focused attestation regression and one-line download correction;
- `a34de34` — approved plan expansion, publication regression, and one-line
  publish correction.

## TDD and validation evidence

The initial focused contract first failed because the attestation section
lacked `--repo $env:GITHUB_REPOSITORY`; its no-checkout assertion already
passed. After correcting download, the expanded
`test_no_checkout_release_commands_select_repository_explicitly` contract
failed because the publish section lacked the same selector. After the second
one-line workflow edit:

- focused regression: 1 passed;
- complete workflow contract module: 18 passed;
- complete unit suite: 121 passed;
- complete headless Blender suite exited 0 and ended
  `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`;
- Blender source validation succeeded;
- the verified `.packaged-releases` directory was cleared of ZIPs, then built
  exactly one `alpha_material_separator-1.3.1.zip` at 72,588 bytes;
- Blender archive validation succeeded for that discovered ZIP.

Initial independent review reported no Critical issue and one Important issue:
the downstream no-checkout publish command would fail for the same reason. That
finding was addressed test-first in `a34de34`. Focused re-review of the complete
expanded diff reported no Critical, Important, or Minor findings and assessed
the workflow and tests as ready after milestone closeout.

Private-reference smoke, performance benchmarks, and installed interactive
material-workflow checks were not required because this branch changes no
resolver, rasterizer, classifier, cache, Preview, Apply, packaging payload, or
preservation behavior.

## Hosted state and recovery boundary

The failed release remains an unpublished v1.3.1 draft targeted at
`0e47fbad0bfa838c01d7f3af5aaa4a3b2d19ad34`. It contains:

- `alpha_material_separator-1.3.1.zip`, 72,588 bytes, GitHub-reported digest
  `sha256:0918c2282ba778e30315fc3d2656a79b5de76bd3ad92fe5959c73e22b66b6313`;
- `SHA256SUMS.txt`, 101 bytes.

No v1.3.1 tag exists and nothing was published. This branch does not mutate
that draft. After the correction merges, retrying the strict release workflow
requires separate explicit authorization to delete the failed draft first;
the workflow correctly refuses an existing release identity.

The next manual run must still confirm:

- the read-only attestation token can download the private draft asset when the
  repository is selected explicitly;
- the pinned action creates provenance for the exact downloaded ZIP;
- failed attestation continues to leave the release unpublished;
- after publication, the downloaded asset passes the version-neutral
  `gh attestation verify` command documented in `docs/testing.md`.

## Next action

The branch is ready for final review and pull-request preparation. Pushing or
opening a draft pull request requires separate user authorization. Do not rerun
the release until this correction merges and deletion of the failed draft is
separately authorized.
