# Release Artifact Attestation Design

**Status:** Approved in conversation on 2026-08-09; awaiting written-spec
review.

## Objective

Prepare version 1.3.1 with GitHub build-provenance attestation support for the
downloadable Alpha Material Separator extension ZIP. Preserve the existing
fail-closed draft-release workflow while ensuring that the attestation action
never runs in a job whose `GITHUB_TOKEN` has `contents: write`. Publishing the
prepared release remains a separately authorized operation.

The release version changes from 1.3.0 to 1.3.1 in the manifest and README.
The public integration API remains API 1.3 because this change does not alter
addon runtime behavior or its published API surface.

## Verified Starting Point

Before this design branch was created, local `main` and refreshed
`origin/main` both pointed to `fb80d9d8e8b793e239a9b879172ae2dbe165000a`.
Pull request #15 was merged, its remote topic branch was deleted, and GitHub
reported v1.3.0 as the latest published release. The complete unit baseline
passed 117 tests on the new branch.

The current manual release path is one protected Windows job with
`contents: write`. It fetches the exact public `GITHUB_SHA` without
credentials, rebuilds and validates the extension ZIP, writes
`SHA256SUMS.txt`, refuses an existing tag or release, creates a draft, uploads
the assets, downloads and re-hashes the stored ZIP, and publishes the verified
draft.

## Scope

### In scope

- Attest only the exact extension ZIP downloaded back from the GitHub draft
  release.
- Use GitHub's `actions/attest` action pinned to the reviewed full commit
  `1e69f48acb82d1966a394da916b4c1698aa569d6` (v4.2.2).
- Split draft creation, attestation, and publication into separate jobs so the
  action receives only read and attestation permissions.
- Preserve manual dispatch, exact version validation, `main` and public
  repository guards, the protected `release` environment, exact-source fetch,
  draft-first publication, stored-asset re-hashing, and individual-step
  `GH_TOKEN` exposure.
- Add deterministic workflow contract coverage and consumer verification
  documentation.
- Increment the extension version to 1.3.1 in the manifest and README.

### Out of scope

- Publishing, tagging, or creating the 1.3.1 release during implementation.
- Retroactively attesting v1.3.0 or older releases.
- Attesting routine pull-request or push validation ZIPs.
- Attesting `SHA256SUMS.txt`, generated source archives, documentation, or
  individual files inside the extension ZIP.
- SBOM generation, package registries, workflow artifact transfer, caches,
  setup actions, containers, self-hosted runners, or new network sources.
- Changing addon behavior, API 1.3, material analysis, assignment, or Blender
  compatibility.
- Changing repository settings or environment protection rules.

## Architecture

The existing `release` job becomes three jobs. The existing `validate` and
`release_gate` jobs remain unchanged except for dependency references required
by the renamed draft job.

### 1. Draft release job

The `release_draft` job retains the existing Windows runner, timeout, manual
release guards, `needs: [validate, release_gate]`, protected `release`
environment, and `contents: write` permission. It contains no `uses:` step.

It performs the existing release work through stored-ZIP verification, but it
does not publish the draft. It exposes four non-secret job outputs derived from
the already validated release identity and archive:

- `version`: strict `X.Y.Z` manifest version;
- `tag`: `v` plus the validated version;
- `archive_name`: the exact versioned AMS ZIP basename;
- `sha256`: lowercase SHA-256 of the locally built ZIP, already confirmed
  against the downloaded draft asset before the job succeeds.

The job retains unauthenticated native Git for fetching the exact public
`GITHUB_SHA`. `GH_TOKEN` remains present only on the GitHub CLI steps that
refuse an existing release, create the draft, upload the assets, and download
the stored ZIP.

### 2. Attestation job

The `release_attestation` job depends on `release_draft`, repeats the manual
dispatch, `main`, and public-repository guards, and uses a GitHub-hosted runner
with only these permissions:

```yaml
permissions:
  contents: read
  id-token: write
  attestations: write
```

It does not check out source and does not receive `contents: write`. A shell
step receives the validated tag, archive name, and expected digest through
environment variables, downloads the exact ZIP from the draft release into a
fresh runner-temporary directory using `gh release download`, and verifies the
download with PowerShell's native `Get-FileHash -Algorithm SHA256`. `GH_TOKEN`
is scoped to that download step and has `contents: read` only.

After the independent hash comparison succeeds, the job runs exactly this
pinned action:

```yaml
- name: Attest stored extension ZIP
  uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
  with:
    subject-path: '${{ runner.temp }}/downloaded-release/${{ needs.release_draft.outputs.archive_name }}'
```

The subject must resolve to that one downloaded ZIP. It must not use a wildcard,
the pre-upload build path, or the checksum file. The generated Sigstore bundle
is stored through GitHub's attestation service; it is not added as another
release asset.

### 3. Publication job

The `release_publish` job depends on successful completion of both
`release_draft` and `release_attestation`. It repeats the manual dispatch,
`main`, and public-repository guards, uses the protected `release` environment,
and has `contents: write`. It contains no `uses:` step.

Its only mutation is the existing native GitHub CLI publication command:

```powershell
gh release edit $env:RELEASE_TAG --draft=false
```

The validated tag is passed through an environment variable rather than
interpolated into shell source. `GH_TOKEN` is exposed only to this step. If any
upstream build, upload, download, hash, or attestation operation fails, this
job does not run and the release remains a draft.

## Security Properties

- Workflow-level defaults remain `contents: read`.
- Only the protected manual draft and publication jobs receive
  `contents: write`, and neither job executes an action.
- The attestation action receives `contents: read`, `id-token: write`, and
  `attestations: write`, never `contents: write`.
- Every action remains allowlisted and pinned to a reviewed full commit SHA.
- No action receives a release credential through `GH_TOKEN`; all such
  variables remain scoped to individual native `gh` steps.
- Release inputs and job outputs enter shell steps through environment
  variables. The strict release identity continues to reject anything outside
  `X.Y.Z` and the exact manifest version.
- Publication is ordered after verification of the GitHub-stored ZIP and its
  provenance attestation.
- A provenance attestation proves the artifact's workflow identity and digest;
  it is not a claim that the artifact is vulnerability-free.

## Failure and Recovery Behavior

- Failure before draft creation leaves no tag or release.
- Failure after draft creation leaves an unpublished draft and never publishes
  an unattested ZIP.
- A transient attestation or publication failure can use GitHub's failed-job
  rerun path without rerunning the successful draft job. If GitHub instead
  reruns the draft job, the existing tag/release refusal fails closed rather
  than overwriting the draft.
- Deleting a failed draft or tag remains a deliberate maintainer action outside
  this workflow and outside implementation authorization.
- The first hosted dispatch must confirm that the read-only attestation job can
  access the draft asset and record whether two jobs referencing the protected
  `release` environment require one or multiple approvals. A failure changes
  operational assumptions and returns to design review; it must not be worked
  around by granting the action `contents: write`.

## Versioning and Documentation

Only `addon/blender_manifest.toml` and `README.md` carry the extension release
version. They change from 1.3.0 to 1.3.1. Existing derived-version tests remain
the authority that no third file hardcodes the extension version.

`docs/testing.md` will document the three-job release boundary and a
version-neutral online consumer verification command:

```powershell
$Archives = @(Get-ChildItem -Filter 'alpha_material_separator-*.zip' -File)
if ($Archives.Count -ne 1) { throw "Expected one AMS ZIP." }
gh attestation verify $Archives[0].FullName `
  --repo Alrauna/blender-alpha-material-separator
```

The documentation must state that 1.3.1 is not published merely because the
workflow and manifest are prepared. Live verification remains pending until a
separately authorized release succeeds.

## Test-First Validation

The implementation begins by changing
`tests/unit/test_ci_workflow_contract.py` so the new contract fails against the
current single-job workflow. The focused regression will require:

- exactly two pinned checkout uses and one exact pinned attest use;
- no action in either `contents: write` job;
- exact attestation-job permissions and absence of `contents: write` there;
- manual, `main`, public-repository, dependency, and protected-environment
  gates on every mutating release job;
- exact ordering from draft creation through stored-ZIP hashing, attestation,
  and publication;
- the downloaded ZIP as the sole attestation subject;
- native digest comparison before attestation;
- validated outputs passed into shell through environment variables;
- `GH_TOKEN` confined to individual `gh` steps;
- preservation of exact-source unauthenticated Git fetch and the existing
  validation matrix.

The version bump uses the existing manifest, README, and API contract tests;
no new hardcoded-version test is needed. Documentation contracts will require
the attestation verification command and least-privilege job split.

After the focused RED/GREEN cycle, the implementation change gate is:

1. focused CI workflow, manifest, README, and API contract tests;
2. complete unit suite;
3. complete headless Blender suite;
4. Blender extension source validation;
5. clean build producing exactly one 1.3.1 AMS ZIP;
6. validation of that discovered ZIP;
7. `git diff --check` and complete branch-diff review.

Private-reference smoke, performance benchmarks, and interactive material
workflow checks are not required because the change does not affect resolver,
rasterization, classification, caching, Preview, Apply, or preservation
behavior. The future 1.3.1 release still requires the repository's separate
release gate and explicit publication approval.

## Acceptance Criteria

- Pull-request and push validation retain all three stable Blender 5.2 jobs.
- Manual release preparation builds version 1.3.1 from the exact validated
  `main` commit.
- The GitHub-stored ZIP is re-hashed before attestation.
- `actions/attest` runs only with read, OIDC, and attestation permissions.
- Publication cannot run unless the exact stored ZIP was attested.
- Any failure leaves no published unattested release.
- Consumers can verify the published ZIP with `gh attestation verify` after a
  separately authorized hosted release.
- No unrelated runtime, dependency, network, repository-setting, or packaging
  behavior changes.
