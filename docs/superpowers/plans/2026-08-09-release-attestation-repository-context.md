# Release Attestation Repository Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both no-checkout release jobs address the intended GitHub repository explicitly.

**Architecture:** Preserve the approved three-job release boundary. Supply GitHub CLI's missing repository context with the runner-provided `GITHUB_REPOSITORY` environment variable in both the attestation download and publication command, and lock that behavior with one source-level workflow contract.

**Tech Stack:** GitHub Actions YAML, PowerShell 7, GitHub CLI, Python 3.13 `unittest`.

## Global Constraints

- Keep `actions/attest` pinned to `1e69f48acb82d1966a394da916b4c1698aa569d6`.
- Keep the attestation job permissions exactly `contents: read`, `id-token: write`, and `attestations: write`.
- Do not add a checkout, action, dependency, permission, token, trigger, runner, artifact transfer, or network source.
- Do not delete, publish, or otherwise mutate the failed hosted v1.3.1 draft.
- Preserve stable Windows, Linux, and macOS validation jobs and names.

---

### Task 1: Reproduce and correct missing GitHub CLI repository context

**Files:**
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: GitHub Actions' standard `GITHUB_REPOSITORY=owner/repository` environment variable.
- Produces: an explicit `--repo $env:GITHUB_REPOSITORY` selector for the no-checkout `gh release download` and `gh release edit` commands.

- [ ] **Step 1: Write the failing workflow contract**

Add this method to `CiWorkflowContractTests`:

```python
def test_no_checkout_release_commands_select_repository_explicitly(self) -> None:
    attestation = self.text.split(
        "\n  release_attestation:\n", 1
    )[1].split("\n  release_publish:\n", 1)[0]
    publish = self.text.split("\n  release_publish:\n", 1)[1]
    for section in (attestation, publish):
        self.assertNotIn("actions/checkout@", section)
        self.assertIn("--repo $env:GITHUB_REPOSITORY", section)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_no_checkout_release_commands_select_repository_explicitly `
  -v
```

Expected for the initial hosted regression: FAIL because the attestation
section lacks `--repo $env:GITHUB_REPOSITORY` while confirming it has no
checkout. After correcting attestation, rerun the expanded contract and expect
it to fail because the publish section lacks the same explicit selector.

- [ ] **Step 3: Make the minimum workflow correction**

Change only the two no-checkout GitHub CLI commands:

```powershell
gh release download $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  --pattern $env:ARCHIVE_NAME `
  --dir $DownloadDirectory

gh release edit $env:RELEASE_TAG `
  --repo $env:GITHUB_REPOSITORY `
  --draft=false
```

- [ ] **Step 4: Verify GREEN and affected workflow contracts**

Run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_no_checkout_release_commands_select_repository_explicitly `
  -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest tests.unit.test_ci_workflow_contract -v
```

Expected: the new test and complete workflow contract module pass.

- [ ] **Step 5: Run the change gate**

Run the complete unit suite, headless Blender suite, source validation,
`git diff --check`, and a clean 1.3.1 archive build/validation. Expected: all
pass, with exactly one discovered `alpha_material_separator-1.3.1.zip`.

- [ ] **Step 6: Review and close the milestone**

Review the full branch diff for accidental permission, action, trigger, runner,
token, or release-scope changes. Update `docs/HANDOFF.md` with the hosted root
cause, failed-draft state, TDD evidence, validation, and separately authorized
recovery action. Delete this completed plan and its design spec, then commit the
verified correction and documentation closeout in coherent commits.
