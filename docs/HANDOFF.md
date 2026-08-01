# Repository handoff

Updated: 2026-08-01

## Current objective

The balanced Analyze responsiveness implementation is complete, committed,
packaged, and verified through automated, private, and instrumented performance
gates. The remaining immediate objective is a clean-profile foreground check of
progress stages and Escape cancellation; Windows automation could not bind to
the isolated Blender window.

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

### Package and installed lifecycle

```powershell
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

Result: build and validation passed.

- Size: 66,296 bytes.
- SHA-256:
  `39E95AEEAC9A5BE9AA4EC5DA48BB3B9825F5A427B0A8E8F5C9C6541BE0D220D6`.
- Isolated installation and `tests/blender/verify_installed_zip.py` passed.

## Known failures, warnings, and unverified assumptions

- Foreground installed-ZIP visual interaction is not verified. Computer Use
  twice returned:
  `window id 68920 no longer belongs to blender.5.2; current owner is blender.5.2`.
  The isolated process was closed without modifying user data.
- The 51.544 s result is an instrumented modal estimate, not a foreground UI
  wall-clock measurement.
- Expected Blender warnings remain the bundled Grease Pencil brush-path
  warning, the deliberate stale-input warning, and a Blender 6.0
  `Material.use_nodes` deprecation warning in generated fixtures.
- Git may report expected LF-to-CRLF working-copy notices.
- Ordinary Unity material/submesh validation, Apply-preflight timing, the
  generated two-material interactive partial-apply case, and the 150 percent
  UI-scale pass remain release tasks.

## Remaining tasks in priority order

1. Run the rebuilt ZIP in the isolated profile and verify the five progress
   stages, continuous texture/face progress, Escape cancellation during texture
   and face work, prior-report preservation, and status-text cleanup.
2. Record actual foreground Analyze wall-clock timing for the private or
   generated stress workflow.
3. Complete the remaining release-validation items listed above.

## Recommended next action

Manually run the clean-profile installed ZIP and report whether progress stages
and Escape cancellation behave as specified.
