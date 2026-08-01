# Repository handoff

Updated: 2026-08-01

## Current objective

The release-validation checklist is complete. The extension version is now
`1.0.0` in source and current documentation, with public API `1.2` unchanged.
The full source/package gate passed; the local release commit remains next.
Afterward, fast-forward `feat/alpha-material-separator-0.1` into local `main`
and create `ci/automation`. Do not push without separate approval.

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
- The local merge to `main` and `ci/automation` branch creation have not
  started.
- `.packaged-releases/alpha_material_separator-1.0.0.zip` is validated and
  remains ignored.

## Remaining tasks in priority order

1. Commit the verified `1.0.0` release identity.
2. Fast-forward the verified feature branch into local `main`.
3. Create `ci/automation` without adding workflow files.
4. Design and approve the Actions workflow before implementation.
5. Separately reproduce and design a fix for cursor/sidebar progress
   desynchronization if the user prioritizes it.

## Recommended next action

Commit the verified `1.0.0` identity.
