# Balanced Analyze Responsiveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove multi-second image-progress stalls and most avoidable modal scheduling delay without changing analysis results, public APIs, or Blender data.

**Architecture:** Keep `Image.pixels.foreach_get` as the single native transfer for eligible images, but retain its buffer only while `ImageSnapshotBuilder` processes at most 65,536 participating texels per modal step. Add an optional deadline to the existing polygon loop and have only the modal operator use a 12 ms target, 4,096-polygon cap, and 1 ms Blender timer. Reuse the current progress state, adding only one private visibility flag so preparation and validation can show truthful stage text without a false percentage.

**Tech Stack:** Python 3.11, Blender 5.2 Python API, `array`, `hashlib`, `time.perf_counter`, `unittest`/assert-based headless Blender tests, PowerShell validation scripts.

## Global Constraints

- Target Blender `5.2.0`; extension version remains `0.1.0` and public API remains `1.2`.
- Preserve the exact rasterizer, classifications, budgets, resolver behavior, cache keys, operator IDs, arguments, payload fields, and assignment behavior.
- Keep the existing 384 MiB native bulk-read eligibility cap.
- Process at most 65,536 participating texels per bulk post-transfer step.
- Modal face work uses a 12 ms target checked only between polygons and a hard 4,096-polygon callback cap.
- The Blender modal event timer is 1 ms; synchronous and headless analysis remains a tight count-bounded loop.
- Preparation and publication validation show stage text without a numeric percentage; 100 percent appears only after authoritative publication validation succeeds.
- Cancellation or failure releases retained buffers, publishes no partial result or cache entry, and preserves the previous complete report and review token.
- Do not add threads, processes, dependencies, preferences, public settings, runtime network access, or resumable per-polygon rasterization.
- The rare duration of one indivisible polygon remains an accepted balanced-target limit.
- Keep private files, helpers, raw timings, packaged ZIPs, and test output uncommitted.

---

### Task 1: Resumable native image post-processing

**Files:**
- Modify: `addon/adapters/image_data.py:15-205`
- Modify: `tests/blender/test_analysis_preview.py:279-388`

**Interfaces:**
- Consumes: existing `ImageSnapshotBuilder.step() -> int`, `finish() -> ImageSnapshot`, and `read_image_snapshot(...)`.
- Produces: `MAX_BULK_TEXELS_PER_STEP = 65_536`, `ImageSnapshotBuilder.close() -> None`, and unchanged snapshot digest/grid results.

- [ ] **Step 1: Extend the generated image doubles**

Change `_Image` so tests can create more than two texels while preserving all current callers:

```python
class _Image:
    def __init__(
        self,
        values,
        component_count,
        *,
        size=(2, 1),
        **pixel_options,
    ):
        self.size = size
        self.pixels = _Pixels(values, **pixel_options)
        self.component_count = component_count
```

- [ ] **Step 2: Write failing bulk-step and cleanup regressions**

Extend `_bulk_image_reader_tests()` with a generated 131,073-texel RGBA image and direct builder assertions:

```python
texel_count = 131_073
values = array("f")
for index in range(texel_count):
    values.extend((0.25, 0.5, 0.75, 0.0 if index % 2 else 1.0))
image = _Image(
    values,
    4,
    size=(texel_count, 1),
    reject_slices=True,
)
builder = image_data.ImageSnapshotBuilder(
    image,
    channel="ALPHA",
    threshold=0.999,
)
step_sizes = []
while not builder.complete:
    before = builder.destination
    builder.step()
    step_sizes.append(builder.destination - before)
assert step_sizes == [65_536, 65_536, 1], step_sizes
assert image.pixels.bulk_reads == 1
assert image.pixels.slice_reads == 0
assert builder._bulk_pixels is None
snapshot = builder.finish()
assert len(snapshot.grid.affected) == texel_count
```

Add a boundary error and explicit cancellation cleanup:

```python
boundary_values = array("f", [1.0]) * 65_537
boundary_values[65_536] = float("nan")
boundary = image_data.ImageSnapshotBuilder(
    _Image(boundary_values, 1, size=(65_537, 1)),
    channel="RED",
    threshold=0.999,
)
boundary.step()
try:
    boundary.step()
except ImageReadError:
    pass
else:
    raise AssertionError("chunk-boundary NaN was accepted")
assert boundary._bulk_pixels is None

cancelled = image_data.ImageSnapshotBuilder(
    _Image(array("f", [1.0]) * 65_537, 1, size=(65_537, 1)),
    channel="RED",
    threshold=0.999,
)
cancelled.step()
assert cancelled._bulk_pixels is not None
cancelled.close()
assert cancelled._bulk_pixels is None
```

Keep the existing all-component/all-channel bulk-versus-fallback digest and affected-grid parity loop.

- [ ] **Step 3: Run the headless test and verify the intended failure**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL because the first bulk `step()` currently processes all 131,073 texels and there is no retained buffer or `close()` method.

- [ ] **Step 4: Implement the smallest resumable bulk reader**

In `addon/adapters/image_data.py`, add:

```python
MAX_BULK_TEXELS_PER_STEP = 65_536
```

Initialize one retained buffer:

```python
self._bulk_pixels: array | None = None
```

Replace only the `use_bulk_read` branch of `step()` with this behavior:

```python
if self.use_bulk_read:
    if self._bulk_pixels is None:
        try:
            self._bulk_pixels = array("f", [0.0]) * len(self.image.pixels)
            self.image.pixels.foreach_get(self._bulk_pixels)
        except (AttributeError, MemoryError, RuntimeError, TypeError, ValueError):
            self._bulk_pixels = None
            self.use_bulk_read = False
            return self.step()

    start_texel = self.destination
    stop_texel = min(
        self.width * self.height,
        start_texel + MAX_BULK_TEXELS_PER_STEP,
    )
    first_value = start_texel * self.component_count
    stop_value = stop_texel * self.component_count
    values = _selected_values(
        self._bulk_pixels[first_value:stop_value],
        self.component_count,
        self.channel,
    )
    try:
        self.digest.update(values.tobytes())
        for value in values:
            if not math.isfinite(value):
                raise ImageReadError(
                    "image contains non-finite participating values"
                )
            self.affected[self.destination] = value < self.threshold
            self.destination += 1
    except Exception:
        self.close()
        raise
    previous_row = self.current_row
    self.current_row = min(
        self.height,
        self.destination // self.width,
    )
    if self.destination == self.width * self.height:
        self.current_row = self.height
        self.close()
    return self.current_row - previous_row
```

Add the idempotent cleanup method:

```python
def close(self) -> None:
    self._bulk_pixels = None
```

Do not alter `_selected_values`, the row-slice fallback, the digest prefix, or `ImageSnapshot`.

- [ ] **Step 5: Run the headless suite and verify green**

Run the Step 3 command.

Expected: `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [ ] **Step 6: Commit the image boundary**

```powershell
git add -- addon/adapters/image_data.py tests/blender/test_analysis_preview.py
git diff --cached --check
git commit -m "perf: chunk native image post-processing"
```

---

### Task 2: Deadline-aware polygon stepping

**Files:**
- Modify: `addon/adapters/analysis.py:829-1177`
- Modify: `tests/blender/test_analysis_preview.py:390-680`

**Interfaces:**
- Consumes: `AnalysisEngine.step(polygon_budget=128)`.
- Produces: backward-compatible `AnalysisEngine.step(polygon_budget=128, *, time_budget_seconds=None, clock=None) -> bool`, `AnalysisEngine.stage -> str`, and `AnalysisEngine.close() -> None`.

- [ ] **Step 1: Add a generated multi-polygon fixture**

Add a local helper beside `_quad` that creates independent triangles without private data:

```python
def _polygon_strip(name, count):
    vertices = []
    faces = []
    for index in range(count):
        offset = len(vertices)
        x = float(index)
        vertices.extend(((x, 0.0, 0.0), (x + 0.5, 0.0, 0.0), (x, 0.5, 0.0)))
        faces.append((offset, offset + 1, offset + 2))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, (), faces)
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    return object_
```

- [ ] **Step 2: Write failing deadline, cap, synchronous, and stage regressions**

Add `_analysis_cadence_tests()` and call it from `run()`:

```python
def _analysis_cadence_tests():
    timed_object = _polygon_strip("AMS_TIMED_ENGINE", 5)
    timed = AnalysisEngine((timed_object,), AnalysisConfig())
    analyzed = []
    timed._analyze_polygon = lambda prepared, polygon: analyzed.append(polygon.index)
    ticks = iter((0.0, 0.004, 0.008, 0.012))
    assert not timed.step(
        4_096,
        time_budget_seconds=0.010,
        clock=lambda: next(ticks),
    )
    assert analyzed == [0, 1, 2], analyzed

    capped_object = _polygon_strip("AMS_CAPPED_ENGINE", 4_100)
    capped = AnalysisEngine((capped_object,), AnalysisConfig())
    capped_count = 0

    def count_polygon(_prepared, _polygon):
        nonlocal capped_count
        capped_count += 1

    capped._analyze_polygon = count_polygon
    assert not capped.step(4_096)
    assert capped_count == 4_096

    synchronous = AnalysisEngine((timed_object,), AnalysisConfig())
    synchronous._analyze_polygon = lambda _prepared, _polygon: None
    assert synchronous.step(5, clock=lambda: (_ for _ in ()).throw(
        AssertionError("clock used without a time budget")
    ))
```

In the existing deferred-image test, assert:

```python
assert deferred.stage == "Reading Textures"
while deferred.stage == "Reading Textures":
    assert deferred.step(1) is False
assert deferred.stage == "Analyzing Faces"
```

Then cancel it and retain the existing incomplete-report assertion.

- [ ] **Step 3: Run the headless suite and verify the intended failure**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL because `AnalysisEngine.step()` does not accept a time budget or clock and `stage` is absent.

- [ ] **Step 4: Implement the optional deadline in the existing loop**

Add:

```python
@property
def stage(self) -> str:
    if (
        self._deferred_images
        and self._image_builder_index < len(self._image_builders)
    ):
        return "Reading Textures"
    return "Analyzing Faces"

def close(self) -> None:
    for builder in self._image_builders:
        builder.close()

def cancel(self) -> None:
    self.cancelled = True
    self.close()
```

Change the step signature and only the polygon loop:

```python
def step(
    self,
    polygon_budget: int = 128,
    *,
    time_budget_seconds: float | None = None,
    clock=None,
) -> bool:
    # Keep the existing cancellation and deferred-image block unchanged.
    if time_budget_seconds is not None:
        clock = clock or time.perf_counter
        deadline = clock() + time_budget_seconds
    else:
        deadline = None

    processed = 0
    while self._prepared_index < len(self.prepared) and processed < polygon_budget:
        prepared = self.prepared[self._prepared_index]
        polygons = prepared.object.data.polygons
        while self._polygon_index < len(polygons) and processed < polygon_budget:
            self._analyze_polygon(prepared, polygons[self._polygon_index])
            self._polygon_index += 1
            self.completed += 1
            processed += 1
            if deadline is not None and clock() >= deadline:
                return False
        if self._polygon_index >= len(polygons):
            self._polygon_index = 0
            self._prepared_index += 1
    return self._prepared_index >= len(self.prepared)
```

Do not put a clock check inside rasterization or classification. Do not pass a time budget from synchronous `execute()`.

- [ ] **Step 5: Run the headless suite and verify green**

Run the Step 3 command.

Expected: `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [ ] **Step 6: Commit the engine boundary**

```powershell
git add -- addon/adapters/analysis.py tests/blender/test_analysis_preview.py
git diff --cached --check
git commit -m "perf: time-slice modal face analysis"
```

---

### Task 3: Truthful modal progress and cleanup

**Files:**
- Modify: `addon/operators/analyze.py:13-269`
- Modify: `addon/runtime.py:96-165`
- Modify: `addon/properties.py:91-109`
- Modify: `addon/panel.py:291-309`
- Modify: `tests/blender/test_analysis_preview.py:609-680`
- Modify: `tests/blender/test_ux_overrides.py:417-438`

**Interfaces:**
- Consumes: `AnalysisEngine.stage`, deadline-aware `step()`, and existing private UI state.
- Produces: `analysis_progress_visible: BoolProperty`, optional `show_progress` on `runtime.update_analysis`, and modal constants `0.001`, `0.012`, and `4_096`.

- [ ] **Step 1: Write failing progress-state tests**

Extend the existing progress block in `test_ux_overrides.py`:

```python
assert ui.analysis_stage == "Preparing Inputs"
assert not ui.analysis_progress_visible
runtime.update_analysis(
    bpy.context.window_manager,
    5,
    10,
    "Reading Textures",
)
assert ui.analysis_progress_visible
assert ui.analysis_progress == 0.5
runtime.update_analysis(
    bpy.context.window_manager,
    10,
    10,
    "Validating Inputs",
    show_progress=False,
)
assert ui.analysis_stage == "Validating Inputs"
assert not ui.analysis_progress_visible
assert ui.analysis_progress == 0.5
runtime.update_analysis(
    bpy.context.window_manager,
    10,
    10,
    "Analysis Complete",
)
assert ui.analysis_progress_visible
assert ui.analysis_progress == 1.0
```

Keep the existing decreasing-update assertion to prove measurable progress remains monotonic.

- [ ] **Step 2: Write failing operator-stage and prior-report tests**

In `test_analysis_preview.py`, temporarily wrap `runtime.update_analysis` while running a normal analysis:

```python
stages = []
original_update_analysis = runtime.update_analysis

def record_progress(window_manager, completed, total, stage, **kwargs):
    stages.append((stage, kwargs.get("show_progress", True)))
    return original_update_analysis(
        window_manager,
        completed,
        total,
        stage,
        **kwargs,
    )

runtime.update_analysis = record_progress
try:
    result = bpy.ops.alpha_material_separator.analyze()
finally:
    runtime.update_analysis = original_update_analysis
assert result == {"FINISHED"}
assert ("Validating Inputs", False) in stages
assert stages[-1] == ("Analysis Complete", True)
```

Assert the operator constants are exact:

```python
from addon.operators import analyze as analyze_operator

assert analyze_operator.MODAL_TIMER_SECONDS == 0.001
assert analyze_operator.MODAL_FACE_TIME_BUDGET_SECONDS == 0.012
assert analyze_operator.MODAL_POLYGON_BUDGET == 4_096
```

Retain the current cancellation test proving the previous report and review token survive. Extend the deferred-engine cancellation assertion with:

```python
deferred.cancel()
assert all(builder._bulk_pixels is None for builder in deferred._image_builders)
```

- [ ] **Step 3: Run the headless suite and verify the intended failure**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL because the progress-visibility property, approved stage sequence, modal constants, and cleanup calls are not implemented.

- [ ] **Step 4: Add the private progress visibility state**

In `properties.py` add:

```python
analysis_progress_visible: BoolProperty(default=False, options={"SKIP_SAVE"})
```

In `runtime.py`, use exact title casing and keep an indeterminate stage from changing the last measured fraction:

```python
def begin_analysis(window_manager) -> bool:
    # Existing guard and fields remain.
    ui.analysis_progress = 0.0
    ui.analysis_progress_visible = False
    ui.analysis_stage = "Preparing Inputs"
```

```python
def update_analysis(
    window_manager,
    completed: int,
    total: int,
    stage: str,
    *,
    show_progress: bool = True,
) -> None:
    ui = _ui(window_manager)
    if ui is None:
        return
    if show_progress:
        ui.analysis_progress = min(
            1.0,
            max(ui.analysis_progress, completed / max(1, total)),
        )
    ui.analysis_progress_visible = show_progress
    ui.analysis_stage = stage
    tag_redraw()
```

Reset `analysis_progress_visible` to `False` in both `finish_analysis()` and `clear()`.

In `panel.py`, render one adaptive label:

```python
stage = ui.analysis_stage or "Analyzing"
if ui.analysis_progress_visible:
    stage = f"{stage} - {round(ui.analysis_progress * 100)}%"
analysis.label(text=stage)
```

- [ ] **Step 5: Wire the approved modal cadence and stages**

At module level in `operators/analyze.py` add:

```python
MODAL_TIMER_SECONDS = 0.001
MODAL_FACE_TIME_BUDGET_SECONDS = 0.012
MODAL_POLYGON_BUDGET = 4_096
```

Add one operator-local helper so the panel and Blender status bar receive the
same text:

```python
def _update_progress(
    self,
    context,
    stage: str,
    *,
    show_progress: bool = True,
) -> None:
    completed = self._engine.completed
    total = self._engine.total
    runtime.update_analysis(
        context.window_manager,
        completed,
        total,
        stage,
        show_progress=show_progress,
    )
    text = stage
    if show_progress:
        text = f"{stage} - {round(completed / max(1, total) * 100)}%"
    context.workspace.status_text_set(text=text)
```

Immediately after `runtime.begin_analysis()` succeeds and before constructing
`AnalysisEngine`, set:

```python
context.workspace.status_text_set(text="Preparing Inputs")
```

Clear that text in either constructor exception path. After engine construction,
call:

```python
self._update_progress(context, self._engine.stage)
```

Keep synchronous image preparation and execution count-bounded; do not pass it
a time budget.

In `invoke()` use:

```python
self._timer = context.window_manager.event_timer_add(
    MODAL_TIMER_SECONDS,
    window=context.window,
)
```

In `modal()` use:

```python
complete = self._engine.step(
    MODAL_POLYGON_BUDGET,
    time_budget_seconds=MODAL_FACE_TIME_BUDGET_SECONDS,
)
```

After each step, call:

```python
self._update_progress(context, self._engine.stage)
```

At the start of `_publish()`, before `validate_report_for_publication`, call:

```python
self._update_progress(
    context,
    "Validating Inputs",
    show_progress=False,
)
```

Publish `"Analysis Complete"` with normal visible progress only after validation succeeds.

Set it when the stage changes and clear it with:

```python
context.workspace.status_text_set(text=None)
```

from both synchronous `finally` and `_finish_modal()`. In both cleanup paths call `self._engine.close()` before dropping the engine reference. Preserve the existing previous-report behavior by continuing to call `runtime.set_report()` only after validation.

- [ ] **Step 6: Run focused and full headless verification**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: both suites pass; the Blender run ends with `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [ ] **Step 7: Commit the operator/UI boundary**

```powershell
git add -- addon/operators/analyze.py addon/runtime.py addon/properties.py `
  addon/panel.py tests/blender/test_analysis_preview.py `
  tests/blender/test_ux_overrides.py
git diff --cached --check
git commit -m "fix: smooth analyze progress updates"
```

---

### Task 4: Performance, private workflow, packaging, and documentation gate

**Files:**
- Modify: `docs/performance.md:139-170`
- Modify: `PLAN.md:211-235`
- Modify: `docs/HANDOFF.md`
- Local ignored only: `.local-references/default-example/_validate_analysis.py`
- Local ignored only: `.test-output/`
- Generated ignored only: `.packaged-releases/alpha_material_separator-0.1.0.zip`

**Interfaces:**
- Consumes: completed responsive image, engine, and operator behavior.
- Produces: reviewed timing evidence, updated milestone status, a validated local ZIP, and an exact continuation handoff.

- [ ] **Step 1: Run source and complete automated validation**

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
```

Expected: unit suite passes, Blender prints `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, and source validation succeeds.

- [ ] **Step 2: Run the private Analyze → Preview → Apply preservation smoke**

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

Expected: workflow, out-of-range addressing, preview/plan equivalence, mutation plan, idempotence, and preservation gates pass. The retired hand-made 1,176-face opaque difference remains diagnostic rather than a regression.

- [ ] **Step 3: Measure generated performance**

Run one discarded warm-up and five measured runs through the existing script:

```powershell
.\scripts\run_benchmarks.ps1 -Blender $Blender52
```

Record medians from the ignored output. Fail the gate for an unexplained same-machine regression above 25 percent in cold analysis, digest time, peak working set, or an established release tier.

- [ ] **Step 4: Measure modal cadence on the private stress example**

Recreate the ignored cadence profiler described in `docs/HANDOFF.md`, using the same anonymous stage/callback aggregation as the pre-change run. Discard one warm-up and measure five runs.

Accept only if:

```text
maximum generated 2K/4K bulk post-processing callback <= 250 ms
maximum private image callback < 1.0 s
private interactive Analyze median improves by at least 25%
classification and unsupported-reason aggregates remain unchanged
```

Do not commit the profiler, private paths embedded in output, or raw measurements.

- [ ] **Step 5: Build and validate the installable ZIP**

```powershell
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

Expected: archive build and validation succeed.

- [ ] **Step 6: Perform installed-ZIP interactive acceptance**

In a clean Blender 5.2 profile:

1. Install the rebuilt ZIP.
2. Select the generated nontrivial fixture and invoke Analyze.
3. Confirm stages appear in this order: Preparing Inputs, Reading Textures, Analyzing Faces, Validating Inputs, Analysis Complete.
4. Confirm image and face percentages move without multi-second image stalls.
5. Press Escape during Reading Textures and again during Analyzing Faces; confirm no partial report, cache result, or data mutation appears and the previous complete report/review remains.
6. Confirm a completed report still supports Preview → Object Mode → Apply without reanalysis.
7. Confirm the status bar text clears after completion, cancellation, and failure.

- [ ] **Step 7: Update durable records**

In `docs/performance.md`, append the new five-run medians, callback maxima, peak working set, and comparison with the pre-change 20 ms estimate. State that the 12 ms target is checked between polygons and is not a strict callback maximum.

In `PLAN.md`, mark the balanced-responsiveness implementation and its completed gates accurately. Do not mark installed-ZIP or performance items complete until those exact checks pass.

In `docs/HANDOFF.md`, replace the implementation objective with current verified results, exact commands, warnings, unverified assumptions, remaining release work, and one recommended next action.

- [ ] **Step 8: Check and commit the documentation boundary**

```powershell
git diff --check
git status --short
git add -- docs/performance.md PLAN.md docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record analyze responsiveness results"
git status --short
```

Expected: only ignored private/generated artifacts remain outside Git; do not push.
