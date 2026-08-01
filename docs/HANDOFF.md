# Repository handoff

Updated: 2026-08-01

## Current objective

The current branch is `ci/automation`. The verified Blender bootstrap,
read-only Windows/Linux validation matrix, guarded draft-first publication
path, documentation, and release-input injection fix are implemented in local
commits. A pre-push audit found additional hardening work, and the corrective
design is approved. No push or remote GitHub change has occurred; the next
milestone is an approval-gated test-first implementation plan.

## Completed work

- Prepared the `1.0.0` release identity:
  - Manifest and runtime capability payload both report `1.0.0`.
  - Public integration API remains `1.2`.
  - Current installation, support, testing, plan, and repository instructions
    use the new release identity.
  - Generated `alpha_material_separator-1.0.0.zip` validated successfully.
  - Archive size: 66,294 bytes.
  - Archive SHA-256:
    `1123BA95DC307ABBB3F12F9D5815AC19763B3CA12DEAD8B5116BA407C79EFE6C`.
- `eeb79b1 chore: release version 1.0.0`
  - Contains the synchronized manifest/runtime release identity, current
    documentation, and RED/GREEN release contracts.
  - Local `main` fast-forwarded from the initial commit to this verified tip.
  - The merged result passed 52 unit tests, the complete Blender suite, and
    source manifest validation.
- Created local `ci/automation` from verified `main`.
- Retained `feat/alpha-material-separator-0.1` at `eeb79b1`.
- `origin/main` remains
  `5c91b7eb1ef6ab7c68dc4a2bdb11555458146864`; no remote operation occurred.
- Approved CI/CD specification:
  `docs/superpowers/specs/2026-08-01-github-actions-ci-cd-design.md`.
- Test-first CI/CD implementation plan:
  `docs/superpowers/plans/2026-08-01-github-actions-ci-cd.md`.
- `ff293e3 ci: add verified Blender bootstrap`
  - Adds fixed Blender 5.2.0 trust anchors, streamed hashing, strict checksum
    parsing/consensus, HTTPS-only curl commands, verified extraction, executable
    version checking, and generated unit contracts.
- `aec88d5 ci: add Windows and Linux validation`
  - Adds the pinned, read-only `windows-2025`/`ubuntu-24.04` matrix and stable
    required-check names.
- `ade948c ci: add guarded immutable release publishing`
  - Adds strict release identity, checksum generation/reverification, protected
    manual release gating, narrowly scoped write permission, draft-first asset
    upload, stored-ZIP re-hash, and final publication.
- `fb66cd1 docs: document CI and immutable releases`
  - Documents the trust model, local/hosted validation boundary, protected
    release environment, immutable-release policy, and rollout sequence.
- `12af07e fix: prevent release input shell injection`
  - Moves the manual release version into job environment variables so
    untrusted workflow-dispatch input is never interpolated into PowerShell
    source.
  - Adds a workflow contract that permits the expression only in the two
    environment declarations.
- `695b4a7 test: benchmark final Apply preflight`
  - Adds a generated contract for a distinct final Apply-preflight measurement.
  - Reuses the 4,900-polygon, 1K-image structural fixture with one generated
    alpha texel so the plan is actionable.
  - Calls the real `_validated_plan()` boundary after one discarded warm-up and
    records five runs.
  - Proves the preflight preserves report identity, face material indices,
    material slots, and material datablocks.
- Recorded the 2026-08-01 Apply-preflight baseline:
  - Median: `0.03526610000153596` seconds.
  - Runs: `0.03526610000153596`, `0.035744400000112364`,
    `0.036189399999784655`, `0.034122900000511436`, and
    `0.03372010000020964` seconds.
  - Cold analysis: `0.7210454000014579` seconds.
  - Preflight/cold ratio: `0.04890968030787611` (4.89 percent).
  - One component hash, zero image-digest rows, zero rasterized polygons, zero
    coverage hits/misses, actionable, and mutation-free.
- Recorded the user's 2026-08-01 manual passes for:
  - Ordinary Unity material/submesh validation.
  - 150 percent UI scale.
  - Optional-preview confirmation, cancellation, Apply, Undo, and
    assignment-only-change behavior.
  - Material Details disclosure/deduplication at narrow and wide widths.
  - Count-only Apply warning layouts.
  - Generated two-material interactive partial apply.
- Generated tests additionally cover Apply-before-Preview enablement and the
  previewed clean-plan no-warning path.

## Important decisions and constraints

- Extension version is `1.0.0`; public API remains `1.2`.
- The benchmark adds test-only timing and no production instrumentation,
  behavior, dependencies, public fields, or new threshold.
- The timing covers authoritative validation, assignment-plan rebuilding,
  public-plan creation, and review-signature comparison. It excludes dialog
  response, assignment mutation, Undo, and UI rendering.
- The private before/after smoke was intentionally not run because this
  milestone changes only generated benchmark and documentation code.
- The ignored raw benchmark output remains at
  `.test-output/benchmarks/revalidation-current.json` and must not be committed.
- Keep commits local and do not push without explicit approval.
- Keep the curl-based Quad9 DoH check for the initial hosted run. If GitHub's
  runners reproduce the local curl failure, the approved contingency is a
  minimal RFC 8484 client that preserves Quad9 as an independent source and
  the byte-for-byte checksum consensus requirement.
- Use Blender's native extension-repository system for future updates. Hosting
  and `index.json` publication are a separate milestone; AMS will not contain a
  custom updater.
- The release job will use unauthenticated native Git for the exact public
  commit so `actions/checkout` never receives its write-capable token.

## Files changed and why

- `tests/blender/test_benchmark_contract.py`: generated five-run output,
  actionability, counter, and mutation-free contract.
- `tests/blender/run_benchmarks.py`: real Apply-preflight timing and additive
  ignored JSON fields.
- `tests/blender/run_all.py`: runs the benchmark contract in the headless gate.
- `docs/performance.md`: exact standalone Apply-preflight result.
- `docs/testing.md`: measurement method and completed manual/automated checks.
- `PLAN.md`: completed release-validation status.
- `docs/HANDOFF.md`: current evidence and next action.
- `scripts/ci.py`: standard-library trust-chain and release-identity helper.
- `.github/workflows/ci.yml`: pinned read-only Windows/Linux validation and
  guarded manual draft-first publication.
- `tests/unit/test_ci.py`: trust-anchor, checksum, download, and release helper
  contracts.
- `tests/unit/test_ci_workflow_contract.py`: workflow security, platform,
  validation, publication, and shell-injection contracts.
- `docs/testing.md`, `PLAN.md`, and `AGENTS.md`: CI trust model, rollout,
  required checks, and repository operating rules.
- `addon/blender_manifest.toml`, `addon/api_contract.py`: extension version
  `1.0.0` while API remains `1.2`.
- `tests/unit/test_api_contract.py`: manifest/runtime version agreement.
- `tests/unit/test_readme_contract.py`: current installable release identity.
- `README.md`, `docs/integration-api.md`, `docs/material-support.md`,
  `docs/testing.md`, `PLAN.md`, and `AGENTS.md`: current `1.0.0` release and
  post-transition branch instructions.

## Validation commands and results

### TDD RED

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
```

Result: failed as intended with
`KeyError: 'apply_preflight_seconds_runs'`.

### TDD GREEN

The same command passed and printed:

```text
ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK
ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK
```

### Focused measurement

```powershell
$Output = '.test-output\benchmarks\revalidation-current.json'
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_benchmarks.py -- `
  --output $Output --only revalidation
```

Result: exit `0`, `REVALIDATION complete`, and `BENCHMARK_OUTPUT`. Exact
measurements are listed under Completed work.

### Complete gate

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe' `
  -m unittest discover -s tests/unit -t . -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --background --disable-autoexec --python-exit-code 1 `
  --python tests/blender/run_all.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --factory-startup --command extension validate addon
git diff --check
```

Result: 51/51 unit tests passed; the headless suite printed both success
markers above; source manifest validation succeeded; `git diff --check`
reported no errors.

### Release 1.0 gate

The runtime/manifest RED contract failed as intended with capability version
`0.1.0` instead of `1.0.0`, then passed after changing the two release
authorities. The README RED contract failed on the old release sentence, then
passed after updating current documentation.

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-1.0.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Result: 52/52 unit tests passed; Blender printed
`ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`; source and archive validation
succeeded; `git diff --check` reported no errors.

The same 52-test, complete Blender, and source-validation gate passed again
after `git merge --ff-only feat/alpha-material-separator-0.1` on local `main`.

### CI/CD planning gate

```powershell
Select-String -Path `
  docs/superpowers/plans/2026-08-01-github-actions-ci-cd.md `
  -Pattern 'TBD|TODO|implement later|fill in|similar to'
git diff --check
```

Result: the plan's required placeholder scan returned no matches; its
specification coverage and interface names were reviewed; `git diff --check`
reported no errors. No workflow, helper, test, or remote state was created.

### CI/CD Task 1 TDD and trust-chain attempt

```powershell
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Python52 scripts/ci.py prepare-blender `
  --platform windows `
  --output-dir .test-output/ci/blender-windows
```

Result: the focused RED failed because `scripts.ci` did not exist. After the
minimal helper was added, 5/5 focused tests and 57/57 total unit tests passed.
The real trust-chain command failed closed on the Quad9-routed checksum request
with curl exit `6`, HTTP `000`, and `Could not resolve host:
download.blender.org`. System DNS and Cloudflare produced byte-identical
777-byte checksum files with SHA-256
`F35709C2EB91FBB58EBBD354285039DF62217E6DBDA9C3A4713EC113D728057F`.

The local curl reports version `8.21.0`, advertises `--doh-url`, and lacks an
HTTP/2 feature. Exact diagnostic retries using Quad9's documented hostname,
trailing-question-mark form, TLS-validated published bootstrap address, and
IP-form DoH endpoint all failed with the same resolver error. No Blender archive
was downloaded or extracted.

### CI/CD Tasks 2 and 3

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest `
  tests.unit.test_ci tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate `
  .packaged-releases/alpha_material_separator-1.0.0.zip
```

Result: the workflow contract first failed because the workflow did not exist,
then passed. Publication contracts first failed for missing release helpers and
jobs, then 14/14 focused contracts and 66/66 total unit tests passed. The
complete headless Blender suite printed both success markers; source and
freshly built archive validation succeeded. The local release CLI accepted
`1.0.0`, produced `v1.0.0` and `SHA256SUMS.txt`, reverified the ZIP, and rejected
manifest-mismatched `1.0.1` with exit `1`.

### Final CI security review and completion gate

The independent review found one important issue: the manual release version
was interpolated directly into PowerShell source. The new contract failed on
four unsafe command lines before the fix. After moving the value into the job
environment, the focused workflow suite passed 9/9 and the full unit suite
passed 68/68.

```powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate `
  .packaged-releases/alpha_material_separator-1.0.0.zip
git diff --check
```

Result: 68/68 unit tests passed; the headless suite printed
`ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`; source validation, archive build,
and exact archive validation succeeded. The fresh ZIP was 66,755 bytes and
contained no `scripts/`, `tests/`, or `.github/` entries. `git diff --check`
reported no errors. The minimalism review found no safe removable complexity
within the approved trust and publication boundaries.

## Known warnings and unverified assumptions

- Expected Blender output includes bundled Grease Pencil brush-path warnings,
  the deliberate stale-input warning, and the Blender 6.0
  `Material.use_nodes` deprecation warning from generated fixtures.
- Git may report expected LF-to-CRLF working-copy notices.
- The Unity, UI-scale, and interactive workflow results are user-reported
  manual acceptance evidence, not automation performed in this turn.
- Installed-ZIP Escape cancellation passed. The cursor and sidebar progress
  percentages can briefly disagree; root cause and desired synchronization
  behavior have not been investigated.
- `.packaged-releases/alpha_material_separator-1.0.0.zip` is validated and
  remains ignored.
- GitHub Actions code is implemented locally but has not been parsed or
  executed by GitHub. Runner image tooling, PowerShell behavior, Linux bundled
  Python discovery, stable check display names, and draft-release commands
  remain hosted assumptions.
- The approved curl `--doh-url` method is not viable on the tested local
  Windows curl/network combination. Do not count the local real trust chain as
  passed.
- Deferred contingency if hosted runners reproduce the failure: replace curl's
  built-in DoH resolution with a minimal standard-library RFC 8484
  query/response path, retain TLS hostname validation and dynamically resolved
  Blender addresses, and continue requiring byte-identical checksum content.
  Do not drop Quad9 or weaken consensus.

## Remaining tasks in priority order

1. Prepare and obtain approval for the test-first implementation plan in
   `docs/superpowers/specs/2026-08-01-github-actions-hardening-design.md`.
2. Implement and locally verify the approved pre-push hardening.
3. Obtain explicit approval before pushing `ci/automation` and creating a pull
   request.
4. Run and inspect the required Windows/Linux GitHub checks.
5. Use the documented RFC 8484 contingency only if hosted runners reproduce
   the curl Quad9 failure.
6. After both checks pass, separately approve repository visibility, branch
   protection, release-environment protection, merge, and first publication.
7. Design Blender native extension-repository hosting as a separate milestone.
8. Separately reproduce and design a fix for cursor/sidebar progress
   desynchronization if the user prioritizes it.

## Recommended next action

Review and approve the written pre-push hardening specification, then prepare
its test-first implementation plan.
