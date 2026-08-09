# Release Artifact Attestation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task. Repository
> policy makes inline execution the default; use
> superpowers:subagent-driven-development only after an explicit user request.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare Alpha Material Separator 1.3.1 and make its protected manual
release workflow attest the exact ZIP downloaded from the draft release without
giving the attestation action `contents: write`.

**Architecture:** Split the current write-authorized release job into a
write-authorized draft job, a read-only attestation job, and a write-authorized
publication job. The draft job exposes validated identity and digest outputs;
the attestation job downloads and independently hashes the stored ZIP before a
full-SHA-pinned `actions/attest` call; publication depends on successful
attestation.

**Tech Stack:** GitHub Actions YAML, PowerShell on GitHub-hosted Windows runners,
GitHub CLI, GitHub artifact attestations/Sigstore, Python 3.13 `unittest`,
Blender 5.2.0 extension tooling.

## Global Constraints

- Branch: `codex/ci-release-attestation-1.3.1`, based on refreshed `main` at
  `fb80d9d8e8b793e239a9b879172ae2dbe165000a`.
- Extension identity remains `alpha_material_separator`; Blender minimum remains
  `5.2.0`; license remains `GPL-3.0-or-later`.
- Extension version changes from `1.3.0` to `1.3.1`; public API version remains
  `1.3`.
- Attest only the exact extension ZIP downloaded from the draft release.
- Pin `actions/attest` v4.2.2 to
  `1e69f48acb82d1966a394da916b4c1698aa569d6`.
- Never run an action in a job with `contents: write`.
- Default workflow permission remains `contents: read`; only protected manual
  draft and publication jobs receive `contents: write`.
- `GH_TOKEN` remains scoped to individual native `gh` steps.
- Preserve manual dispatch, strict `X.Y.Z` validation, `main` and public-repo
  guards, protected `release` environment, exact unauthenticated source fetch,
  draft-first publication, stored-ZIP hash verification, and stable
  Windows/Linux/macOS validation jobs.
- Add no cache, workflow artifact transfer, setup action, container,
  self-hosted runner, package registry, SBOM, dependency, trigger, permission,
  or network source beyond the approved attestation API/action.
- Do not push, open a pull request, tag, publish a release, or change repository
  settings without separate user approval.
- Execute production changes test-first. Stop for design review if a finding
  changes the approved job boundary, credential model, artifact subject,
  release guards, or hosted assumptions.

## File Structure

- Modify `.github/workflows/ci.yml`: split the release data flow into draft,
  attestation, and publication jobs and add the pinned attestation action.
- Modify `tests/unit/test_ci_workflow_contract.py`: encode exact action,
  permission, token, subject, dependency, guard, and ordering contracts.
- Modify `docs/testing.md`: document the least-privilege job split, provenance
  meaning, consumer verification, and hosted acceptance still pending.
- Modify `addon/blender_manifest.toml`: set extension version `1.3.1`.
- Modify `README.md`: keep the user-facing version and ZIP name equal to the
  manifest.
- Modify `docs/HANDOFF.md`: record implementation status, verification evidence,
  and hosted release checks that remain pending.
- Delete at milestone completion:
  `docs/superpowers/specs/2026-08-09-release-artifact-attestation-design.md` and
  `docs/superpowers/plans/2026-08-09-release-artifact-attestation.md`; their
  committed history retains the approved wording.

---

### Task 1: Enforce and implement the least-privilege release job split

**Files:**

- Modify: `tests/unit/test_ci_workflow_contract.py:12-233`
- Modify: `.github/workflows/ci.yml:121-272`

**Interfaces:**

- Consumes: existing `scripts/ci.py prepare-release` outputs `version`, `tag`,
  `archive_name`, and `sha256`; existing manual `inputs.version`; existing
  `validate` and `release_gate` jobs.
- Produces: `release_draft` job outputs named `version`, `tag`, `archive_name`,
  and `sha256`; `release_attestation` dependency and provenance; final
  `release_publish` dependency. No Python API changes.

- [ ] **Step 1: Add focused contract tests that describe the missing job
  isolation**

Add the exact action identity beside `CHECKOUT_SHA`:

```python
ATTEST_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"
```

Add these focused tests without first changing the workflow:

```python
def test_release_attestation_is_isolated_from_content_writes(self) -> None:
    for marker in (
        "\n  release_draft:\n",
        "\n  release_attestation:\n",
        "\n  release_publish:\n",
    ):
        self.assertIn(marker, self.text)

    draft = self.text.split("\n  release_draft:\n", 1)[1].split(
        "\n  release_attestation:\n", 1
    )[0]
    attestation = self.text.split("\n  release_attestation:\n", 1)[1].split(
        "\n  release_publish:\n", 1
    )[0]
    publish = self.text.split("\n  release_publish:\n", 1)[1]

    self.assertIn("environment: release", draft)
    self.assertIn("permissions:\n      contents: write", draft)
    self.assertNotIn("uses:", draft)
    self.assertEqual(
        re.findall(r"^\s{4}permissions:\n(?:^\s{6}.+\n?)+", attestation,
                   re.MULTILINE),
        [
            "    permissions:\n"
            "      contents: read\n"
            "      id-token: write\n"
            "      attestations: write\n"
        ],
    )
    self.assertNotIn("contents: write", attestation)
    self.assertIn(f"actions/attest@{ATTEST_SHA}", attestation)
    self.assertIn("environment: release", publish)
    self.assertIn("permissions:\n      contents: write", publish)
    self.assertNotIn("uses:", publish)

def test_stored_zip_is_verified_attested_then_published(self) -> None:
    expected_subject = (
        "subject-path: '${{ runner.temp }}/downloaded-release/"
        "${{ needs.release_draft.outputs.archive_name }}'"
    )
    for text in (
        "Get-FileHash -LiteralPath $Archive -Algorithm SHA256",
        "$Actual -ne $env:EXPECTED_SHA256",
        expected_subject,
    ):
        self.assertIn(text, self.text)

    positions = [
        self.text.index("gh release create"),
        self.text.index("gh release upload"),
        self.text.index("gh release download"),
        self.text.index("scripts/ci.py verify-file"),
        self.text.index("Get-FileHash -LiteralPath $Archive -Algorithm SHA256"),
        self.text.index(f"actions/attest@{ATTEST_SHA}"),
        self.text.index("gh release edit"),
    ]
    self.assertEqual(positions, sorted(positions))
    self.assertEqual(self.text.count("subject-path:"), 1)
```

Keep these tests text-based like the existing security contracts. Do not add a
YAML parser dependency.

- [ ] **Step 2: Run the focused tests and capture the expected RED result**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_release_attestation_is_isolated_from_content_writes `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_stored_zip_is_verified_attested_then_published `
  -v
```

Expected: both tests fail because the current workflow has one `release` job
and no `actions/attest` use.

- [ ] **Step 3: Split the release workflow with the smallest credential-safe
  change**

Rename the current `release` job to `release_draft`. Preserve its current
guards, Windows runner, timeout, protected environment, `contents: write`,
exact-source fetch, build, validation, identity preparation, existing-release
refusal, draft creation, upload, download, and stored-ZIP verification. Add
these job outputs immediately after `permissions`:

```yaml
    outputs:
      version: ${{ steps.release.outputs.version }}
      tag: ${{ steps.release.outputs.tag }}
      archive_name: ${{ steps.release.outputs.archive_name }}
      sha256: ${{ steps.release.outputs.sha256 }}
```

Remove only the existing `Publish verified draft` step from this renamed job.
Do not add any `uses:` step to it.

Append the attestation job exactly at the job level:

```yaml
  release_attestation:
    name: Attest stored release ZIP
    if: >-
      github.event_name == 'workflow_dispatch' &&
      github.ref == 'refs/heads/main' &&
      github.event.repository.visibility == 'public'
    needs: [release_draft]
    runs-on: windows-2025
    timeout-minutes: 10
    permissions:
      contents: read
      id-token: write
      attestations: write
    env:
      RELEASE_TAG: ${{ needs.release_draft.outputs.tag }}
      ARCHIVE_NAME: ${{ needs.release_draft.outputs.archive_name }}
      EXPECTED_SHA256: ${{ needs.release_draft.outputs.sha256 }}
    steps:
      - name: Download and verify stored ZIP
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          $DownloadDirectory = '${{ runner.temp }}/downloaded-release'
          New-Item -ItemType Directory -Path $DownloadDirectory | Out-Null
          gh release download $env:RELEASE_TAG `
            --pattern $env:ARCHIVE_NAME `
            --dir $DownloadDirectory
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not download the draft release ZIP for attestation.'
          }
          $Archive = Join-Path $DownloadDirectory $env:ARCHIVE_NAME
          $Actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
          $Actual = $Actual.ToLowerInvariant()
          if ($Actual -ne $env:EXPECTED_SHA256) {
            throw 'Draft release ZIP does not match the verified build digest.'
          }

      - name: Attest stored extension ZIP
        uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2
        with:
          subject-path: '${{ runner.temp }}/downloaded-release/${{ needs.release_draft.outputs.archive_name }}'
```

Append the publication job:

```yaml
  release_publish:
    name: Publish attested release
    if: >-
      github.event_name == 'workflow_dispatch' &&
      github.ref == 'refs/heads/main' &&
      github.event.repository.visibility == 'public'
    needs: [release_draft, release_attestation]
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    environment: release
    permissions:
      contents: write
    env:
      RELEASE_TAG: ${{ needs.release_draft.outputs.tag }}
    steps:
      - name: Publish verified and attested draft
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release edit $env:RELEASE_TAG --draft=false
```

Keep `environment: release` on `release_draft` as well. Do not interpolate job
outputs directly into shell source.

- [ ] **Step 4: Update the existing workflow contracts for the new job names
  without weakening them**

Make these exact adaptations in `test_ci_workflow_contract.py`:

- `test_no_unapproved_actions_or_execution_surfaces` expects
  `[f"actions/checkout@{CHECKOUT_SHA}"] * 2 +
  [f"actions/attest@{ATTEST_SHA}"]`.
- Every split on `"\n  release:\n"` selects the precise new section it needs:
  `release_draft` for source fetch/build/draft checks,
  `release_attestation` for the action and read token, and `release_publish`
  for final publication.
- `test_release_is_manual_main_public_and_environment_gated` checks all three
  release sections for the three guards, checks the two write jobs for
  `environment: release`, checks draft dependencies
  `needs: [validate, release_gate]`, and checks publication dependencies
  `needs: [release_draft, release_attestation]`.
- `test_dispatch_contexts_never_enter_shell_source` continues checking the
  expression-level guards and verifies the three job-output values enter shell
  through `env`, never inside a `run:` expression.
- Rename `test_release_is_draft_first_and_rehashes_downloaded_asset` to
  `test_release_is_draft_first_rehashes_attests_and_publishes`; retain the
  GraphQL refusal, `SHA256SUMS.txt`, draft, upload, download, verify-file, and
  publication assertions, and add the native re-hash and attest positions.
- Rename `test_write_token_is_scoped_to_release_and_gh_steps` to
  `test_tokens_and_permissions_are_scoped_to_release_steps`. Assert exactly two
  `contents: write` occurrences, only in draft/publish; assert the attestation
  permission block exactly; assert `GH_TOKEN` occurs four times in draft, once
  in attestation, once in publish, and every occurrence is
  `${{ github.token }}`.
- Preserve the two checkout count, `persist-credentials: false`, forbidden
  execution surfaces, exact-source fetch, version-independent validation ZIP,
  build-directory, and release-input interpolation assertions.

Do not relax an assertion merely because the job split moved text.

- [ ] **Step 5: Run focused GREEN tests, then the entire workflow contract
  module**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_release_attestation_is_isolated_from_content_writes `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_stored_zip_is_verified_attested_then_published `
  -v

& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest tests.unit.test_ci_workflow_contract -v
```

Expected: focused tests pass, followed by the complete workflow contract module
passing with no skipped or weakened security check.

- [ ] **Step 6: Review and commit the isolated CI unit**

Run:

```powershell
git diff --check
git diff -- .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py
git add -- .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py
git diff --cached --check
git diff --cached
git commit -m "ci: attest stored release artifacts"
```

Confirm the staged diff contains only the job split and its contract tests.

---

### Task 2: Prepare version 1.3.1 and document provenance verification

**Files:**

- Modify: `tests/unit/test_ci_workflow_contract.py:194-233`
- Modify: `docs/testing.md:36-88`
- Modify: `addon/blender_manifest.toml:4`
- Modify: `README.md:22-28`

**Interfaces:**

- Consumes: manifest-derived `EXTENSION_VERSION`, README contract derived from
  the manifest, the three release jobs from Task 1.
- Produces: installable version `1.3.1`, version-matched README download name,
  documented `gh attestation verify` consumer command. API version remains
  `1.3`.

- [ ] **Step 1: Add the documentation contract before changing documentation**

Extend `test_ci_security_and_rollout_are_documented` so `docs/testing.md` must
contain all of these exact strings:

```python
for text in (
    "actions/attest",
    "1e69f48acb82d1966a394da916b4c1698aa569d6",
    "gh attestation verify",
    "release_draft",
    "release_attestation",
    "release_publish",
    "contents: read",
    "id-token: write",
    "attestations: write",
):
    self.assertIn(text, testing)
```

- [ ] **Step 2: Run the documentation contract and capture RED**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Expected: FAIL because `docs/testing.md` does not yet describe attestation.

- [ ] **Step 3: Document the three-job boundary and verification command**

In `docs/testing.md`'s GitHub Actions CI/CD section, replace the single-job
publication paragraph with concise text that states:

````markdown
Manual dispatch requires a strict `X.Y.Z` version. Publication additionally
requires `main`, a public repository, successful Windows, Linux, and macOS
validation, and the protected `release` environment. `release_draft` rebuilds
from an unauthenticated exact-SHA fetch, creates a draft, uploads the ZIP and
`SHA256SUMS.txt`, downloads the stored ZIP, and verifies its digest. It has
`contents: write` and executes no action.

`release_attestation` downloads and independently hashes that exact stored ZIP,
then runs
`actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`
(v4.2.2) with only `contents: read`, `id-token: write`, and
`attestations: write`. `release_publish` has `contents: write`, executes no
action, and publishes only after attestation succeeds. A failed build, upload,
download, digest check, or attestation leaves an unpublished draft.

After downloading a published extension ZIP, discover exactly one AMS archive
and verify that its digest and provenance are bound to this repository's
release workflow:

```powershell
$Archives = @(Get-ChildItem -Filter 'alpha_material_separator-*.zip' -File)
if ($Archives.Count -ne 1) { throw "Expected one AMS ZIP." }
gh attestation verify $Archives[0].FullName `
  --repo Alrauna/blender-alpha-material-separator
```

An attestation identifies the source workflow and artifact digest; it does not
claim that the artifact is vulnerability-free. Live verification of 1.3.1 and
read-only access to a draft asset remain pending until publication is separately
authorized.
````

Retain the existing exact-fetch, token isolation, draft-first hash verification,
release guard, and no-workflow-artifact documentation. Remove wording that
incorrectly describes publication as one job.

- [ ] **Step 4: Use the existing derived-version test as the RED check for the
  1.3.1 README update**

Change only this manifest line first:

```toml
version = "1.3.1"
```

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_readme_contract.ReadmeContractTests.test_current_release_identity_is_documented `
  -v
```

Expected: FAIL because README still names version 1.3.0 and its ZIP.

- [ ] **Step 5: Make the minimum README version update and run focused GREEN**

Change only these two README strings:

```markdown
Version 1.3.1 targets Blender 5.2 LTS.
```

```markdown
1. Download `alpha_material_separator-1.3.1.zip`. Do not unzip it.
```

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_readme_contract.ReadmeContractTests.test_current_release_identity_is_documented `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  tests.unit.test_manifest `
  tests.unit.test_api_contract `
  -v
```

Expected: all selected tests pass; API payloads still report API `1.3`, and the
derived extension version is `1.3.1`.

- [ ] **Step 6: Review and commit the version/documentation unit**

Run:

```powershell
git diff --check
git diff -- tests/unit/test_ci_workflow_contract.py docs/testing.md `
  addon/blender_manifest.toml README.md
git add -- tests/unit/test_ci_workflow_contract.py docs/testing.md `
  addon/blender_manifest.toml README.md
git diff --cached --check
git diff --cached
git commit -m "chore: prepare attested release 1.3.1"
```

Confirm no permanent product document other than the README hardcodes the new
extension version.

---

### Task 3: Run the complete gate, review the branch, and close the milestone

**Files:**

- Modify: `docs/HANDOFF.md`
- Delete:
  `docs/superpowers/specs/2026-08-09-release-artifact-attestation-design.md`
- Delete:
  `docs/superpowers/plans/2026-08-09-release-artifact-attestation.md`

**Interfaces:**

- Consumes: completed Task 1 workflow/contracts and Task 2 version/docs.
- Produces: verified review-ready branch and an accurate immediate handoff.
  Hosted draft download, environment approval behavior, actual attestation, and
  live consumer verification remain explicitly pending.

- [ ] **Step 1: Run focused and complete unit validation**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_ci_workflow_contract `
  tests.unit.test_readme_contract tests.unit.test_manifest `
  tests.unit.test_api_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: both commands exit 0 with no failure or error. Record the exact test
counts in `docs/HANDOFF.md`; do not reuse the 117-test baseline count.

- [ ] **Step 2: Run the complete headless Blender and source-validation gates**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Blender52 --factory-startup --command extension validate addon
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Expected: headless suite ends with
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`; source validation reports success.

- [ ] **Step 3: Build and validate exactly one version 1.3.1 archive**

First inspect the exact cleanup target:

```powershell
$RepositoryRoot = (Resolve-Path '.').Path
New-Item -ItemType Directory -Force '.packaged-releases' | Out-Null
$ReleaseDirectory = (Resolve-Path '.packaged-releases').Path
if ((Split-Path -Parent $ReleaseDirectory) -ne $RepositoryRoot) {
  throw 'Release output escaped the repository.'
}
Get-ChildItem -LiteralPath $ReleaseDirectory -Filter '*.zip' -File
```

Then run the ordinary packaging gate:

```powershell
Get-ChildItem -LiteralPath $ReleaseDirectory -Filter '*.zip' -File |
  Remove-Item
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir $ReleaseDirectory
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Archives = @(Get-ChildItem -LiteralPath $ReleaseDirectory `
  -Filter 'alpha_material_separator-*.zip' -File)
if ($Archives.Count -ne 1) {
  throw "Expected one AMS ZIP, found $($Archives.Count)."
}
if ($Archives[0].Name -ne 'alpha_material_separator-1.3.1.zip') {
  throw "Unexpected archive name: $($Archives[0].Name)"
}
& $Blender52 --factory-startup --command extension validate `
  $Archives[0].FullName
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Expected: one `alpha_material_separator-1.3.1.zip`, validated successfully.
The ignored archive remains local and must not be staged.

- [ ] **Step 4: Review the complete branch for scope and security invariants**

Run:

```powershell
git status --short
git log --oneline --decorate main..HEAD
git diff --check main...HEAD
git diff --stat main...HEAD
git diff main...HEAD -- .github/workflows/ci.yml `
  tests/unit/test_ci_workflow_contract.py docs/testing.md `
  addon/blender_manifest.toml README.md docs/HANDOFF.md `
  docs/superpowers
```

Review every changed line. Confirm:

- exactly three release jobs implement draft, attest, and publish;
- only draft and publish have `contents: write` and neither has `uses:`;
- attestation has only read/OIDC/attestation permissions and one pinned action;
- subject path names only the separately downloaded ZIP;
- all release jobs retain manual/main/public guards;
- both write jobs retain the protected environment;
- all `GH_TOKEN` values remain individual-step scoped;
- validation jobs, triggers, checkout pinning, network sources, and addon API
  behavior are unchanged;
- no ignored or generated output is staged.

- [ ] **Step 5: Update the handoff with evidence and explicit hosted pending
  items**

Update `docs/HANDOFF.md` with:

- branch objective and commit history;
- exact focused/full unit counts and commands;
- headless marker, source validation, archive name, and archive validation;
- the reviewed action pin and per-job permissions;
- confirmation that no release, tag, push, PR, or repository setting changed;
- pending hosted proof that a read-only job can download a draft asset;
- pending observation of whether the two protected write jobs require one or
  multiple approvals;
- pending successful manual 1.3.1 dispatch and
  `gh attestation verify alpha_material_separator-1.3.1.zip --repo
  Alrauna/blender-alpha-material-separator`;
- recommended next action: review the branch, then request push/draft-PR
  publication separately.

Do not claim hosted or interactive checks that were not run.

- [ ] **Step 6: Remove the completed design and plan artifacts as the final
  milestone edit**

Use `apply_patch` to delete exactly:

```text
docs/superpowers/specs/2026-08-09-release-artifact-attestation-design.md
docs/superpowers/plans/2026-08-09-release-artifact-attestation.md
```

Do not delete their parent directories recursively and do not remove any other
specification or plan. Git history at commits `872c403` and the plan checkpoint
retains the approved wording.

- [ ] **Step 7: Verify the final documentation-only closeout and commit it**

Run:

```powershell
git diff --check
git status --short
git diff -- docs/HANDOFF.md docs/superpowers
git add -- docs/HANDOFF.md `
  docs/superpowers/specs/2026-08-09-release-artifact-attestation-design.md `
  docs/superpowers/plans/2026-08-09-release-artifact-attestation.md
git diff --cached --check
git diff --cached
git commit -m "docs: close release attestation milestone"
```

Expected: only the accurate handoff and deletion of the two completed process
artifacts are committed.

- [ ] **Step 8: Run the final clean-state evidence check and stop**

Run:

```powershell
git status --short --branch
git log --oneline --decorate main..HEAD
git diff --check main...HEAD
git diff --stat main...HEAD
```

Expected: clean `codex/ci-release-attestation-1.3.1`; coherent commits for
design, plan, workflow/contracts, version/docs, and milestone closeout; no
whitespace error. Present the branch for review. Do not begin another objective
or publish it without authorization.
