# Repository handoff

Updated: 2026-08-01

## Current objective

The release-validation checklist is complete. The release-transition design is
approved and written. It promotes the extension to `1.0.0`, fast-forwards
`feat/alpha-material-separator-0.1` into local `main`, and creates
`ci/automation`. The written specification still requires user review
before its test-first implementation plan is prepared. Do not push without
separate approval.

## Completed work

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

- Version is still `0.1.0` and public API is still `1.2` in the current commit.
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
- The `1.0.0` version bump, merge to `main`, and GitHub Actions branch have not
  started.
- The existing `.packaged-releases/alpha_material_separator-0.1.0.zip`
  predates this test-only benchmark milestone; no package rebuild was required.

## Remaining tasks in priority order

1. Obtain user review of
   `docs/superpowers/specs/2026-08-01-release-1.0-transition-design.md`.
2. Prepare and approve the test-first release-transition implementation plan.
3. Execute the verified `1.0.0` bump and local fast-forward.
4. Create `ci/automation` without adding workflow files.
5. Design and approve the Actions workflow before implementation.
6. Separately reproduce and design a fix for cursor/sidebar progress
   desynchronization if the user prioritizes it.

## Recommended next action

Review and approve the written release-transition specification.
