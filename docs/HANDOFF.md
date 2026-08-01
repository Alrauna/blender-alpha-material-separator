# Repository handoff

Updated: 2026-08-01

## Current objective

Observe and inspect the required hosted checks on draft pull request
[#2](https://github.com/Alrauna/blender-alpha-material-separator/pull/2).
Repository-setting changes, merge, tags, releases, and publication remain
separately approval-gated.

## Completed work

- Extension version remains `1.0.0`; public API remains `1.2`.
- The Windows/Linux validation matrix, guarded draft-first release path, fixed
  Blender 5.2.0 trust anchors, checksum consensus, and stored-asset re-hash were
  already implemented locally.
- `6b5103e1bf333b4525cee1f9e9c4ac1f5776f534`
  (`fix: bound Blender bootstrap operations`):
  - adds a 30-second connection timeout, 600-second total curl limit, two
    retries, and a 620-second parent-process limit;
  - removes partial downloads after timeout; and
  - uses Python's safe data extraction filter for Linux tar archives.
- `8b7de986b33e14b6efef67af332b9b0c8a50d78e`
  (`fix: isolate release write credentials`):
  - confines the pinned checkout action to the two read-only jobs;
  - uses unauthenticated native Git in the write-authorized release job;
  - fetches and verifies the exact `GITHUB_SHA`;
  - keeps dispatch context checks in workflow expressions rather than shell
    source; and
  - discovers exactly one versioned AMS ZIP in ordinary validation.
- Durable CI rules and milestone status now describe these boundaries.
- Inline correctness/security review found no accepted code finding.
- Ponytail minimalism review result: `Lean already. Ship.`
- `ci/automation` was pushed to `origin` after explicit approval.
- Draft pull request
  [#2](https://github.com/Alrauna/blender-alpha-material-separator/pull/2)
  targets `main`.

## Important decisions and constraints

- Default workflow permission is `contents: read`; only the protected manual
  release job receives `contents: write`.
- `GH_TOKEN` appears only on the five individual GitHub CLI release steps.
  Git, tests, Python, Blender, build, validation, and hashing do not receive it.
- Read-only jobs use the pinned checkout action with
  `persist-credentials: false`; the write job invokes no action.
- Blender retrieval remains HTTPS-only, redirect-rejecting, exact-HTTP-200,
  fixed-version, hash-before-extraction, and dependent on byte-identical
  system/Cloudflare/Quad9 checksum content.
- Timeouts and retries bound failure; they do not weaken resolver or hash
  requirements.
- Blender native extension-repository hosting and `index.json` publication are
  a separate milestone. AMS has no custom updater.
- The private before/after smoke is not required for this CI-only change.
- Do not change repository settings, merge, tag, release, or publish without
  explicit approval.

## Files changed and why

- `scripts/ci.py`: bounded curl execution, timeout cleanup, and safe Linux
  extraction.
- `tests/unit/test_ci.py`: RED/GREEN contracts for those helper changes.
- `.github/workflows/ci.yml`: credential-free exact-SHA release fetch,
  expression-only release gating, and version-independent ZIP validation.
- `tests/unit/test_ci_workflow_contract.py`: workflow security, credential,
  dispatch, archive-discovery, and durable-documentation contracts.
- `docs/testing.md`: current trust model and hosted/local boundary.
- `AGENTS.md`: durable checkout, token, exact-SHA, network, and version rules.
- `PLAN.md`: completed local hardening items; remote rollout remains open.
- `docs/HANDOFF.md`: current evidence, risks, and next action.

## Validation commands and results

### Task 1 RED

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_curl_command_requires_https_tls_no_redirect_and_optional_doh `
  tests.unit.test_ci.CiTrustTests.test_download_timeout_removes_partial_output `
  -v
```

Result: failed as intended because curl bounds were absent and
`subprocess.TimeoutExpired` escaped.

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_archive_extraction_uses_safe_linux_tar_filter `
  -v
```

Result: errored as intended because `extract_archive` did not exist.

### Task 1 GREEN

```powershell
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Result: 9/9 focused and 70/70 total unit tests passed; diff check was clean.

### Task 2 RED

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_checkout_and_default_permissions_are_locked_down `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_release_job_fetches_exact_public_sha_without_credentials `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_dispatch_contexts_never_enter_shell_source `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_validation_discovers_exactly_one_versioned_zip `
  -v
```

Result: all four failed as intended on the third checkout, missing native-Git
boundary, dispatch expressions in PowerShell, and hard-coded `1.0.0` ZIP.

### Task 2 GREEN

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest `
  tests.unit.test_ci tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Result: 12/12 workflow, 21/21 combined CI, and 73/73 total unit tests passed;
diff check was clean. Inspection reported zero `uses:` entries in the release
job, two total checkout actions, and five release-job `GH_TOKEN` declarations.

### Task 3 RED and GREEN

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Result: failed as intended because the durable guidance did not yet say
`unauthenticated native Git`; passed after the documentation update.

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Result: 12/12 workflow and 73/73 total unit tests passed; diff check was clean.

### Complete Blender and package gate

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

Result: Blender printed
`ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`; source and archive validation
succeeded. The rebuilt ignored ZIP is 66,755 bytes with 29 entries. Package
inspection found no `.github/`, `scripts/`, `tests/`, `.local-references/`, or
repository-documentation entries.

## Known failures, warnings, and unverified assumptions

- The tested local Windows curl/network combination still cannot complete the
  Quad9 `--doh-url` checksum request. It fails closed. System DNS and Cloudflare
  returned byte-identical checksum files in the earlier diagnostic.
- Hosted Windows/Linux execution has not yet verified runner tooling,
  PowerShell/YAML behavior, Linux bundled-Python discovery, safe tar filtering,
  exact-SHA fetch acceptance, GitHub CLI release behavior, or Quad9 DoH.
- If hosted runners reproduce the Quad9 failure, the approved fallback is a
  minimal standard-library RFC 8484 client that preserves Quad9, TLS hostname
  validation, dynamic Blender addresses, and byte consensus.
- Expected local output includes Grease Pencil asset-path warnings, the
  deliberate stale-input warning, and LF-to-CRLF Git notices.
- `.packaged-releases/alpha_material_separator-1.0.0.zip` is ignored and must
  not be committed.

## Remaining tasks in priority order

1. Inspect both required hosted checks:
   `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2`.
2. Use the RFC 8484 contingency only if hosted runners reproduce the Quad9
   failure.
3. Separately approve repository visibility, required-check protection,
   release-environment protection, merge, and the first `1.0.0` publication.
4. Plan Blender native extension-repository hosting as a separate milestone.

## Recommended next action

Inspect the Windows and Linux checks on draft pull request #2.
