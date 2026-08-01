# GitHub Actions Pre-Push Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the audited release-token exposure and make the existing GitHub Actions workflow version-safe, network-bounded, and extraction-hardened before its first push.

**Architecture:** Keep the existing standard-library helper and single workflow. Harden bootstrap operations in `scripts/ci.py`; replace privileged `actions/checkout` with an unauthenticated exact-SHA native Git fetch; simplify dispatch gating; and discover the single validation ZIP instead of duplicating the manifest version.

**Tech Stack:** Python 3.13 standard library, `unittest`, GitHub Actions YAML, PowerShell 7, native Git and curl, Blender 5.2.0 CLI.

## Global Constraints

- Work only on local branch `ci/automation`.
- Do not alter remotes, push, create a pull request, change repository settings, create tags, or publish a release.
- Extension version remains `1.0.0`; public API remains `1.2`.
- Blender remains fixed at `5.2.0`.
- Keep `actions/checkout` pinned to `3d3c42e5aac5ba805825da76410c181273ba90b1` in read-only jobs with `persist-credentials: false`.
- The release job must invoke no action and must give no credential to Git.
- Default workflow permission remains `contents: read`; only the protected release job receives `contents: write`.
- `GH_TOKEN` remains present only on the five individual `gh` release steps.
- Keep system DNS, Cloudflare DoH, and Quad9 DoH mandatory and require byte-identical checksum content.
- Keep HTTPS-only transport, TLS validation, redirect rejection, exact HTTP 200, committed SHA-256 agreement, and pre-extraction hashing.
- Do not add actions, dependencies, setup steps, caches, artifacts, containers, self-hosted runners, schedules, signing, attestations, update hosting, or a custom updater.
- Blender native extension-repository hosting and `index.json` publication remain a separate milestone.
- The private before/after `.blend` smoke is not required because no extension behavior changes.
- Use TDD for every production change and create one coherent local commit after each verified task.

## File Map

- Modify `scripts/ci.py`: bounded curl execution and safe platform-specific archive extraction.
- Modify `tests/unit/test_ci.py`: RED/GREEN contracts for network bounds, timeout cleanup, and Linux tar filtering.
- Modify `.github/workflows/ci.yml`: exact-SHA unauthenticated release fetch, expression-only dispatch gating, and version-independent validation ZIP discovery.
- Modify `tests/unit/test_ci_workflow_contract.py`: RED/GREEN workflow security and future-version contracts.
- Modify `docs/testing.md`: corrected token boundary, native Git release fetch, network bounds, and local/hosted validation boundary.
- Modify `PLAN.md`: mark only locally verified pre-push hardening items complete.
- Modify `AGENTS.md`: durable release-fetch and version-independent validation rules.
- Modify `docs/HANDOFF.md`: exact RED/GREEN commands, review findings, local results, warnings, and the approval-gated next action.

---

### Task 1: Bound Bootstrap Networking and Harden Extraction

**Files:**
- Modify: `tests/unit/test_ci.py`
- Modify: `scripts/ci.py`

**Interfaces:**
- Produces: `CURL_CONNECT_TIMEOUT_SECONDS = 30`
- Produces: `CURL_TOTAL_TIMEOUT_SECONDS = 600`
- Produces: `CURL_PROCESS_TIMEOUT_SECONDS = 620`
- Produces: `CURL_RETRIES = 2`
- Produces: `extract_archive(platform: str, archive: Path, extract_dir: Path) -> None`
- Preserves: `curl_command(url: str, output: Path, doh_url: str | None = None) -> list[str]`
- Preserves: `download(url: str, output: Path, doh_url: str | None = None) -> None`
- Preserves: `prepare_blender(platform: str, output_dir: Path, github_output: Path | None = None) -> tuple[Path, Path]`

- [ ] **Step 1: Add RED contracts for bounded curl and timeout cleanup**

Add these imports to `tests/unit/test_ci.py`:

```python
import subprocess
from unittest import mock
```

Extend
`test_curl_command_requires_https_tls_no_redirect_and_optional_doh` with:

```python
        for flag, value in (
            ("--connect-timeout", "30"),
            ("--max-time", "600"),
            ("--retry", "2"),
            ("--retry-delay", "2"),
            ("--retry-max-time", "600"),
        ):
            self.assertIn(flag, plain)
            self.assertEqual(plain[plain.index(flag) + 1], value)
        self.assertIn("--retry-all-errors", plain)
```

Add:

```python
    def test_download_timeout_removes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partial.bin"
            output.write_bytes(b"partial")
            timeout = subprocess.TimeoutExpired(
                cmd=["curl"],
                timeout=620,
            )
            with mock.patch.object(
                ci.subprocess,
                "run",
                side_effect=timeout,
            ):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    ci.download(ci.CHECKSUM_URL, output)
            self.assertFalse(output.exists())
```

- [ ] **Step 2: Run the focused tests and record RED**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_curl_command_requires_https_tls_no_redirect_and_optional_doh `
  tests.unit.test_ci.CiTrustTests.test_download_timeout_removes_partial_output `
  -v
```

Expected: the command-contract test fails because timeout/retry flags are
absent; the timeout test errors with uncaught `subprocess.TimeoutExpired`.

- [ ] **Step 3: Implement the minimal network bounds**

Add beside the fixed URL constants in `scripts/ci.py`:

```python
CURL_CONNECT_TIMEOUT_SECONDS = 30
CURL_TOTAL_TIMEOUT_SECONDS = 600
CURL_PROCESS_TIMEOUT_SECONDS = 620
CURL_RETRIES = 2
```

Add these arguments to the existing `curl_command()` list before
`"--output"`:

```python
        "--connect-timeout",
        str(CURL_CONNECT_TIMEOUT_SECONDS),
        "--max-time",
        str(CURL_TOTAL_TIMEOUT_SECONDS),
        "--retry",
        str(CURL_RETRIES),
        "--retry-delay",
        "2",
        "--retry-max-time",
        str(CURL_TOTAL_TIMEOUT_SECONDS),
        "--retry-all-errors",
```

Replace the direct `subprocess.run()` call in `download()` with:

```python
    try:
        result = subprocess.run(
            curl_command(url, output, doh_url),
            check=False,
            capture_output=True,
            text=True,
            timeout=CURL_PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as ex:
        output.unlink(missing_ok=True)
        raise RuntimeError("download timed out") from ex
```

Keep the existing return-code and exact-HTTP-200 check unchanged.

- [ ] **Step 4: Run the focused network tests and record GREEN**

Run the Step 2 command again.

Expected: both tests pass.

- [ ] **Step 5: Add the RED Linux extraction-filter contract**

Add to `tests/unit/test_ci.py`:

```python
    def test_archive_extraction_uses_safe_linux_tar_filter(self) -> None:
        archive = Path("blender.tar.xz")
        output = Path("blender")
        with mock.patch.object(ci.shutil, "unpack_archive") as unpack:
            ci.extract_archive("linux", archive, output)
            unpack.assert_called_once_with(archive, output, filter="data")

        with mock.patch.object(ci.shutil, "unpack_archive") as unpack:
            ci.extract_archive("windows", Path("blender.zip"), output)
            unpack.assert_called_once_with(Path("blender.zip"), output)
```

- [ ] **Step 6: Run the extraction test and record RED**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_archive_extraction_uses_safe_linux_tar_filter `
  -v
```

Expected: error because `extract_archive` does not exist.

- [ ] **Step 7: Add the smallest platform-specific extraction function**

Add to `scripts/ci.py`:

```python
def extract_archive(
    platform: str,
    archive: Path,
    extract_dir: Path,
) -> None:
    if platform == "linux":
        shutil.unpack_archive(archive, extract_dir, filter="data")
    else:
        shutil.unpack_archive(archive, extract_dir)
```

Replace:

```python
    shutil.unpack_archive(archive, extract_dir)
```

inside `prepare_blender()` with:

```python
    extract_archive(platform, archive, extract_dir)
```

- [ ] **Step 8: Run focused and full unit verification**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Expected: all focused and full unit tests pass; `git diff --check` prints
nothing.

- [ ] **Step 9: Review and commit Task 1**

Run:

```powershell
git add -- scripts/ci.py tests/unit/test_ci.py
git diff --cached --check
git diff --cached
git commit -m "fix: bound Blender bootstrap operations"
```

Confirm the staged diff contains only Task 1.

---

### Task 2: Isolate Release Credentials and Remove Version Brittleness

**Files:**
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: existing strict `RELEASE_VERSION` environment handling.
- Produces: release environment values `SOURCE_REPOSITORY`, `SOURCE_SHA`, and `GIT_TERMINAL_PROMPT`.
- Preserves: exact required check names and all five scoped `GH_TOKEN` steps.
- Preserves: publication filename derived from validated `RELEASE_VERSION`.

- [ ] **Step 1: Add RED contracts for the privileged source boundary**

Change the checkout count in
`test_checkout_and_default_permissions_are_locked_down` from `3` to `2`.

Add to `tests/unit/test_ci_workflow_contract.py`:

```python
    def test_release_job_fetches_exact_public_sha_without_credentials(self) -> None:
        release = self.text.split("\n  release:\n", 1)[1]
        source_step = release.split(
            "\n      - name: Refuse an existing tag or release",
            1,
        )[0]
        self.assertNotIn("uses:", release)
        self.assertIn(
            "SOURCE_REPOSITORY: https://github.com/${{ github.repository }}.git",
            source_step,
        )
        self.assertIn("SOURCE_SHA: ${{ github.sha }}", source_step)
        self.assertIn("GIT_TERMINAL_PROMPT: 0", source_step)
        self.assertIn("git init .", source_step)
        self.assertIn(
            "git fetch --no-tags --depth=1 origin $env:SOURCE_SHA",
            source_step,
        )
        self.assertIn("git checkout --detach FETCH_HEAD", source_step)
        self.assertIn("git rev-parse HEAD", source_step)
        self.assertIn("$Actual.Trim() -ne $env:SOURCE_SHA", source_step)
        self.assertNotIn("GH_TOKEN:", source_step)
        self.assertNotIn("github.token", source_step)
```

- [ ] **Step 2: Add RED contracts for safe gating and ZIP discovery**

Add:

```python
    def test_dispatch_contexts_never_enter_shell_source(self) -> None:
        self.assertNotIn("if ('${{ github.ref }}'", self.text)
        self.assertNotIn(
            "if ('${{ github.event.repository.visibility }}'",
            self.text,
        )
        release_gate = self.text.split(
            "\n  release_gate:\n",
            1,
        )[1].split("\n  release:\n", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", release_gate)
        self.assertIn(
            "github.event.repository.visibility == 'public'",
            release_gate,
        )

    def test_validation_discovers_exactly_one_versioned_zip(self) -> None:
        validate = self.text.split(
            "\n  release_gate:\n",
            1,
        )[0]
        self.assertNotIn(
            "alpha_material_separator-1.0.0.zip",
            validate,
        )
        self.assertIn("Get-ChildItem", validate)
        self.assertIn(
            "-Filter 'alpha_material_separator-*.zip'",
            validate,
        )
        self.assertIn("$Archives.Count -ne 1", validate)
        self.assertIn("$Archives[0].FullName", validate)
```

- [ ] **Step 3: Run the new workflow contracts and record RED**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_checkout_and_default_permissions_are_locked_down `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_release_job_fetches_exact_public_sha_without_credentials `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_dispatch_contexts_never_enter_shell_source `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_validation_discovers_exactly_one_versioned_zip `
  -v
```

Expected: failures show the third checkout, missing native Git boundary,
shell-interpolated ref/visibility, and hard-coded `1.0.0` validation ZIP.

- [ ] **Step 4: Make the release gate expression-only**

Change `release_gate.if` in `.github/workflows/ci.yml` to:

```yaml
    if: >-
      github.event_name == 'workflow_dispatch' &&
      github.ref == 'refs/heads/main' &&
      github.event.repository.visibility == 'public'
```

Replace the gate command body with:

```yaml
      - name: Require manifest release version
        shell: pwsh
        run: >-
          python scripts/ci.py check-release
          --version $env:RELEASE_VERSION
          --manifest addon/blender_manifest.toml
```

Do not change the existing gate-job `RELEASE_VERSION` environment declaration.

- [ ] **Step 5: Replace privileged checkout with exact native Git**

Delete the release job's `actions/checkout` step. Insert as its first step:

```yaml
      - name: Fetch exact public source without credentials
        shell: pwsh
        env:
          SOURCE_REPOSITORY: https://github.com/${{ github.repository }}.git
          SOURCE_SHA: ${{ github.sha }}
          GIT_TERMINAL_PROMPT: 0
        run: |
          git init .
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not initialize the release workspace.'
          }
          git remote add origin $env:SOURCE_REPOSITORY
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not configure the public source remote.'
          }
          git fetch --no-tags --depth=1 origin $env:SOURCE_SHA
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not fetch the exact release commit.'
          }
          git checkout --detach FETCH_HEAD
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not check out the exact release commit.'
          }
          $Actual = git rev-parse HEAD
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not read the checked-out release commit.'
          }
          if ($Actual.Trim() -ne $env:SOURCE_SHA) {
            throw 'Checked-out release commit does not match GITHUB_SHA.'
          }
```

Do not add token, credential helper, GitHub CLI, action, branch fetch, tag
fetch, or full history to this step.

- [ ] **Step 6: Discover the single validation ZIP**

Replace the validation matrix's `Validate extension ZIP` command with:

```yaml
      - name: Validate extension ZIP
        shell: pwsh
        run: |
          $Archives = @(
            Get-ChildItem `
              -LiteralPath '${{ runner.temp }}/release' `
              -Filter 'alpha_material_separator-*.zip' `
              -File
          )
          if ($Archives.Count -ne 1) {
            throw "Expected one AMS ZIP, found $($Archives.Count)."
          }
          & '${{ steps.blender.outputs.blender }}' `
            --factory-startup --command extension validate `
            $Archives[0].FullName
          if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
          }
```

Keep the release job's validated-version archive path unchanged.

- [ ] **Step 7: Run focused and complete workflow contracts**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest `
  tests.unit.test_ci `
  tests.unit.test_ci_workflow_contract `
  -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Expected: all focused and complete unit tests pass; diff check prints nothing.

- [ ] **Step 8: Review and commit Task 2**

Run:

```powershell
git add -- .github/workflows/ci.yml `
  tests/unit/test_ci_workflow_contract.py
git diff --cached --check
git diff --cached
git commit -m "fix: isolate release write credentials"
```

Confirm the release section has no `uses:` line and exactly five scoped
`GH_TOKEN` declarations.

---

### Task 3: Durable Guidance, Full Gate, and Review

**Files:**
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Modify: `docs/testing.md`
- Modify: `PLAN.md`
- Modify: `AGENTS.md`
- Modify: `docs/HANDOFF.md`
- Modify only for accepted review findings: `.github/workflows/ci.yml`, `scripts/ci.py`, and their focused tests.

**Interfaces:**
- Consumes: verified Task 1 and Task 2 behavior.
- Produces: current contributor policy and a clean local branch ready for separately approved hosted validation.

- [ ] **Step 1: Add a RED durable-documentation contract**

Extend `test_ci_security_and_rollout_are_documented` with:

```python
        for text in (
            "unauthenticated native Git",
            "exact `GITHUB_SHA`",
            "30-second connection timeout",
            "two retries",
            "version-independent",
            "separate milestone",
        ):
            self.assertIn(text, testing + agents + plan)
```

- [ ] **Step 2: Run the documentation contract and record RED**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Expected: fail because one or more approved hardening rules are absent from
durable guidance.

- [ ] **Step 3: Update durable documentation**

Update `docs/testing.md` to state:

- read-only jobs use the pinned checkout action;
- the write-authorized release job fetches exact `GITHUB_SHA` through
  unauthenticated native Git;
- Git verifies the resulting `HEAD`;
- ordinary CI discovers exactly one versioned AMS ZIP;
- curl uses a 30-second connection timeout, a fixed total limit, and two
  retries before failing closed;
- Linux tar extraction uses the safe data filter;
- the local curl/Quad9 failure remains unresolved until hosted execution; and
- Blender repository hosting is a separate milestone with no AMS updater.

Update the `GitHub Actions CI/CD` section of `PLAN.md` by adding locally
verifiable hardening checkboxes. Mark each complete only after its exact
focused and full commands pass. Leave push, hosted checks, settings, merge,
release, and repository hosting unchecked.

Update `AGENTS.md` under CI/CD security:

- checkout is allowed only in read-only jobs;
- the write job must use unauthenticated native Git and verify exact
  `GITHUB_SHA`;
- `GH_TOKEN` remains limited to individual GitHub CLI steps;
- ordinary validation may not hard-code an extension release version; and
- network bounds may not weaken resolver or hash requirements.

- [ ] **Step 4: Run the documentation and complete unit gates**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Expected: all tests pass and diff check prints nothing.

- [ ] **Step 5: Run the complete Blender and package gate**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-1.0.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

Expected:

```text
ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK
ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK
Validation succeeded
```

Inspect the ZIP and require that it contains no `.github/`, `scripts/`,
`tests/`, `.local-references/`, or repository documentation.

- [ ] **Step 6: Perform correctness/security and minimalism reviews**

Use `superpowers:requesting-code-review` to verify:

- no action receives a write-capable token;
- native Git receives no token and verifies exact `GITHUB_SHA`;
- dispatch contexts do not enter shell source;
- project code, Blender, hashing, and packaging receive no `GH_TOKEN`;
- retry and timeout behavior remains HTTPS-only and fail closed;
- the validation ZIP is version-independent while release naming remains
  strict;
- Linux extraction uses `filter="data"`;
- release gating, existing-tag refusal, draft-first upload, stored-ZIP hash,
  and publication ordering remain intact.

Use `ponytail:ponytail-review` to identify removable duplication or speculative
machinery. Do not remove an approved trust-boundary check merely to reduce
line count.

- [ ] **Step 7: Correct accepted findings with a fresh RED/GREEN cycle**

For each accepted finding:

1. Add one focused failing assertion to `test_ci.py` or
   `test_ci_workflow_contract.py`.
2. Run it and record the intended failure.
3. Make the smallest correction.
4. Run the focused test, both CI test modules, and the full unit suite.
5. Commit a security finding separately when it is materially distinct from
   documentation.

Do not weaken the design to work around an unverified hosted-runner assumption.

- [ ] **Step 8: Update the handoff with exact evidence**

Update `docs/HANDOFF.md` with:

- Task 1 and Task 2 commit hashes;
- each RED and GREEN command and result;
- full unit count and headless success markers;
- source and archive validation result;
- package-boundary result;
- review findings and corrections;
- the still-unverified hosted runner, Quad9, native Git, and GitHub CLI
  assumptions;
- confirmation that no remote operation occurred; and
- one recommended next action: request approval to push `ci/automation` and
  create the pull request.

- [ ] **Step 9: Commit documentation and final evidence**

Run:

```powershell
git add -- tests/unit/test_ci_workflow_contract.py `
  docs/testing.md PLAN.md AGENTS.md docs/HANDOFF.md
git diff --cached --check
git diff --cached
git commit -m "docs: record pre-push CI hardening"
git status --short
```

Expected: the commit contains only durable contracts/documentation and the
working tree is clean.

- [ ] **Step 10: Stop before remote mutation**

Present:

- the new local commits;
- exact local verification evidence;
- remaining hosted assumptions;
- expected required checks; and
- the documented bootstrap exception.

Do not push, create a pull request, change GitHub settings, merge, or publish
without separate approval.
