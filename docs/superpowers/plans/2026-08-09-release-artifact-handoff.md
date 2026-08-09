# Release Artifact Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish version 1.3.1 with provenance attestation by passing one
validated ZIP through a short-lived workflow artifact, without granting
release-write authority to the attestation action.

**Architecture:** A read-only `release_package` job builds and validates the
ZIP once from exact `GITHUB_SHA`, records its digest, and uploads the ZIP plus
checksum as `ams-release-package`. Separate attestation and protected
publication jobs natively download that exact current-run artifact, validate
its identity and digest, and only then attest or publish it. The write-authorized
publication job executes no action and creates no draft until attestation has
succeeded.

**Tech Stack:** GitHub Actions YAML, PowerShell 7, GitHub CLI, Python
`unittest`, Blender 5.2.0 extension commands.

## Global Constraints

- Release version remains exactly `1.3.1`; do not increment to 1.3.2.
- Target Blender 5.2 LTS; manifest minimum remains `5.2.0`.
- Keep workflow permissions at `contents: read` by default.
- Keep `actions/checkout` in read-only jobs only, pinned to
  `3d3c42e5aac5ba805825da76410c181273ba90b1`, with
  `persist-credentials: false`.
- Add exactly one action:
  `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`.
- Retain `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`.
- Do not add `actions/download-artifact`, a cache, setup action, package
  installer, container, self-hosted runner, external dependency, secret, or
  network source.
- The write-authorized `release_publish` job must execute no `uses:` action.
- `GH_TOKEN` belongs only on individual native `gh` command steps.
- Artifact name is exactly `ams-release-package`, retention is one day, and
  upload compression is disabled with `compression-level: 0`.
- Both consumers select exact `GITHUB_RUN_ID`, `GITHUB_REPOSITORY`, and artifact
  name when calling native `gh run download`.
- Ordinary validation continues to discover exactly one version-independent
  AMS ZIP; only the strict release path derives a versioned filename.
- Preserve all existing workflow triggers, stable validation job names,
  runners, Blender trust checks, archive checks, and release guards.
- Do not delete release ID `367440347`, create a tag, publish a release, push,
  or mutate repository settings during this plan.

---

### Task 1: Replace the draft handoff with a tested workflow artifact handoff

**Files:**

- Modify: `tests/unit/test_ci_workflow_contract.py:12-397`
- Modify: `.github/workflows/ci.yml:121-345`

**Interfaces:**

- Consumes: manual input `${{ inputs.version }}`, exact `${{ github.sha }}`,
  current `${{ github.run_id }}`, current `${{ github.repository }}`, and the
  existing `scripts/ci.py prepare-release` outputs.
- Produces: `release_package.outputs.version`, `.tag`, `.archive_name`, and
  `.sha256`; workflow artifact `ams-release-package` containing exactly the
  version-derived ZIP and `SHA256SUMS.txt`.
- Produces: a verified ZIP at
  `${{ runner.temp }}/downloaded-release/${{ needs.release_package.outputs.archive_name }}`
  in `release_attestation` and at the equivalent path in `release_publish`.

- [ ] **Step 1: Add the exact upload-action pin and convert the action allowlist
  contract to RED**

Add beside the existing action constants:

```python
UPLOAD_ARTIFACT_SHA = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
```

Change `test_no_unapproved_actions_or_execution_surfaces` so the ordered action
list is exactly two checkouts, one upload, and one attestation:

```python
self.assertEqual(
    action_uses,
    [f"actions/checkout@{CHECKOUT_SHA}"] * 2
    + [f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}"]
    + [f"actions/attest@{ATTEST_SHA}"],
)
for forbidden in (
    "actions/cache",
    "actions/download-artifact",
    "setup-python",
    "container:",
    "self-hosted",
    "secrets.",
):
    self.assertNotIn(forbidden, self.text)
```

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_no_unapproved_actions_or_execution_surfaces `
  -v
```

Expected: FAIL because the workflow still has no `actions/upload-artifact` use.

- [ ] **Step 2: Replace old draft-specific contracts with the complete new job
  boundary contracts**

Update job-section splits from `release_draft` to `release_package`. Preserve
the existing trigger, validation, exact-SHA fetch, safe expression flow, and
version-independent archive assertions. Rename draft-specific test methods and
variables to package terminology.

Add or rewrite focused assertions with these exact requirements:

```python
def test_release_jobs_preserve_approved_permission_boundaries(self) -> None:
    package = self.text.split("\n  release_package:\n", 1)[1].split(
        "\n  release_attestation:\n", 1
    )[0]
    attestation = self.text.split("\n  release_attestation:\n", 1)[1].split(
        "\n  release_publish:\n", 1
    )[0]
    publish = self.text.split("\n  release_publish:\n", 1)[1]

    self.assertNotIn("environment: release", package)
    self.assertIn("permissions:\n      contents: read", package)
    self.assertEqual(package.count("uses:"), 1)
    self.assertIn(f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", package)
    self.assertEqual(
        re.findall(
            r"^\s{4}permissions:\n(?:^\s{6}.+\n?)+",
            attestation,
            re.MULTILINE,
        ),
        [
            "    permissions:\n"
            "      actions: read\n"
            "      contents: read\n"
            "      id-token: write\n"
            "      attestations: write\n"
        ],
    )
    self.assertNotIn("contents: write", attestation)
    self.assertIn("environment: release", publish)
    self.assertIn(
        "permissions:\n      actions: read\n      contents: write",
        publish,
    )
    self.assertNotIn("uses:", publish)
    self.assertEqual(self.text.count("contents: write"), 1)
```

```python
def test_release_package_uploads_exact_short_lived_artifact(self) -> None:
    package = self.text.split("\n  release_package:\n", 1)[1].split(
        "\n  release_attestation:\n", 1
    )[0]
    upload = package.split("\n      - name: Upload release package\n", 1)[1]
    self.assertIn(f"uses: actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}", upload)
    self.assertIn("name: ams-release-package", upload)
    self.assertIn(
        "${{ runner.temp }}/release/${{ steps.release.outputs.archive_name }}",
        upload,
    )
    self.assertIn("${{ runner.temp }}/release/SHA256SUMS.txt", upload)
    self.assertIn("if-no-files-found: error", upload)
    self.assertIn("retention-days: 1", upload)
    self.assertIn("compression-level: 0", upload)
    self.assertNotIn("overwrite:", upload)
    self.assertNotIn("include-hidden-files:", upload)
    for mutation in ("gh release create", "gh release upload", "gh release edit"):
        self.assertNotIn(mutation, package)
```

```python
def test_release_consumers_download_and_verify_current_run_artifact(self) -> None:
    attestation = self.text.split("\n  release_attestation:\n", 1)[1].split(
        "\n  release_publish:\n", 1
    )[0]
    publish = self.text.split("\n  release_publish:\n", 1)[1]
    for section in (attestation, publish):
        self.assertIn("actions: read", section)
        self.assertIn("RELEASE_ARTIFACT_NAME: ams-release-package", section)
        self.assertIn("gh run download $env:GITHUB_RUN_ID", section)
        self.assertIn("--repo $env:GITHUB_REPOSITORY", section)
        self.assertIn("--name $env:RELEASE_ARTIFACT_NAME", section)
        self.assertIn("--dir $DownloadDirectory", section)
        self.assertIn("Get-FileHash -LiteralPath $Archive -Algorithm SHA256", section)
        self.assertIn("$Actual -ne $env:EXPECTED_SHA256", section)
        self.assertIn("SHA256SUMS.txt", section)
        self.assertIn("GH_TOKEN: ${{ github.token }}", section)
        self.assertNotIn("actions/download-artifact", section)
```

Rewrite dependency/order assertions to require:

```python
self.assertIn("needs: [validate, release_gate]", package)
self.assertIn("needs: [release_package]", attestation)
self.assertIn(
    "needs: [release_package, release_attestation]",
    publish,
)
self.assertLess(
    self.text.index(f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}"),
    self.text.index(f"actions/attest@{ATTEST_SHA}"),
)
self.assertLess(
    self.text.index(f"actions/attest@{ATTEST_SHA}"),
    self.text.index("gh release create"),
)
self.assertLess(
    self.text.index("gh release create"),
    self.text.index("gh release upload"),
)
self.assertLess(
    self.text.index("gh release upload"),
    self.text.index("gh release edit"),
)
```

Update token assertions to prove package has zero `GH_TOKEN` entries,
attestation has exactly one, every token-bearing step contains native `gh` in
`run:`, and publish has tokens only on its six native GitHub CLI steps:
artifact download, identity refusal, draft creation, asset upload, stored ZIP
download, and publication.

- [ ] **Step 3: Run the focused contracts to establish RED before editing the
  workflow**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
```

Expected: FAIL in the renamed/missing `release_package`, upload-action,
artifact-download, permission, dependency, and ordering contracts. Existing
stable validation and trust-boundary contracts remain passing where they do not
depend on the old job names.

- [ ] **Step 4: Convert `release_draft` into the read-only producer**

In `.github/workflows/ci.yml`, rename the job to `release_package`, name it
`Build verified release package`, remove `environment: release`, change its
permissions to `contents: read`, and retain its outputs. Keep the exact native
Git fetch, Blender verification, build, ZIP validation, and
`prepare-release` steps unchanged.

Delete the package job's existing tag/release refusal, draft creation, release
asset upload, stored ZIP download, and stored ZIP verification steps. Add:

```yaml
      - name: Upload release package
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: ams-release-package
          path: |
            ${{ runner.temp }}/release/${{ steps.release.outputs.archive_name }}
            ${{ runner.temp }}/release/SHA256SUMS.txt
          if-no-files-found: error
          retention-days: 1
          compression-level: 0
```

Do not set `overwrite` or `include-hidden-files`.

- [ ] **Step 5: Make attestation consume and validate the workflow artifact**

Change `needs` and all output references from `release_draft` to
`release_package`. Add `actions: read` before the existing three permissions.
Set job environment values:

```yaml
    env:
      RELEASE_ARTIFACT_NAME: ams-release-package
      ARCHIVE_NAME: ${{ needs.release_package.outputs.archive_name }}
      EXPECTED_SHA256: ${{ needs.release_package.outputs.sha256 }}
```

Replace the draft download step with `Download and verify release package`.
Its native PowerShell must:

```powershell
$DownloadDirectory = '${{ runner.temp }}/downloaded-release'
New-Item -ItemType Directory -Path $DownloadDirectory | Out-Null
gh run download $env:GITHUB_RUN_ID `
  --repo $env:GITHUB_REPOSITORY `
  --name $env:RELEASE_ARTIFACT_NAME `
  --dir $DownloadDirectory
if ($LASTEXITCODE -ne 0) {
  throw 'Could not download the current release package.'
}
$Files = @(Get-ChildItem -LiteralPath $DownloadDirectory -File)
$ExpectedNames = @($env:ARCHIVE_NAME, 'SHA256SUMS.txt')
$Unexpected = @($Files | Where-Object { $_.Name -notin $ExpectedNames })
if ($Files.Count -ne 2 -or $Unexpected.Count -ne 0) {
  throw 'Release package must contain exactly the expected ZIP and checksum.'
}
$Archive = Join-Path $DownloadDirectory $env:ARCHIVE_NAME
$ChecksumPath = Join-Path $DownloadDirectory 'SHA256SUMS.txt'
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf) -or
    -not (Test-Path -LiteralPath $ChecksumPath -PathType Leaf)) {
  throw 'Release package is missing the expected ZIP or checksum.'
}
$Actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
$Actual = $Actual.ToLowerInvariant()
if ($Actual -ne $env:EXPECTED_SHA256) {
  throw 'Release package ZIP does not match the verified build digest.'
}
$ExpectedChecksum = "$($env:EXPECTED_SHA256)  $($env:ARCHIVE_NAME)"
$ActualChecksum = (Get-Content -LiteralPath $ChecksumPath -Raw).Trim()
if ($ActualChecksum -ne $ExpectedChecksum) {
  throw 'Release checksum does not identify the verified ZIP.'
}
```

Keep `GH_TOKEN` only on this step. Keep the pinned attestation action and change
its subject output reference to `needs.release_package.outputs.archive_name`.

- [ ] **Step 6: Move all release mutations into the protected native publish
  job**

Change `release_publish` to `windows-2025`, timeout 10 minutes, depend on
`[release_package, release_attestation]`, and grant exactly:

```yaml
    permissions:
      actions: read
      contents: write
```

Set:

```yaml
    env:
      RELEASE_ARTIFACT_NAME: ams-release-package
      RELEASE_TAG: ${{ needs.release_package.outputs.tag }}
      ARCHIVE_NAME: ${{ needs.release_package.outputs.archive_name }}
      EXPECTED_SHA256: ${{ needs.release_package.outputs.sha256 }}
```

Add a first `Download and verify attested package` step using the same exact
two-file and digest/checksum validation from Step 5. Keep its token step-local.
This step must finish before any release mutation.

Move the existing GraphQL `Refuse an existing tag or release` logic into this
job unchanged. Then move the native draft creation and asset upload operations
here, adding explicit repository selection because this job has no checkout:

```powershell
gh release create $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  --draft --generate-notes `
  --title $env:RELEASE_TAG `
  --target '${{ github.sha }}'
```

```powershell
gh release upload $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  (Join-Path $DownloadDirectory $env:ARCHIVE_NAME) `
  (Join-Path $DownloadDirectory 'SHA256SUMS.txt')
```

Give each step only the environment values it uses, including
`DOWNLOAD_DIRECTORY: ${{ runner.temp }}/downloaded-release` for asset upload.

Add a separate stored ZIP download directory and verify the stored ZIP with
native PowerShell because this no-checkout job cannot call `scripts/ci.py`:

```powershell
$StoredDirectory = '${{ runner.temp }}/stored-release'
New-Item -ItemType Directory -Path $StoredDirectory | Out-Null
gh release download $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  --pattern $env:ARCHIVE_NAME `
  --dir $StoredDirectory
if ($LASTEXITCODE -ne 0) {
  throw 'Could not download the stored draft ZIP.'
}
$StoredArchive = Join-Path $StoredDirectory $env:ARCHIVE_NAME
$StoredSha256 = (
  Get-FileHash -LiteralPath $StoredArchive -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($StoredSha256 -ne $env:EXPECTED_SHA256) {
  throw 'Stored draft ZIP does not match the attested package digest.'
}
```

Finally retain native publication, after stored verification:

```powershell
gh release edit $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  --draft=false
```

The complete publish section must contain no `uses:` line.

- [ ] **Step 7: Run focused contracts GREEN, then the complete unit suite**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all workflow contract tests pass, then all unit tests pass with zero
failures or errors.

- [ ] **Step 8: Review and commit the workflow unit**

Run:

```powershell
git diff --check
git diff -- .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py
git status --short
```

Confirm only the approved action was added; `release_package` has no mutation
or token; attestation has no content write; publication has no action; all
artifact and release downloads select repository explicitly; and draft
creation occurs after attestation in the job dependency graph.

Commit:

```powershell
git add -- .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py
git diff --cached --check
git diff --cached
git commit -m "ci: hand off attested release artifact"
```

---

### Task 2: Make permanent CI policy and operator documentation match reality

**Files:**

- Modify: `tests/unit/test_ci_workflow_contract.py:346-397`
- Modify: `AGENTS.md:256-289`
- Modify: `docs/testing.md:40-116`
- Modify: `PLAN.md:282-313`

**Interfaces:**

- Consumes: the implemented `release_package`, `release_attestation`, and
  `release_publish` workflow contracts from Task 1.
- Produces: permanent contributor policy, release-operator documentation, and
  CI milestone state that describe the same byte/digest flow.

- [ ] **Step 1: Strengthen the documentation contract and establish RED**

Extend `test_ci_security_and_rollout_are_documented` so `docs/testing.md`
must include:

```python
for text in (
    "release_package",
    "ams-release-package",
    "actions/upload-artifact",
    UPLOAD_ARTIFACT_SHA,
    "actions: read",
    "gh run download",
    "GITHUB_RUN_ID",
    "retention-days: 1",
    "compression-level: 0",
):
    self.assertIn(text, testing)
self.assertNotIn("`release_draft`", testing)
```

Require the new permanent policy across `AGENTS.md` and `PLAN.md`:

```python
for text in (
    "read-only release-package job builds once",
    "same current-run workflow artifact",
    "re-downloads the stored ZIP",
):
    self.assertIn(text, agents + plan)
```

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Expected: FAIL because permanent documentation still describes
`release_draft` rebuilding and exposing the draft to attestation.

- [ ] **Step 2: Update the repository CI/CD security policy**

In `AGENTS.md`, preserve the default-read, checkout, action-approval, Blender
trust, release-authorization, and resolver rules. Replace only the obsolete
write-job fetch/rebuild wording with these explicit invariants:

```markdown
- Keep `actions/checkout` confined to read-only jobs, pinned to a reviewed full
  commit SHA, with `persist-credentials: false`. The read-only release-package
  job must use unauthenticated native Git, fetch the exact `GITHUB_SHA`, and
  verify `HEAD` without credentials. Adding an action, dependency, cache,
  artifact transfer, trigger, runner type, permission, or network source
  requires design review and explicit approval.
- Validation builds are disposable. The read-only release-package job builds
  once from the exact validated `main` commit. Attestation and protected
  publication independently download the same current-run workflow artifact
  and verify its producer-reported SHA-256. Publication uploads those exact
  bytes, re-downloads the stored ZIP, re-hashes it, then publishes.
```

Clarify that only `release_publish` may use `contents: write`, while the
artifact consumers may use `actions: read`.

- [ ] **Step 3: Rewrite release operation and failure semantics**

In `docs/testing.md`, replace the statement that workflow artifacts are unused
with the narrower truth: ordinary validation uses none; the manual release
path uses one short-lived package artifact.

Replace the `release_draft` paragraphs with exact producer, attestation, and
publication responsibilities. Document the action pin, artifact name,
`retention-days: 1`, `compression-level: 0`, native
`gh run download $GITHUB_RUN_ID`, exact digest/checksum verification, and the
fact that `release_publish` creates the draft only after attestation succeeds.

State failure behavior precisely:

- package or attestation failure creates no draft;
- failure after draft creation leaves an unpublished draft;
- no path publishes before attestation and stored-asset digest verification.

Retain the existing `gh attestation verify` operator command and the caveat
that provenance is not a vulnerability-free claim. Replace the obsolete
pending draft-read check with hosted acceptance of artifact handoff and final
published-asset verification.

- [ ] **Step 4: Update the CI milestone without rewriting historical work**

In `PLAN.md` Milestone 6, add checked items recording the approved artifact
handoff and least-privilege separation. Add the permanent three-job flow in a
short paragraph containing the phrases required by the contract. Leave
historical hosted bootstrap notes intact unless they directly claim the current
release implementation still rebuilds in the write job.

- [ ] **Step 5: Run documentation contract GREEN and the complete unit suite**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: the focused documentation contract passes, then all unit tests pass
with zero failures or errors.

- [ ] **Step 6: Review and commit the permanent documentation unit**

Run:

```powershell
git diff --check
git diff -- AGENTS.md PLAN.md docs/testing.md tests/unit/test_ci_workflow_contract.py
```

Confirm every document describes one read-only build, two same-run consumers,
one write-authorized native publication job, and identical digest checks.

Commit:

```powershell
git add -- AGENTS.md PLAN.md docs/testing.md tests/unit/test_ci_workflow_contract.py
git diff --cached --check
git diff --cached
git commit -m "docs: document release artifact trust flow"
```

---

### Task 3: Review, verify, and close the implementation milestone

**Files:**

- Modify: `docs/HANDOFF.md`
- Delete after all review and verification passes:
  `docs/superpowers/specs/2026-08-09-release-artifact-handoff-design.md`
- Delete after all review and verification passes:
  `docs/superpowers/plans/2026-08-09-release-artifact-handoff.md`

**Interfaces:**

- Consumes: the complete branch diff and all local test/build commands.
- Produces: a reviewable branch whose handoff records exact evidence and whose
  in-flight design/plan files remain recoverable from Git history.

- [ ] **Step 1: Invoke the required correctness/security review gate**

Use `superpowers:requesting-code-review` on the complete branch diff from
`f39fafc72507c099dc4bf3af39ae497a1e8499a9` through `HEAD`. Review at minimum:

- action pin/allowlist and no unapproved execution surface;
- exact permissions and step-local tokens;
- unauthenticated exact-SHA producer fetch;
- artifact identity, current-run selection, file-set validation, checksum, and
  digest checks in both consumers;
- no release mutation before attestation succeeds;
- no `uses:` action in the write job;
- explicit repository selection on every no-checkout release command;
- failure behavior and existing-release refusal;
- preservation of stable validation and Blender download trust contracts.

If review finds a correctness or security defect, invoke
`superpowers:receiving-code-review`, reproduce it with a focused failing
contract, apply the smallest root-cause correction, rerun the focused and full
unit suites, and commit the correction separately. Do not broaden scope into
unrelated CI cleanup.

- [ ] **Step 2: Run the fresh complete local gate**

Run exactly:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'

& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon

Remove-Item .\.packaged-releases\*.zip -ErrorAction SilentlyContinue
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
$Archives = @(
  Get-ChildItem .\.packaged-releases\alpha_material_separator-*.zip -File
)
if ($Archives.Count -ne 1) {
  throw "Expected one AMS ZIP, found $($Archives.Count)."
}
& $Blender52 --factory-startup --command extension validate `
  $Archives[0].FullName
git diff --check
```

Expected: workflow contracts and all unit tests pass; the headless suite exits
zero and ends with `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`; source
validation succeeds; exactly one 1.3.1 ZIP is built and archive validation
succeeds; `git diff --check` emits no errors.

Private-reference smoke, performance benchmarks, and installed interactive
material checks are not applicable because this branch changes no add-on
payload, resolver, rasterizer, classifier, cache, Preview, Apply, assignment,
or preservation behavior.

- [ ] **Step 3: Review final scope and update the handoff with evidence**

Run:

```powershell
git diff --stat f39fafc72507c099dc4bf3af39ae497a1e8499a9..HEAD
git diff f39fafc72507c099dc4bf3af39ae497a1e8499a9..HEAD -- `
  .github/workflows/ci.yml `
  tests/unit/test_ci_workflow_contract.py `
  AGENTS.md PLAN.md docs/testing.md
git log --oneline --decorate `
  f39fafc72507c099dc4bf3af39ae497a1e8499a9..HEAD
```

Update `docs/HANDOFF.md` with:

- branch purpose and base SHA;
- approved architecture and exact action pins;
- RED/GREEN commands and failure reasons;
- complete verification command results and archive identity;
- review findings and any correction commits;
- current hosted draft ID `367440347`, explicitly untouched;
- next action: prepare a PR, then after merge separately authorize draft
  deletion and the next 1.3.1 dispatch.

- [ ] **Step 4: Remove in-flight lifecycle documents and commit closeout**

Only after Steps 1-3 pass, remove the design and implementation plan from the
working tree. Git history retains both approved checkpoints.

Stage and inspect only closeout documentation:

```powershell
git add -- docs/HANDOFF.md `
  docs/superpowers/specs/2026-08-09-release-artifact-handoff-design.md `
  docs/superpowers/plans/2026-08-09-release-artifact-handoff.md
git diff --cached --check
git diff --cached
git commit -m "docs: close release artifact handoff milestone"
```

- [ ] **Step 5: Apply verification-before-completion after the closeout commit**

Run:

```powershell
git status --short --branch
git log --oneline --decorate `
  f39fafc72507c099dc4bf3af39ae497a1e8499a9..HEAD
git diff --check f39fafc72507c099dc4bf3af39ae497a1e8499a9..HEAD
```

Expected: clean topic branch, coherent commits limited to the release artifact
handoff, and no whitespace errors. Do not claim hosted success: artifact
transfer, attestation, release publication, and final
`gh attestation verify` remain post-merge acceptance work.
