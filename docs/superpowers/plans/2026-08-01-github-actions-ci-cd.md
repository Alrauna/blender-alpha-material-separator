# GitHub Actions CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add minimal, fail-closed GitHub Actions validation for Blender 5.2.0 on Windows and Linux, plus an approval-gated manual release path that publishes a verified immutable ZIP.

**Architecture:** One standard-library Python helper owns fixed Blender download metadata, checksum consensus, archive verification, release-input validation, and file hashing. One GitHub workflow calls that helper from a two-platform validation matrix and a draft-first release job; focused unit and text-contract tests protect the security boundary without adding YAML, DNS, packaging, or setup dependencies.

**Tech Stack:** Python 3 standard library, GitHub Actions YAML, GitHub-hosted `windows-2025` and `ubuntu-24.04` runners, native `curl`, Blender 5.2.0 CLI, GitHub CLI, `unittest`.

## Global Constraints

- Work on `ci/automation`; do not alter remotes, push, create a pull request, change repository visibility, configure protection, or publish a release without separate approval.
- Extension version is `1.0.0`; public API remains `1.2`.
- Use Blender `5.2.0` exactly.
- Windows archive is `blender-5.2.0-windows-x64.zip` with SHA-256 `2d184b626c001692c362291911293b6a297179d618d95e9e9192c3a80318adc4`.
- Linux archive is `blender-5.2.0-linux-x64.tar.xz` with SHA-256 `96f6c181a30f4950607839dc84d42a354b250d8a0231b098b59b7bc69c351c48`.
- Official checksum URL is `https://download.blender.org/release/Blender5.2/blender-5.2.0.sha256`.
- Pin `actions/checkout` to full SHA `3d3c42e5aac5ba805825da76410c181273ba90b1` and set `persist-credentials: false`.
- Use only GitHub-hosted runners, native runner tools, Blender, GitHub CLI, and Python standard-library code.
- Do not add third-party actions, setup actions, package installers, caches, artifacts, containers, self-hosted runners, schedules, `pull_request_target`, secrets, or long-lived credentials.
- Default workflow permission is `contents: read`; only the publication job receives `contents: write`.
- Validation ZIPs are built independently on each runner and discarded with that runner.
- Publication rebuilds a fresh ZIP; no validation artifact crosses a job boundary.
- Resolver-consensus downloads must use system DNS, Cloudflare DoH, and Quad9 DoH, require identical checksum bytes, require HTTPS/TLS, reject redirects, and agree with the committed hash before extraction.
- Exact DNS IP comparison, certificate pinning, fixed IPs, external DNS libraries, and fallback to weaker verification are excluded.
- Hosted-runner performance thresholds are excluded; correctness benchmark contracts remain part of the ordinary suite.
- Private `.local-references/` data is excluded. This CI-only change does not require the private before/after smoke.
- Each coherent local task ends with focused tests, the applicable broader gate, staged-diff inspection, and a local commit.

## File Map

- Create `scripts/ci.py`: fixed trust anchors, fail-closed downloads, checksum parsing, archive verification, Blender discovery/version verification, release identity validation, SHA-256 generation, and a small command-line interface.
- Create `tests/unit/test_ci.py`: generated tests for the helper's trust and release boundaries.
- Create `tests/unit/test_ci_workflow_contract.py`: dependency-free text contracts for the security-sensitive workflow structure.
- Create `.github/workflows/ci.yml`: Windows/Linux validation and protected manual publication.
- Modify `docs/testing.md`: local and hosted CI commands, trust model, performance boundary, and rollout checks.
- Modify `PLAN.md`: CI/CD milestone status.
- Modify `AGENTS.md`: durable workflow security and validation rules.
- Modify `docs/HANDOFF.md`: exact local/remote validation evidence and next action.

---

### Task 1: Verified Blender Bootstrap Helper

**Files:**
- Create: `tests/unit/test_ci.py`
- Create: `scripts/ci.py`

**Interfaces:**
- Produces: `PLATFORMS: dict[str, dict[str, str]]`
- Produces: `parse_checksum_manifest(payload: bytes) -> dict[str, str]`
- Produces: `require_checksum_consensus(payloads: tuple[bytes, bytes, bytes], filename: str, expected_sha256: str) -> None`
- Produces: `sha256_file(path: Path) -> str`
- Produces: `curl_command(url: str, output: Path, doh_url: str | None = None) -> list[str]`
- Produces: `download(url: str, output: Path, doh_url: str | None = None) -> None`
- Produces: `prepare_blender(platform: str, output_dir: Path, github_output: Path | None = None) -> tuple[Path, Path]`

- [ ] **Step 1: Add generated RED tests for fixed trust anchors and checksum parsing**

Create `tests/unit/test_ci.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts import ci


WINDOWS_SHA256 = (
    "2d184b626c001692c362291911293b6a"
    "297179d618d95e9e9192c3a80318adc4"
)
LINUX_SHA256 = (
    "96f6c181a30f4950607839dc84d42a35"
    "4b250d8a0231b098b59b7bc69c351c48"
)


class CiTrustTests(unittest.TestCase):
    def test_fixed_blender_5_2_0_trust_anchors(self) -> None:
        self.assertEqual(ci.BLENDER_VERSION, "5.2.0")
        self.assertEqual(
            ci.CHECKSUM_URL,
            "https://download.blender.org/release/Blender5.2/"
            "blender-5.2.0.sha256",
        )
        self.assertEqual(
            ci.PLATFORMS["windows"]["filename"],
            "blender-5.2.0-windows-x64.zip",
        )
        self.assertEqual(ci.PLATFORMS["windows"]["sha256"], WINDOWS_SHA256)
        self.assertEqual(
            ci.PLATFORMS["linux"]["filename"],
            "blender-5.2.0-linux-x64.tar.xz",
        )
        self.assertEqual(ci.PLATFORMS["linux"]["sha256"], LINUX_SHA256)

    def test_parse_checksum_manifest_rejects_missing_duplicate_and_bad_rows(self) -> None:
        valid = (
            f"{WINDOWS_SHA256}  blender-5.2.0-windows-x64.zip\n"
            f"{LINUX_SHA256}  blender-5.2.0-linux-x64.tar.xz\n"
        ).encode()
        self.assertEqual(
            ci.parse_checksum_manifest(valid)["blender-5.2.0-windows-x64.zip"],
            WINDOWS_SHA256,
        )
        for payload in (
            b"",
            b"not-a-sha  archive.zip\n",
            (
                f"{WINDOWS_SHA256}  archive.zip\n"
                f"{WINDOWS_SHA256}  archive.zip\n"
            ).encode(),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    ci.parse_checksum_manifest(payload)

    def test_resolver_payloads_and_committed_hash_must_all_agree(self) -> None:
        filename = "blender-5.2.0-windows-x64.zip"
        payload = f"{WINDOWS_SHA256}  {filename}\n".encode()
        ci.require_checksum_consensus(
            (payload, payload, payload), filename, WINDOWS_SHA256
        )
        with self.assertRaisesRegex(ValueError, "resolver"):
            ci.require_checksum_consensus(
                (payload, payload + b"\n", payload), filename, WINDOWS_SHA256
            )
        with self.assertRaisesRegex(ValueError, "committed"):
            ci.require_checksum_consensus(
                (payload, payload, payload), filename, "0" * 64
            )

    def test_sha256_file_hashes_bytes_without_loading_the_whole_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.bin"
            path.write_bytes(b"alpha-material-separator")
            self.assertEqual(
                ci.sha256_file(path),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_ci -v
```

Expected: `ERROR` because `scripts.ci` does not exist.

- [ ] **Step 3: Add RED tests for fail-closed curl arguments**

Add to `CiTrustTests`:

```python
    def test_curl_command_requires_https_tls_no_redirect_and_optional_doh(self) -> None:
        output = Path("checksum.txt")
        plain = ci.curl_command(ci.CHECKSUM_URL, output)
        cloudflare = ci.curl_command(
            ci.CHECKSUM_URL,
            output,
            "https://cloudflare-dns.com/dns-query",
        )
        self.assertIn("--proto", plain)
        self.assertIn("=https", plain)
        self.assertIn("--tlsv1.2", plain)
        self.assertIn("--fail", plain)
        self.assertIn("--write-out", plain)
        self.assertNotIn("--location", plain)
        self.assertNotIn("--doh-url", plain)
        self.assertEqual(
            cloudflare[cloudflare.index("--doh-url") + 1],
            "https://cloudflare-dns.com/dns-query",
        )
        with self.assertRaises(ValueError):
            ci.curl_command("http://download.blender.org/file", output)
```

- [ ] **Step 4: Implement the minimum trust helper**

Create `scripts/ci.py` with:

```python
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


BLENDER_VERSION = "5.2.0"
BASE_URL = "https://download.blender.org/release/Blender5.2"
CHECKSUM_URL = f"{BASE_URL}/blender-5.2.0.sha256"
DOH_URLS = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.quad9.net/dns-query",
)
PLATFORMS = {
    "windows": {
        "filename": "blender-5.2.0-windows-x64.zip",
        "sha256": (
            "2d184b626c001692c362291911293b6a"
            "297179d618d95e9e9192c3a80318adc4"
        ),
        "executable": "blender.exe",
        "python_pattern": "python.exe",
    },
    "linux": {
        "filename": "blender-5.2.0-linux-x64.tar.xz",
        "sha256": (
            "96f6c181a30f4950607839dc84d42a35"
            "4b250d8a0231b098b59b7bc69c351c48"
        ),
        "executable": "blender",
        "python_pattern": "python3.*",
    },
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def parse_checksum_manifest(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not _SHA256.fullmatch(parts[0].lower()):
            raise ValueError("malformed checksum row")
        digest, filename = parts[0].lower(), parts[1].removeprefix("*")
        if filename in result:
            raise ValueError(f"duplicate checksum entry: {filename}")
        result[filename] = digest
    if not result:
        raise ValueError("empty checksum manifest")
    return result


def require_checksum_consensus(
    payloads: tuple[bytes, bytes, bytes],
    filename: str,
    expected_sha256: str,
) -> None:
    if len(set(payloads)) != 1:
        raise ValueError("resolver checksum payloads disagree")
    actual = parse_checksum_manifest(payloads[0]).get(filename)
    if actual is None:
        raise ValueError(f"checksum entry is missing: {filename}")
    if actual != expected_sha256:
        raise ValueError("official checksum disagrees with committed checksum")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def curl_command(
    url: str, output: Path, doh_url: str | None = None
) -> list[str]:
    if urlparse(url).scheme != "https":
        raise ValueError("HTTPS is required")
    command = [
        "curl",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--fail",
        "--silent",
        "--show-error",
        "--output",
        str(output),
        "--write-out",
        "%{http_code}",
    ]
    if doh_url:
        if urlparse(doh_url).scheme != "https":
            raise ValueError("DNS-over-HTTPS requires HTTPS")
        command.extend(("--doh-url", doh_url))
    return [*command, url]


def download(url: str, output: Path, doh_url: str | None = None) -> None:
    result = subprocess.run(
        curl_command(url, output, doh_url),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode or result.stdout != "200":
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"download failed with curl={result.returncode}, "
            f"http={result.stdout!r}: {result.stderr.strip()}"
        )


def _write_github_output(path: Path | None, **values: str | Path) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            text = str(value)
            if "\n" in text or "\r" in text:
                raise ValueError("GitHub outputs must be single-line")
            stream.write(f"{key}={text}\n")


def prepare_blender(
    platform: str,
    output_dir: Path,
    github_output: Path | None = None,
) -> tuple[Path, Path]:
    metadata = PLATFORMS[platform]
    output_dir.mkdir(parents=True, exist_ok=False)
    checksum_paths = tuple(
        output_dir / f"checksums-{index}.txt" for index in range(3)
    )
    download(CHECKSUM_URL, checksum_paths[0])
    for path, doh_url in zip(checksum_paths[1:], DOH_URLS, strict=True):
        download(CHECKSUM_URL, path, doh_url)
    payloads = tuple(path.read_bytes() for path in checksum_paths)
    require_checksum_consensus(
        payloads, metadata["filename"], metadata["sha256"]
    )
    archive = output_dir / metadata["filename"]
    download(f"{BASE_URL}/{metadata['filename']}", archive)
    if sha256_file(archive) != metadata["sha256"]:
        raise ValueError("downloaded archive hash mismatch")
    extract_dir = output_dir / "blender"
    shutil.unpack_archive(archive, extract_dir)
    executable_matches = list(extract_dir.rglob(metadata["executable"]))
    if len(executable_matches) != 1:
        raise ValueError("expected exactly one Blender executable")
    blender = executable_matches[0].resolve()
    python_matches = [
        path.resolve()
        for path in blender.parent.joinpath("5.2", "python", "bin").glob(
            metadata["python_pattern"]
        )
        if path.is_file() and "config" not in path.name
    ]
    if not python_matches:
        raise ValueError("bundled Python executable was not found")
    python = min(python_matches, key=lambda path: len(path.name))
    version = subprocess.run(
        [str(blender), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    if version != "Blender 5.2.0":
        raise ValueError(f"unexpected Blender version: {version!r}")
    _write_github_output(github_output, blender=blender, python=python)
    return blender, python
```

Add an `argparse` `prepare-blender` subcommand that calls `prepare_blender()`. Do not add retries or alternate mirrors: a trust-chain failure stops the job.

- [ ] **Step 5: Run focused and complete unit tests**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all tests pass.

- [ ] **Step 6: Exercise the real Windows download trust chain**

Run:

```powershell
& $Python52 scripts/ci.py prepare-blender `
  --platform windows `
  --output-dir .test-output/ci/blender-windows
```

Expected: exit `0`; three checksum downloads agree, the Windows archive matches all approved hashes before extraction, and the executable reports `Blender 5.2.0`. If native `curl` lacks working `--doh-url`, stop and report the runner/tool limitation; do not weaken or bypass consensus.

- [ ] **Step 7: Commit the verified bootstrap**

```powershell
git add scripts/ci.py tests/unit/test_ci.py
git diff --cached --check
git diff --cached
git commit -m "ci: add verified Blender bootstrap"
```

### Task 2: Two-Platform Read-Only Validation Workflow

**Files:**
- Create: `tests/unit/test_ci_workflow_contract.py`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `python scripts/ci.py prepare-blender --platform <windows|linux> --output-dir <path> --github-output <path>`
- Produces: stable checks `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2`

- [ ] **Step 1: Add the RED workflow security contract**

Create `tests/unit/test_ci_workflow_contract.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


class CiWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_validation_triggers_and_stable_names(self) -> None:
        for text in (
            "pull_request:",
            "push:",
            "branches: [main]",
            "workflow_dispatch:",
            "CI / ${{ matrix.label }} — Blender 5.2",
            "runner: windows-2025",
            "runner: ubuntu-24.04",
            "label: Windows",
            "label: Linux",
        ):
            self.assertIn(text, self.text)
        self.assertNotIn("pull_request_target", self.text)
        self.assertNotIn("schedule:", self.text)

    def test_checkout_and_default_permissions_are_locked_down(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA}", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertEqual(self.text.count("actions/checkout@"), 2)

    def test_no_unapproved_actions_or_execution_surfaces(self) -> None:
        action_uses = re.findall(r"^\s*uses:\s*(\S+)", self.text, re.MULTILINE)
        self.assertEqual(
            action_uses,
            [f"actions/checkout@{CHECKOUT_SHA}"] * 2,
        )
        for forbidden in (
            "actions/cache",
            "actions/upload-artifact",
            "actions/download-artifact",
            "setup-python",
            "container:",
            "self-hosted",
            "secrets.",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_validation_runs_the_complete_project_gate(self) -> None:
        for text in (
            "scripts/ci.py prepare-blender",
            "-m unittest discover -s tests/unit -t . -v",
            "--disable-autoexec",
            "--python tests/blender/run_all.py",
            "--command extension validate addon",
            "--command extension build --source-dir addon",
            "--command extension validate",
        ):
            self.assertIn(text, self.text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the workflow contract and confirm RED**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
```

Expected: `ERROR` because `.github/workflows/ci.yml` does not exist.

- [ ] **Step 3: Add the minimal validation workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      version:
        description: Release version in X.Y.Z form
        required: true
        type: string

permissions:
  contents: read

jobs:
  validate:
    name: CI / ${{ matrix.label }} — Blender 5.2
    runs-on: ${{ matrix.runner }}
    timeout-minutes: 45
    strategy:
      fail-fast: false
      matrix:
        include:
          - runner: windows-2025
            label: Windows
            platform: windows
          - runner: ubuntu-24.04
            label: Linux
            platform: linux
    steps:
      - name: Check out source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false

      - name: Verify and extract Blender 5.2.0
        id: blender
        shell: pwsh
        run: >-
          python scripts/ci.py prepare-blender
          --platform '${{ matrix.platform }}'
          --output-dir '${{ runner.temp }}/blender-5.2.0'
          --github-output $env:GITHUB_OUTPUT

      - name: Run unit tests
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.python }}'
          -m unittest discover -s tests/unit -t . -v

      - name: Run headless Blender tests
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.blender }}'
          --factory-startup --background --disable-autoexec
          --python-exit-code 1 --python tests/blender/run_all.py

      - name: Validate extension source
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.blender }}'
          --factory-startup --command extension validate addon

      - name: Build extension ZIP
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.blender }}'
          --factory-startup --command extension build
          --source-dir addon --output-dir '${{ runner.temp }}/release'

      - name: Validate extension ZIP
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.blender }}'
          --factory-startup --command extension validate
          '${{ runner.temp }}/release/alpha_material_separator-1.0.0.zip'
```

This task intentionally omits publication. The validation ZIP remains in the runner temporary directory and is never uploaded.

- [ ] **Step 4: Run focused and complete unit tests**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all tests pass.

- [ ] **Step 5: Run the complete local Blender gate**

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

Expected: the headless success markers print, source validation succeeds, the ZIP is built, and that exact ZIP validates.

- [ ] **Step 6: Commit the validation workflow**

```powershell
git add .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py
git diff --cached --check
git diff --cached
git commit -m "ci: add Windows and Linux validation"
```

### Task 3: Guarded Draft-First Publication

**Files:**
- Modify: `tests/unit/test_ci.py`
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Modify: `scripts/ci.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: `release_identity(version: str, manifest: Path) -> tuple[str, str, str]`
- Produces: `write_sha256s(archive: Path, output: Path) -> str`
- Produces: `require_file_sha256(path: Path, expected_sha256: str) -> None`
- Produces CLI: `check-release --version --manifest`
- Produces CLI: `prepare-release --version --manifest --archive --checksum-output --github-output`
- Produces CLI: `verify-file --file --expected-sha256`

- [ ] **Step 1: Add RED release-helper tests**

Add to `CiTrustTests`:

```python
    def test_release_identity_is_strict_and_matches_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "blender_manifest.toml"
            manifest.write_text('version = "1.0.0"\n', encoding="utf-8")
            self.assertEqual(
                ci.release_identity("1.0.0", manifest),
                (
                    "1.0.0",
                    "v1.0.0",
                    "alpha_material_separator-1.0.0.zip",
                ),
            )
            for value in ("v1.0.0", "1.0", "1.0.0-beta", "1.0.0\nbad"):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        ci.release_identity(value, manifest)
            with self.assertRaisesRegex(ValueError, "manifest"):
                ci.release_identity("1.0.1", manifest)

    def test_checksum_file_uses_lowercase_digest_and_archive_basename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "alpha_material_separator-1.0.0.zip"
            checksum = root / "SHA256SUMS.txt"
            archive.write_bytes(b"release")
            digest = ci.write_sha256s(archive, checksum)
            self.assertEqual(digest, hashlib.sha256(b"release").hexdigest())
            self.assertEqual(
                checksum.read_text(encoding="utf-8"),
                f"{digest}  alpha_material_separator-1.0.0.zip\n",
            )
            ci.require_file_sha256(archive, digest)
            with self.assertRaises(ValueError):
                ci.require_file_sha256(archive, "0" * 64)
```

- [ ] **Step 2: Extend the workflow contract for release gates and confirm RED**

First change both checkout-count assertions from `2` to `3`, because `release_gate` needs the manifest and `release` needs a fresh source checkout. Then add:

```python
    def test_release_is_manual_main_public_and_environment_gated(self) -> None:
        for text in (
            "if: github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/main'",
            "github.event.repository.visibility == 'public'",
            "needs: [validate, release_gate]",
            "environment: release",
            "contents: write",
        ):
            self.assertIn(text, self.text)

    def test_release_is_draft_first_and_rehashes_downloaded_asset(self) -> None:
        positions = [
            self.text.index("gh release create"),
            self.text.index("gh release upload"),
            self.text.index("gh release download"),
            self.text.index("scripts/ci.py verify-file"),
            self.text.index("gh release edit"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("--draft", self.text)
        self.assertIn("--draft=false", self.text)
        self.assertIn("SHA256SUMS.txt", self.text)
        self.assertIn("gh api graphql", self.text)
        self.assertNotIn("gh release view", self.text)

    def test_write_token_is_scoped_to_release_and_gh_steps(self) -> None:
        self.assertEqual(self.text.count("contents: write"), 1)
        self.assertNotIn("GH_TOKEN:", self.text.split("  release:", 1)[0])
        for line in self.text.splitlines():
            if "GH_TOKEN:" in line:
                self.assertIn("${{ github.token }}", line)
```

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci `
  tests.unit.test_ci_workflow_contract -v
```

Expected: failures for missing release helper functions and publication steps.

- [ ] **Step 3: Implement the release helper functions and CLI**

Add `tomllib` and:

```python
import tomllib

_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def release_identity(version: str, manifest: Path) -> tuple[str, str, str]:
    if not _VERSION.fullmatch(version):
        raise ValueError("release version must use X.Y.Z")
    manifest_version = tomllib.loads(
        manifest.read_text(encoding="utf-8")
    )["version"]
    if manifest_version != version:
        raise ValueError(
            f"manifest version {manifest_version!r} does not match {version!r}"
        )
    return (
        version,
        f"v{version}",
        f"alpha_material_separator-{version}.zip",
    )


def write_sha256s(archive: Path, output: Path) -> str:
    digest = sha256_file(archive)
    output.write_text(
        f"{digest}  {archive.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return digest


def require_file_sha256(path: Path, expected_sha256: str) -> None:
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 is malformed")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"file SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
```

Extend the `argparse` CLI:

```python
check_release = subparsers.add_parser("check-release")
check_release.add_argument("--version", required=True)
check_release.add_argument("--manifest", type=Path, required=True)

prepare_release = subparsers.add_parser("prepare-release")
prepare_release.add_argument("--version", required=True)
prepare_release.add_argument("--manifest", type=Path, required=True)
prepare_release.add_argument("--archive", type=Path, required=True)
prepare_release.add_argument("--checksum-output", type=Path, required=True)
prepare_release.add_argument("--github-output", type=Path, required=True)

verify_file = subparsers.add_parser("verify-file")
verify_file.add_argument("--file", type=Path, required=True)
verify_file.add_argument("--expected-sha256", required=True)
```

The `check-release` branch calls `release_identity()`. The `prepare-release` branch requires the returned archive basename, writes `SHA256SUMS.txt`, and appends `version`, `tag`, `archive_name`, and `sha256` as single-line GitHub outputs. The `verify-file` branch calls `require_file_sha256()`.

- [ ] **Step 4: Add the read-only release gate and protected publication job**

Extend `.github/workflows/ci.yml`:

```yaml
  release_gate:
    name: Release input gate
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - name: Check out source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false

      - name: Require main, public visibility, and manifest version
        shell: pwsh
        run: |
          if ('${{ github.ref }}' -ne 'refs/heads/main') {
            throw 'Release dispatch must use main.'
          }
          if ('${{ github.event.repository.visibility }}' -ne 'public') {
            throw 'Release publication requires a public repository.'
          }
          python scripts/ci.py check-release `
            --version '${{ inputs.version }}' `
            --manifest addon/blender_manifest.toml

  release:
    name: Publish immutable release
    if: >-
      github.event_name == 'workflow_dispatch' &&
      github.ref == 'refs/heads/main' &&
      github.event.repository.visibility == 'public'
    needs: [validate, release_gate]
    runs-on: windows-2025
    timeout-minutes: 45
    environment: release
    permissions:
      contents: write
    steps:
      - name: Check out source
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          persist-credentials: false

      - name: Verify and extract Blender 5.2.0
        id: blender
        shell: pwsh
        run: >-
          python scripts/ci.py prepare-blender
          --platform windows
          --output-dir '${{ runner.temp }}/blender-5.2.0'
          --github-output $env:GITHUB_OUTPUT

      - name: Build fresh extension ZIP
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.blender }}'
          --factory-startup --command extension build
          --source-dir addon --output-dir '${{ runner.temp }}/release'

      - name: Validate fresh extension ZIP
        shell: pwsh
        run: >-
          & '${{ steps.blender.outputs.blender }}'
          --factory-startup --command extension validate
          '${{ runner.temp }}/release/alpha_material_separator-${{ inputs.version }}.zip'

      - name: Prepare release identity and checksum
        id: release
        shell: pwsh
        run: >-
          python scripts/ci.py prepare-release
          --version '${{ inputs.version }}'
          --manifest addon/blender_manifest.toml
          --archive '${{ runner.temp }}/release/alpha_material_separator-${{ inputs.version }}.zip'
          --checksum-output '${{ runner.temp }}/release/SHA256SUMS.txt'
          --github-output $env:GITHUB_OUTPUT

      - name: Refuse an existing tag or release
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          $Owner, $Name = $env:GITHUB_REPOSITORY.Split('/', 2)
          $Query = @'
          query($owner:String!, $name:String!, $ref:String!, $tag:String!) {
            repository(owner:$owner, name:$name) {
              ref(qualifiedName:$ref) { name }
              release(tagName:$tag) { id }
            }
          }
          '@
          $Tag = '${{ steps.release.outputs.tag }}'
          $State = gh api graphql -f query=$Query `
            -f owner=$Owner -f name=$Name -f ref="refs/tags/$Tag" -f tag=$Tag |
            ConvertFrom-Json
          if ($LASTEXITCODE -ne 0) {
            throw 'Could not verify tag and release absence.'
          }
          if ($State.data.repository.ref) { throw 'Release tag already exists.' }
          if ($State.data.repository.release) { throw 'Release already exists.' }

      - name: Create draft release
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: >-
          gh release create '${{ steps.release.outputs.tag }}'
          --draft --generate-notes
          --title '${{ steps.release.outputs.tag }}'
          --target '${{ github.sha }}'

      - name: Upload release assets
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: >-
          gh release upload '${{ steps.release.outputs.tag }}'
          '${{ runner.temp }}/release/${{ steps.release.outputs.archive_name }}'
          '${{ runner.temp }}/release/SHA256SUMS.txt'

      - name: Download stored ZIP
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          New-Item -ItemType Directory '${{ runner.temp }}/downloaded-release'
          gh release download '${{ steps.release.outputs.tag }}' `
            --pattern '${{ steps.release.outputs.archive_name }}' `
            --dir '${{ runner.temp }}/downloaded-release'

      - name: Verify stored ZIP hash
        shell: pwsh
        run: >-
          python scripts/ci.py verify-file
          --file '${{ runner.temp }}/downloaded-release/${{ steps.release.outputs.archive_name }}'
          --expected-sha256 '${{ steps.release.outputs.sha256 }}'

      - name: Publish verified draft
        shell: pwsh
        env:
          GH_TOKEN: ${{ github.token }}
        run: >-
          gh release edit '${{ steps.release.outputs.tag }}' --draft=false
```

Keep `GH_TOKEN` off job-level and workflow-level `env`; only the five `gh` command steps receive it. The GraphQL absence check distinguishes a valid `null` result from transport or API failure, which remains fatal. If any step after draft creation fails, leave the draft intact.

- [ ] **Step 5: Run focused and complete unit tests**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci `
  tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit guarded publication**

```powershell
git add scripts/ci.py tests/unit/test_ci.py `
  tests/unit/test_ci_workflow_contract.py .github/workflows/ci.yml
git diff --cached --check
git diff --cached
git commit -m "ci: add guarded immutable release publishing"
```

### Task 4: Durable CI and Release Documentation

**Files:**
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Modify: `docs/testing.md`
- Modify: `PLAN.md`
- Modify: `AGENTS.md`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: exact workflow names, helper commands, permissions, trust anchors, and approval boundaries from Tasks 1–3.
- Produces: durable contributor instructions and current handoff state.

- [ ] **Step 1: Add a RED documentation contract**

Extend `tests/unit/test_ci_workflow_contract.py`:

```python
    def test_ci_security_and_rollout_are_documented(self) -> None:
        testing = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        plan = (ROOT / "PLAN.md").read_text(encoding="utf-8")
        for text in (
            "CI / Windows — Blender 5.2",
            "CI / Linux — Blender 5.2",
            "Blender 5.2.0",
            "Cloudflare",
            "Quad9",
            "SHA256SUMS.txt",
            "performance threshold",
        ):
            self.assertIn(text, testing)
        for text in (
            "actions/checkout",
            "persist-credentials: false",
            "contents: read",
            "contents: write",
            "Do not push",
        ):
            self.assertIn(text, agents)
        self.assertIn("GitHub Actions CI/CD", plan)
```

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Expected: fail because durable CI guidance is absent from one or more documents.

- [ ] **Step 2: Document the exact hosted and local gates**

Add `GitHub Actions CI/CD` to `docs/testing.md`, stating:

- the two exact required check names;
- PR, `main` push, and manual dispatch behavior;
- fixed Blender 5.2.0 archives and committed SHA-256 trust anchors;
- system DNS, Cloudflare DoH, and Quad9 DoH checksum-byte consensus;
- source, headless, build, and exact-ZIP validation;
- validation ZIP disposal and fresh publication build;
- draft, upload, download, re-hash, publication order;
- no hosted-runner 25 percent performance gate;
- the private smoke exclusion for CI-only changes;
- the exact local commands from Task 5.

- [ ] **Step 3: Add the CI milestone to `PLAN.md`**

Add:

```markdown
## Milestone 6 — GitHub Actions CI/CD

- [x] Fix Blender 5.2.0 Windows and Linux download identities and hashes.
- [x] Add generated helper and workflow security contracts.
- [x] Add read-only Windows and Linux validation.
- [x] Add protected manual draft-first publication.
- [x] Run the complete local gate.
- [ ] Push `ci/automation` after separate approval.
- [ ] Observe both hosted validation checks.
- [ ] Make the repository public after separate approval.
- [ ] Configure required checks, the `release` environment, and immutable releases.
- [ ] Dispatch and verify release `1.0.0` after separate approval.
```

Only mark a local item complete after its exact command passes. Leave every remote item unchecked.

- [ ] **Step 4: Add durable workflow rules to `AGENTS.md`**

Add:

```markdown
## CI/CD security

- Keep `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2` stable; both
  are required merge checks once repository protection is configured.
- Keep workflow permissions read-only by default. Only the protected manual
  release job may use `contents: write`, and `GH_TOKEN` belongs only on the
  individual `gh` command steps.
- Keep every action pinned to a reviewed full commit SHA with checkout
  credential persistence disabled. Adding an action, dependency, cache,
  artifact transfer, trigger, runner type, permission, or network source
  requires design review and explicit approval.
- Blender downloads must retain the fixed HTTPS identity, committed SHA-256,
  three-path checksum consensus, pre-extraction archive hash, and executable
  version check. Never weaken a failed trust check to make CI pass.
- Validation builds are disposable. Publication rebuilds from the validated
  `main` commit, creates a draft, uploads ZIP and checksum, downloads and
  re-hashes the stored ZIP, then publishes.
- Do not push, change visibility or repository settings, configure protection,
  create tags, or publish releases without explicit user approval.
```

- [ ] **Step 5: Update the handoff with exact evidence**

Replace completed history that no longer needs immediate attention with:

- current objective and completed CI commits;
- exact RED/GREEN commands and results;
- local Blender trust-chain outcome;
- full local gate outcome;
- unverified hosted-runner assumptions;
- absent remote settings;
- single next action: request approval to push `ci/automation` and observe both checks.

- [ ] **Step 6: Run documentation and diff checks**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Expected: all tests pass and `git diff --check` prints nothing.

- [ ] **Step 7: Commit durable documentation**

```powershell
git add tests/unit/test_ci_workflow_contract.py `
  docs/testing.md PLAN.md AGENTS.md docs/HANDOFF.md
git diff --cached --check
git diff --cached
git commit -m "docs: document CI and immutable releases"
```

### Task 5: Local Completion and Security Review

**Files:**
- Modify only when a verified finding requires correction: `scripts/ci.py`, `.github/workflows/ci.yml`, tests, and current documentation.
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: all local deliverables from Tasks 1–4.
- Produces: a reviewed local branch ready for a separately approved remote bootstrap.

- [ ] **Step 1: Run the complete local gate from a clean command context**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-1.0.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
git status --short
```

Expected: all unit tests pass; the headless suite prints both success markers; source and exact archive validation succeed; diff check is clean; status contains only intended CI/CD files.

- [ ] **Step 2: Perform correctness and minimalism reviews**

Use `superpowers:requesting-code-review` to check:

- validation jobs cannot write;
- project tests never receive `GH_TOKEN`;
- publication cannot run from a branch or private repository;
- every download is fixed, TLS-only, redirect-rejecting, and hash-checked;
- failed publication leaves a draft rather than overwriting or deleting;
- both platform jobs execute identical product gates.

Use `ponytail:ponytail-review` to identify removable helpers, duplicated commands, or speculative workflow machinery. Retain explicit trust-boundary validation even when it costs lines.

- [ ] **Step 3: Correct only verified findings with RED/GREEN coverage**

For each accepted production finding:

1. Add or tighten one focused failing assertion in `test_ci.py` or `test_ci_workflow_contract.py`.
2. Run that test and record the intended failure.
3. Make the smallest correction.
4. Run the focused test and full unit suite.

Do not weaken the approved security model to address hosted-runner uncertainty.

- [ ] **Step 4: Refresh the handoff and commit final local evidence**

Update `docs/HANDOFF.md`, then run:

```powershell
git add docs/HANDOFF.md
git diff --cached --check
git diff --cached
git commit -m "docs: record local CI validation"
git status --short
```

If Task 4 already contains the final handoff state, skip the empty commit.

### Task 6: Approval-Gated GitHub Bootstrap

**Files:**
- No planned local file changes unless hosted checks reveal a reproducible runner-specific defect.

**Interfaces:**
- Consumes: clean local `ci/automation`.
- Produces: first Windows and Linux check runs and a pull request eligible for protection configuration.

- [ ] **Step 1: Stop and obtain explicit approval for remote mutation**

Present the local commits, full local validation evidence, branch to push, expected checks, and the documented bootstrap exception. Do not continue until the user explicitly approves push and pull-request creation.

- [ ] **Step 2: Push and open the pull request after approval**

Run:

```powershell
git push -u origin ci/automation
gh pr create --base main --head ci/automation `
  --title "ci: add verified cross-platform validation and releases" `
  --body "Adds pinned Windows/Linux Blender 5.2.0 validation and protected manual draft-first release publication."
```

- [ ] **Step 3: Observe both checks without weakening security**

Run:

```powershell
gh pr checks --watch
```

Expected checks:

```text
CI / Windows — Blender 5.2
CI / Linux — Blender 5.2
```

Both must pass. If either fails, use `github:gh-fix-ci`, reproduce the runner defect with a focused contract where practical, and request approval before changing a security boundary.

- [ ] **Step 4: Stop before repository settings or merge**

Report hosted outcomes. Do not make the repository public, configure rules, merge, dispatch, tag, or publish without separate approval.

### Task 7: Approval-Gated Protection and First Release

**Files:**
- Update after verified remote completion: `docs/testing.md`, `PLAN.md`, `docs/HANDOFF.md`

**Interfaces:**
- Consumes: passing pull-request checks and separate approval for each remote mutation group.
- Produces: protected `main` and a verified immutable `v1.0.0` release.

- [ ] **Step 1: Obtain approval and make the repository public**

After explicit approval:

```powershell
gh repo edit --visibility public --accept-visibility-change-consequences
```

Verify public visibility before proceeding.

- [ ] **Step 2: Configure protection through GitHub's native settings**

In repository settings:

1. Require a pull request before merging to `main`.
2. Require `CI / Windows — Blender 5.2`.
3. Require `CI / Linux — Blender 5.2`.
4. Require branches to be up to date before merging.
5. Block force pushes and branch deletion.
6. Apply the rule to administrators when the repository plan supports it.
7. Create environment `release`, restrict deployment branches to `main`, and add the approved reviewer requirement.
8. Enable immutable releases.

Verify each setting before merging.

- [ ] **Step 3: Obtain merge approval, merge, and observe `main`**

After explicit approval:

```powershell
gh pr merge --merge --delete-branch=false
gh run list --branch main --workflow CI --limit 2
```

Wait until both `main` validation entries pass.

- [ ] **Step 4: Obtain release approval and dispatch `1.0.0`**

After explicit approval:

```powershell
gh workflow run CI --ref main -f version=1.0.0
gh run list --workflow CI --limit 1
```

Approve the protected `release` environment only after both platform jobs and the release-input gate pass.

- [ ] **Step 5: Verify the published immutable release**

Run:

```powershell
gh release view v1.0.0
gh release verify v1.0.0
gh release verify-asset v1.0.0 `
  alpha_material_separator-1.0.0.zip
```

Download `alpha_material_separator-1.0.0.zip` and `SHA256SUMS.txt` into a fresh temporary directory and independently confirm the published checksum with `Get-FileHash -Algorithm SHA256`.

- [ ] **Step 6: Record remote release evidence**

Update `docs/testing.md`, `PLAN.md`, and `docs/HANDOFF.md` with both check results, configured controls, workflow run URL and commit SHA, release tag and asset names, downloaded ZIP SHA-256, warnings, and remaining assumptions. Run unit documentation contracts and `git diff --check`, commit locally, and request approval before pushing that documentation commit.
