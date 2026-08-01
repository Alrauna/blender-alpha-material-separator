# Repository handoff

Updated: 2026-08-01

## Current objective

The balanced Analyze responsiveness implementation is complete, committed,
packaged, and verified. The user confirmed the installed UI works. The current
objective is to decide whether to reduce Analyze's pre-existing retained
coverage-cache memory; the responsiveness implementation did not measurably
regress post-analysis memory.

## Completed work

- `b76696c perf: chunk native image post-processing`
  - Retains one eligible `Image.pixels.foreach_get` buffer.
  - Processes at most 65,536 participating texels per builder step.
  - Releases the buffer after completion, cancellation, fallback, or error.
- `95d8250 perf: time-slice modal face analysis`
  - Adds an optional 12 ms between-polygon deadline.
  - Keeps a hard 4,096-polygon modal callback cap.
  - Leaves synchronous analysis count-bounded and unslept.
- `a1c04cb fix: smooth analyze progress updates`
  - Changes the interactive timer from 20 ms to 1 ms.
  - Reports Preparing Inputs, Reading Textures, Analyzing Faces, Validating
    Inputs, and Analysis Complete.
  - Hides percentages during non-resumable preparation and validation.
  - Clears status text and retained buffers on every operator exit.
- `3df8301 test: reject mid-analysis input mutations`
  - Mutates participating UV data between work chunks and proves publication
    rejects the hybrid run as `INPUTS_CHANGED`.
- Rebuilt and validated
  `.packaged-releases/alpha_material_separator-0.1.0.zip`.
- `5ce5dd7 ui: rename sidebar tab to AMS`
  - Changes the 3D View sidebar category from `Alpha Material` to `AMS`.
  - Keeps the panel heading and full Alpha Material Separator product name.
  - Updates current README location instructions and registered-panel tests.
- Compared current `075a4cb` with pre-responsiveness `5e33c0e` using the same
  ignored memory probe and private multi-object input:
  - Peak working set was 3.274 GiB for both revisions.
  - Post-analysis working set differed by only 0.03 percent.
  - The current retained native pixel buffer was zero bytes after completion.
  - The existing coverage cache held 93,194 entries and approximately 856 MiB
    of Python objects in both revisions.

## Important decisions and constraints

- Version remains `0.1.0`; public API remains `1.2`.
- Classification, rasterization, budgets, resolver behavior, cache keys,
  assignment, and public payloads are unchanged.
- Native transfer remains bounded by the existing 384 MiB eligibility cap.
- The 12 ms target is checked only between polygons. One indivisible polygon
  can exceed it; resumable rasterization remains deferred.
- Multiprocessing remains deferred. The main-thread design is safer and the
  complete-workflow evidence does not justify serialization, memory,
  cancellation, or Blender lifecycle complexity.
- Reset Results, successful Apply, file load, and extension unregister already
  drop extension-owned report and coverage-cache references. Python and
  Blender may keep the freed arenas committed, so Task Manager need not fall
  immediately even after garbage collection.
- Do not add a Windows-only working-set trim. It makes the displayed resident
  set fall without reducing committed private memory, and the operating system
  can reclaim those pages under pressure.
- Private files, helper scripts, raw results, and packaged ZIPs remain ignored.
- Do not push without explicit approval.

## Files changed and why

- `addon/adapters/image_data.py`: resumable native-buffer post-processing and
  cleanup.
- `addon/adapters/analysis.py`: stage reporting, optional polygon deadline, and
  image-builder cleanup.
- `addon/operators/analyze.py`: 1 ms timer, 12 ms modal budget, truthful stages,
  status-bar text, and cleanup.
- `addon/runtime.py`, `addon/properties.py`, `addon/panel.py`: private
  indeterminate-progress state and rendering.
- `tests/blender/test_analysis_preview.py`: generated RED/GREEN image, cadence,
  cleanup, stage, and mid-run mutation tests.
- `tests/blender/test_ux_overrides.py`: progress visibility, monotonicity,
  completion, and prior-report preservation.
- `docs/performance.md`, `PLAN.md`, and the approved Superpowers plan: measured
  results and accurate milestone status.
- `addon/panel.py`, `README.md`, `tests/blender/run_all.py`, and
  `tests/unit/test_readme_contract.py`: native `AMS` sidebar name, matching
  instructions, and boundary contracts.

## Validation commands and results

### TDD RED

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

- Image RED: failed with step sizes `[131073]`; expected
  `[65536, 65536, 1]`.
- Cadence RED: failed because `AnalysisEngine.step()` rejected
  `time_budget_seconds`.
- Progress RED: emitted only `Analyzing faces` and `Analysis complete`; the
  required validation stage was absent.

### Automated and source gate

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

Result: 51/51 unit tests passed, Blender printed
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, and source validation succeeded.

The AMS sidebar rename additionally demonstrated focused RED failures for the
old README instruction and registered `Alpha Material` panel category, then
passed both focused GREEN checks and the same complete gate. The private
before/after smoke was intentionally not rerun because this presentation-only
change does not alter resolution, rasterization, classification, cache,
preview-plan, assignment-plan, or mutation data.

### Private workflow and preservation

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

Result: passed for 48 mesh objects, 65,773 planned/applied faces, and 59,202
positive-area faces outside the base tile. The known 1,176 hand-made
reference-only opaque faces remain diagnostic.

### Generated performance

```powershell
.\scripts\run_benchmarks.ps1 -Blender $Blender52
```

Result: completed in 928.8 seconds using one discarded warm-up and five
measured runs.

| Tier | Median |
| --- | ---: |
| Small | 0.691 s |
| Typical | 8.074 s |
| High | 71.556 s |
| Large/tiled UV | 1.917 s |

Peak working set was about 2.92 GiB. No established matching metric regressed
by more than 25 percent.

### Cadence characterization

The ignored profiler was run and then deleted. Five-run medians/maxima:

- Instrumented interactive estimate: 51.544 s, about 52.8 percent below the
  previous 109.3 s estimate.
- Callback work: 43.093 s.
- Private image callback maximum: 36.8 ms.
- Generated 2K/4K image callback maxima: 10.9/31.6 ms.
- Polygon callback maximum: 196.8 ms.

### Post-analysis memory comparison

An ignored diagnostic loaded the same private multi-object input, ran deferred
Analyze, released the engine, cleared coverage, cleared all extension state,
forced garbage collection, and finally asked Windows to trim reclaimable
working-set pages. It was run once against current `075a4cb` and once against
an ignored export of `5e33c0e`; the probe and export were then deleted.

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python .test-output\_memory_retention_probe.py
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python .test-output\_memory_retention_probe.py -- `
  .test-output\pre_responsiveness
```

Result: no responsiveness regression was detected. Current/pre-change
post-engine working sets were 2.946/2.946 GiB. Clearing all extension state
reduced current working set to 1.851 GiB; a diagnostic working-set trim reduced
resident pages to 42 MiB while committed private bytes remained about 2.08
GiB. This distinguishes released-but-reserved allocator memory from a live
reference leak.

### Package and installed lifecycle

```powershell
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

Result: build and validation passed.

- Size: 66,297 bytes.
- SHA-256:
  `68E09A198DEC8C1B97752C085F080F2770609F0480F60C0EB37CB1A87044A867`.
- Isolated installation and `tests/blender/verify_installed_zip.py` passed.

## Known failures, warnings, and unverified assumptions

- Foreground automation previously could not bind to the isolated Blender
  window, but the user subsequently confirmed the installed UI works.
- The 51.544 s result is an instrumented modal estimate, not a foreground UI
  wall-clock measurement.
- The memory comparison used one run per revision because it compared retained
  structure sizes and lifecycle checkpoints, not timing. It does not yet
  establish a release regression limit for post-analysis retained memory.
- Expected Blender warnings remain the bundled Grease Pencil brush-path
  warning, the deliberate stale-input warning, and a Blender 6.0
  `Material.use_nodes` deprecation warning in generated fixtures.
- Git may report expected LF-to-CRLF working-copy notices.
- Ordinary Unity material/submesh validation, Apply-preflight timing, the
  generated two-material interactive partial-apply case, and the 150 percent
  UI-scale pass remain release tasks.

## Remaining tasks in priority order

1. Obtain design approval for either retaining cross-run coverage reuse as-is
   or reducing its memory through a compact representation or changed cache
   lifetime.
2. If memory reduction is approved, write a TDD plan with generated retention
   checkpoints, cache-reuse timing, cancellation cleanup, and the existing
   25-percent performance gate before production edits.
3. Record actual foreground Analyze wall-clock timing for the private or
   generated stress workflow.
4. Complete the remaining release-validation items listed above.

## Recommended next action

Review the memory findings and choose whether the cross-run coverage cache
should prioritize repeat-analysis speed or lower retained live memory.
