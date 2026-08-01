# Repository handoff

Updated: 2026-08-01

## Current objective

Obtain user approval of the test-first human-first README implementation plan
in `docs/superpowers/plans/2026-08-01-human-first-readme.md`, then execute it
using the selected workflow. The README rewrite has not begun.
Separately, the locally corrected Blender bootstrap still requires explicit
approval before it may be pushed to draft pull request
[#2](https://github.com/Alrauna/blender-alpha-material-separator/pull/2).

## Completed work

- Extension version remains `1.0.0`; public API remains `1.2`.
- The first hosted run, `30698781877`, established two independent failures:
  - Windows curl could not resolve the checksum host through Quad9 DoH.
  - Linux successfully downloaded, hashed, and extracted Blender, then the
    recursive executable search found more than one `blender` path.
- The local fix replaces only the incompatible Quad9 request with a
  standard-library DoT query to `dns.quad9.net:853`. The resulting address is
  passed to curl with `--resolve`, so HTTPS still validates
  `download.blender.org`.
- Linux and Windows executable discovery now requires the exact root derived
  from the fixed official archive name rather than recursively searching.
- The existing system-DNS, Cloudflare-DoH, and Quad9 byte-consensus gate,
  committed SHA-256 anchors, safe extraction, timeouts, and retries remain.
- New generated tests recorded RED before the production changes and GREEN
  after them.
- Durable CI documentation now describes Quad9 DoT and exact-root discovery.
- `7c9db1c` (`fix: make Blender bootstrap portable`) contains the focused
  production and generated-test changes.
- `704e3e7` (`docs: record portable Blender bootstrap`) contains the durable
  guidance, plan status, and validation record.
- `782ebb3` (`fix: harden Quad9 DNS handling`) rejects truncated, malformed,
  mismatched-question, and non-answer-only responses and gives curl every
  distinct authenticated A answer.
- `ed39d88` (`docs: record strict Quad9 validation`) records that hardening.
- `6958325` (`fix: validate Quad9 answer ownership`) additionally binds each
  direct A owner to the question, accepts compression only at validated label
  boundaries, enforces the DNS 255-byte name limit, and caps distinct
  addresses at 16.
- `095fc2c` (`docs: design human-first README`) records the approved
  end-user-only, renderer-agnostic README structure. No README content or
  contract test has changed yet.
- `2b981a5` (`docs: plan human-first README rewrite`) records the self-reviewed
  RED/GREEN implementation plan. No README content or contract test has changed
  yet.
- No workflow YAML, extension code, remote, or GitHub setting was changed.
- Nothing from this local correction has been pushed.

## Important decisions and constraints

- Default workflow permission is `contents: read`; only the protected manual
  release job receives `contents: write`.
- Blender retrieval remains HTTPS-only, redirect-rejecting, exact-HTTP-200,
  fixed-version, hash-before-extraction, and dependent on byte-identical
  system-DNS, Cloudflare-DoH, and Quad9-DoT checksum content.
- Quad9 DoT uses the operating system trust store to validate
  `dns.quad9.net`; the subsequent pinned download separately validates
  `download.blender.org`.
- The trust gates fail closed. Port 853 availability on both GitHub-hosted
  runners must be proven by the next hosted run.
- Blender native extension-repository hosting remains a separate milestone.
- The private before/after smoke is not required for this CI-only change.
- Do not push, merge, tag, release, publish, or change repository settings
  without explicit approval.

## Files changed and why

- `scripts/ci.py`: strict DoT query/response handling, multi-address curl
  pinning, and exact archive-root executable discovery.
- `tests/unit/test_ci.py`: generated RED/GREEN coverage for validated DoT,
  malformed responses, hostname-preserving multi-address curl pinning, and
  exact-root discovery.
- `tests/unit/test_ci_workflow_contract.py`: durable-documentation contract for
  the approved resolver and extraction behavior.
- `docs/testing.md`: current trust model, hosted failure, and rerun boundary.
- `AGENTS.md`: durable Quad9 DoT and exact-root CI rules.
- `PLAN.md`: completed local correction and open hosted rerun.
- `docs/HANDOFF.md`: current evidence, warnings, and next action.

## Validation commands and results

### Hosted failure evidence

- Windows job:
  `https://github.com/Alrauna/blender-alpha-material-separator/actions/runs/30698781877/job/91366015572`
  failed with curl exit `6`, HTTP `000`, and
  `Could not resolve host: download.blender.org`.
- Linux job:
  `https://github.com/Alrauna/blender-alpha-material-separator/actions/runs/30698781877/job/91366015548`
  completed checksum consensus, archive download, hash, and extraction, then
  failed with `ValueError: expected exactly one Blender executable`.

### RED

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_quad9_dot_uses_validated_tls_and_returns_a_records `
  tests.unit.test_ci.CiTrustTests.test_curl_command_can_pin_validated_hostname_to_address `
  tests.unit.test_ci.CiTrustTests.test_quad9_download_uses_resolved_address `
  tests.unit.test_ci.CiTrustTests.test_blender_executable_uses_exact_archive_root `
  -v
```

Result: four errors as intended because the DoT, resolved-address, and
exact-root helpers did not exist.

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Result: failed as intended because durable documentation still specified Quad9
DoH and did not specify exact archive-root discovery.

### DNS hardening RED

```powershell
& $Python52 -m unittest tests.unit.test_ci -v
```

Result: failed as intended because truncated and non-answer-only responses were
accepted, the exact-question parser contract and multi-address curl input were
absent, and `download_via_quad9()` discarded the second address. A subsequent
focused RED also proved an out-of-range compression pointer was accepted.

### GREEN

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_quad9_dot_uses_validated_tls_and_returns_a_records `
  tests.unit.test_ci.CiTrustTests.test_curl_command_can_pin_validated_hostname_to_address `
  tests.unit.test_ci.CiTrustTests.test_quad9_download_uses_resolved_address `
  tests.unit.test_ci.CiTrustTests.test_blender_executable_uses_exact_archive_root `
  -v
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Result: 4/4 focused, 13/13 CI helper, 12/12 workflow contract, and 77/77
complete unit tests passed.

```powershell
& $Python52 -c "from pathlib import Path; import scripts.ci as ci; p=Path('.test-output/quad9-live.txt'); print(ci.quad9_addresses('download.blender.org')); ci.download_via_quad9(ci.CHECKSUM_URL,p); print(len(p.read_bytes()),ci.sha256_file(p)); p.unlink()"
```

Result: Quad9 returned two current addresses; the pinned HTTPS download
returned 777 bytes with SHA-256
`f35709c2eb91fbb58ebbd354285039df62217e6dbda9c3a4713ec113d728057f`.

```powershell
& $Python52 -c "from pathlib import Path; import scripts.ci as ci; root=Path('.test-output'); paths=[root/'ci-system.txt',root/'ci-cloudflare.txt',root/'ci-quad9.txt']; ci.download(ci.CHECKSUM_URL,paths[0]); ci.download(ci.CHECKSUM_URL,paths[1],ci.CLOUDFLARE_DOH_URL); ci.download_via_quad9(ci.CHECKSUM_URL,paths[2]); payloads=[p.read_bytes() for p in paths]; assert len(set(payloads)) == 1; print('THREE_PATH_CHECKSUM_CONSENSUS_OK',len(payloads[0]),ci.sha256_file(paths[0])); [p.unlink() for p in paths]"
```

Result: system DNS, Cloudflare DoH, and Quad9 DoT returned byte-identical
777-byte checksum manifests:
`THREE_PATH_CHECKSUM_CONSENSUS_OK`.

### DNS hardening GREEN

```powershell
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Result: 17/17 focused and 81/81 complete unit tests passed.

```powershell
& $Python52 -c "from pathlib import Path; import scripts.ci as ci; root=Path('.test-output'); paths=[root/'ci-system.txt',root/'ci-cloudflare.txt',root/'ci-quad9.txt']; addresses=ci.quad9_addresses('download.blender.org'); print('QUAD9_ADDRESSES',addresses); command=ci.curl_command(ci.CHECKSUM_URL,paths[2],resolved_addresses=addresses); print('QUAD9_RESOLVE',command[command.index('--resolve')+1]); ci.download(ci.CHECKSUM_URL,paths[0]); ci.download(ci.CHECKSUM_URL,paths[1],ci.CLOUDFLARE_DOH_URL); ci.download_via_quad9(ci.CHECKSUM_URL,paths[2]); payloads=[p.read_bytes() for p in paths]; assert len(set(payloads)) == 1; print('THREE_PATH_CHECKSUM_CONSENSUS_OK',len(payloads[0]),ci.sha256_file(paths[0])); [p.unlink() for p in paths]"
```

Result: Quad9 returned `104.20.41.146` and `172.66.172.236`; both appeared in
one hostname-preserving curl entry, and all three checksum paths returned the
same 777-byte manifest with SHA-256
`f35709c2eb91fbb58ebbd354285039df62217e6dbda9c3a4713ec113d728057f`.

### DNS owner, compression, and address-budget RED/GREEN

```powershell
& $Python52 -m unittest `
  tests.unit.test_ci.CiTrustTests.test_dns_answer_owner_must_match_question `
  tests.unit.test_ci.CiTrustTests.test_dns_name_compression_requires_valid_boundaries `
  tests.unit.test_ci.CiTrustTests.test_dns_address_budget_is_enforced -v
```

RED result: all three tests failed because unrelated answer owners,
mid-label compression pointers, and 17 distinct addresses were accepted.

GREEN result: 3/3 focused and 20/20 CI-helper tests passed. The complete unit
suite passed 84/84.

```powershell
& $Python52 -c "import tempfile; from pathlib import Path; from scripts import ci; d=tempfile.TemporaryDirectory(); p=Path(d.name); a=ci.quad9_addresses('download.blender.org'); print('QUAD9_VALIDATED_ADDRESSES', a); print('QUAD9_RESOLVE', ci.curl_command(ci.CHECKSUM_URL,p/'q.txt',resolved_addresses=a)[-3]); paths=[p/'system.txt',p/'cloudflare.txt',p/'quad9.txt']; ci.download(ci.CHECKSUM_URL,paths[0]); ci.download(ci.CHECKSUM_URL,paths[1],ci.CLOUDFLARE_DOH_URL); ci.download_via_quad9(ci.CHECKSUM_URL,paths[2]); payloads=tuple(x.read_bytes() for x in paths); ci.require_checksum_consensus(payloads,ci.PLATFORMS['windows']['filename'],ci.PLATFORMS['windows']['sha256']); print('THREE_PATH_CHECKSUM_CONSENSUS_OK',len(payloads[0]),ci.sha256_file(paths[0])); d.cleanup()"
```

Result: Quad9 returned two validated direct A addresses. All three paths
returned the same 777-byte manifest with SHA-256
`f35709c2eb91fbb58ebbd354285039df62217e6dbda9c3a4713ec113d728057f`.

### Complete Blender and package gate

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
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
```

Result: 84/84 unit tests passed; Blender printed
`ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`; source and archive validation
succeeded; the rebuilt ignored ZIP is 66,755 bytes; diff check was clean.

## Known failures, warnings, and unverified assumptions

- The local machine proved Quad9 DoT and three-path byte consensus, but
  GitHub-hosted Windows and Linux have not yet proved outbound port 853.
- CNAME expansion is intentionally unsupported. A response without a direct
  matching A answer fails closed rather than expanding aliases.
- Exact-root lookup is covered synthetically and matches the official fixed
  archive names, but the corrected Linux path has not yet run on GitHub.
- The PR still points at `4ca0c3d` and therefore still displays the old failed
  checks until this local correction is approved and pushed.
- Expected local output includes Grease Pencil asset-path warnings, the
  deliberate stale-input warning, and LF-to-CRLF Git notices.
- `.packaged-releases/alpha_material_separator-1.0.0.zip` is ignored and must
  not be committed.

## Remaining tasks in priority order

1. Obtain user approval of the written README implementation plan and select
   inline or subagent-driven execution.
2. Rewrite the README and its contract tests, then verify and commit them.
3. Obtain separate approval to push `ci/automation`.
4. Observe both required hosted checks and address only demonstrated failures.
5. Separately approve repository visibility, required-check protection,
   release-environment protection, merge, and the first `1.0.0` publication.
6. Plan Blender native extension-repository hosting as a separate milestone.

## Recommended next action

Review and approve the written human-first README implementation plan, then
choose inline or subagent-driven execution.
