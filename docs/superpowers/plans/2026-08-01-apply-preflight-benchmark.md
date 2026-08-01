# Apply Preflight Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a distinct, mutation-free median timing row for the real final
Apply preflight.

**Architecture:** Extend the existing generated structural-revalidation tier
and reuse its analyzed 4,900-polygon/1K-image scene. Call the real
`_validated_plan()` boundary through minimal test-only operator/context shapes,
then store five measured durations and validation counters in the existing
ignored JSON schema.

**Tech Stack:** Blender 5.2 Python API, Python `statistics`, Blender headless
tests, existing PowerShell benchmark runner.

## Global Constraints

- Measure authoritative validation, assignment-plan rebuilding, public-plan
  creation, and exact review-signature comparison.
- Discard one warm-up and record five measured runs.
- Prove zero changes to polygon material indices, object material slots,
  material datablocks, and active report identity.
- Do not time confirmation-dialog drawing, user response, assignment mutation,
  or Undo.
- Do not add production instrumentation, dependencies, public API fields, or an
  arbitrary performance threshold.
- Keep version `0.1.0` and API `1.2` during this benchmark milestone.
- Do not run the private before/after smoke; no resolver, classification,
  preview-plan, assignment-plan, or mutation behavior changes.
- Do not push.

---

### Task 1: Add the generated preflight benchmark contract

**Files:**
- Create: `tests/blender/test_benchmark_contract.py`
- Modify: `tests/blender/run_all.py`

**Interfaces:**
- Consumes: `tests.blender.run_benchmarks._revalidation_benchmark() -> dict`.
- Produces: `run() -> None`, a generated headless contract requiring the
  Apply-preflight result fields and five-run measurement method.

- [x] **Step 1: Write the failing generated contract**

Create `tests/blender/test_benchmark_contract.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generated contracts for release benchmark output."""

from __future__ import annotations

import statistics

from tests.blender.run_benchmarks import _revalidation_benchmark


def run() -> None:
    result = _revalidation_benchmark()
    runs = result["apply_preflight_seconds_runs"]
    assert len(runs) == 5, runs
    assert all(value >= 0.0 for value in runs), runs
    assert result["apply_preflight_seconds_median_5"] == statistics.median(runs)
    assert result["apply_preflight_ratio_to_cold_analysis"] >= 0.0
    assert result["apply_preflight_actionable"] is True
    assert result["apply_preflight_mutation_free"] is True
    assert result["apply_preflight_last_validation_component_hash_calls"] >= 0
    assert result["apply_preflight_last_validation_image_digest_rows"] == 0
    assert result["apply_preflight_last_validation_rasterized_polygons"] == 0
    print("ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK")
```

Import and invoke it in `tests/blender/run_all.py`:

```python
from tests.blender.test_benchmark_contract import (
    run as run_benchmark_contract_tests,
)
```

```python
run_benchmark_contract_tests()
```

- [x] **Step 2: Run the headless suite and verify RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL with `KeyError: 'apply_preflight_seconds_runs'`.

---

### Task 2: Measure the real mutation-free preflight

**Files:**
- Modify: `tests/blender/run_benchmarks.py:234-331`
- Test: `tests/blender/test_benchmark_contract.py`

**Interfaces:**
- Consumes:
  - `addon.operators.assign_materials._validated_plan(operator, context)`.
  - `addon.adapters.assignment.build_assignment_plan(report, *, mixed_policy,
    suppressed_policy, unsupported_policy, conflict_policy)`.
  - `addon.presentation.review_signature(...) -> str`.
- Produces these additive keys under the existing `revalidation` JSON object:
  - `apply_preflight_seconds_median_5: float`
  - `apply_preflight_seconds_runs: list[float]`
  - `apply_preflight_ratio_to_cold_analysis: float`
  - `apply_preflight_actionable: bool`
  - `apply_preflight_mutation_free: bool`
  - `apply_preflight_last_validation_component_hash_calls: int`
  - `apply_preflight_last_validation_image_digest_rows: int`
  - `apply_preflight_last_validation_rasterized_polygons: int`
  - `apply_preflight_last_validation_coverage_hits: int`
  - `apply_preflight_last_validation_coverage_misses: int`

- [x] **Step 1: Add only the required test imports**

In `tests/blender/run_benchmarks.py`, add:

```python
from types import SimpleNamespace
```

```python
from addon.adapters.assignment import build_assignment_plan
from addon.operators.assign_materials import _validated_plan
from addon.presentation import review_signature
```

- [x] **Step 2: Create the expected exact review signature outside timing**

After `runtime.set_report(report)` in `_revalidation_benchmark()`, build the
current plan once:

```python
policies = {
    "mixed_policy": "TO_ALPHA",
    "suppressed_policy": "CANCEL_SOURCE_MATERIAL",
    "unsupported_policy": "TO_ALPHA",
    "conflict_policy": "CANCEL_SOURCE_MATERIAL",
}
expected_plan = build_assignment_plan(report, **policies)
expected_payload = expected_plan.public_payload()
expected_signature = review_signature(
    report.analysis_id,
    policies["mixed_policy"],
    policies["suppressed_policy"],
    policies["unsupported_policy"],
    policies["conflict_policy"],
    expected_payload,
)
```

- [x] **Step 3: Snapshot every prohibited mutation**

Before timing, capture:

```python
preflight_before = {
    "indices": tuple(
        polygon.material_index for polygon in object_.data.polygons
    ),
    "slots": tuple(slot.material for slot in object_.material_slots),
    "materials": tuple(
        sorted(material.as_pointer() for material in bpy.data.materials)
    ),
    "report": runtime.report(report.analysis_id),
}
```

- [x] **Step 4: Measure one warm-up and five real preflights**

Create the test-only operator/context shapes:

```python
operator = SimpleNamespace(
    api_major=1,
    expected_analysis_id=report.analysis_id,
    expected_review_signature=expected_signature,
    mixed_policy=policies["mixed_policy"],
    suppressed_policy=policies["suppressed_policy"],
    unsupported_policy=policies["unsupported_policy"],
    derived_conflict_policy=policies["conflict_policy"],
    _status=lambda *_args, **_kwargs: None,
)
context = SimpleNamespace(window_manager=bpy.context.window_manager)
```

Then measure:

```python
preflight_times = []
preflight_plan = None
for run in range(6):
    started = time.perf_counter()
    prepared = _validated_plan(operator, context)
    elapsed = time.perf_counter() - started
    if prepared is None:
        raise RuntimeError("Apply preflight did not produce a valid plan")
    prepared_report, preflight_plan, _payload = prepared
    if prepared_report is not report or not preflight_plan.actionable:
        raise RuntimeError("Apply preflight changed report identity or actionability")
    if run:
        preflight_times.append(elapsed)
```

- [x] **Step 5: Prove the measurement caused no mutation**

After timing, capture the same shape:

```python
preflight_after = {
    "indices": tuple(
        polygon.material_index for polygon in object_.data.polygons
    ),
    "slots": tuple(slot.material for slot in object_.material_slots),
    "materials": tuple(
        sorted(material.as_pointer() for material in bpy.data.materials)
    ),
    "report": runtime.report(report.analysis_id),
}
preflight_mutation_free = preflight_after == preflight_before
if not preflight_mutation_free:
    raise RuntimeError("Apply preflight mutated Blender or report state")
preflight_snapshot = runtime.snapshot()
```

- [x] **Step 6: Add the metrics to the existing result**

Add:

```python
"apply_preflight_seconds_median_5": statistics.median(preflight_times),
"apply_preflight_seconds_runs": preflight_times,
"apply_preflight_ratio_to_cold_analysis": (
    statistics.median(preflight_times) / max(cold_seconds, 1e-12)
),
"apply_preflight_actionable": bool(preflight_plan.actionable),
"apply_preflight_mutation_free": preflight_mutation_free,
"apply_preflight_last_validation_component_hash_calls": preflight_snapshot.get(
    "last_validation_component_hash_calls", 0
),
"apply_preflight_last_validation_image_digest_rows": preflight_snapshot.get(
    "last_validation_image_digest_rows", 0
),
"apply_preflight_last_validation_rasterized_polygons": preflight_snapshot.get(
    "last_validation_rasterized_polygons", 0
),
"apply_preflight_last_validation_coverage_hits": preflight_snapshot.get(
    "last_validation_coverage_hits", 0
),
"apply_preflight_last_validation_coverage_misses": preflight_snapshot.get(
    "last_validation_coverage_misses", 0
),
```

Keep benchmark schema version `2`; these fields are additive.

- [x] **Step 7: Run the headless suite and verify GREEN**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: PASS with both
`ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.

- [x] **Step 8: Review and commit the benchmark code**

```powershell
git diff -- `
  tests/blender/run_benchmarks.py `
  tests/blender/test_benchmark_contract.py `
  tests/blender/run_all.py
git add -- `
  tests/blender/run_benchmarks.py `
  tests/blender/test_benchmark_contract.py `
  tests/blender/run_all.py
git diff --cached --check
git commit -m "test: benchmark final Apply preflight"
```

---

### Task 3: Record the measured release row

**Files:**
- Modify: `docs/performance.md`
- Modify: `docs/testing.md`
- Modify: `PLAN.md`
- Modify: `docs/HANDOFF.md`
- Generated ignored: `.test-output/benchmarks/revalidation-current.json`

**Interfaces:**
- Consumes: the `revalidation` object written by
  `tests/blender/run_benchmarks.py --only revalidation`.
- Produces: one documented Apply-preflight median and closed release checklist
  item, without changing a performance threshold.

- [x] **Step 1: Run the focused benchmark**

Run:

```powershell
$Output = '.test-output\benchmarks\revalidation-current.json'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_benchmarks.py -- `
  --output $Output --only revalidation
```

Expected: exit `0`, `REVALIDATION complete`, and `BENCHMARK_OUTPUT`.

- [x] **Step 2: Inspect the generated measurement**

Run:

```powershell
$Result = Get-Content -Raw `
  '.test-output\benchmarks\revalidation-current.json' | ConvertFrom-Json
$Result.revalidation | Select-Object `
  apply_preflight_seconds_median_5, `
  apply_preflight_seconds_runs, `
  apply_preflight_ratio_to_cold_analysis, `
  apply_preflight_mutation_free, `
  apply_preflight_last_validation_component_hash_calls, `
  apply_preflight_last_validation_image_digest_rows, `
  apply_preflight_last_validation_rasterized_polygons
```

Expected: five non-negative runs, their median, `mutation_free=True`, zero
image-digest rows, and zero rasterized polygons.

- [x] **Step 3: Record the exact row**

In `docs/performance.md`, extend **Structural revalidation baseline** with:

```markdown
| Apply preflight median | `<measured seconds>` |
| Apply preflight / cold ratio | `<measured percent>` |
| Preflight component hashes | `<measured count>` |
| Preflight image-digest rows | `0` |
| Preflight rasterized polygons | `0` |
| Preflight mutation-free | `yes` |
```

Add one sentence stating that this measures validation and plan rebuilding
before mutation, not dialog response or assignment.

- [x] **Step 4: Close only the measured checklist item**

In `PLAN.md`, mark the distinct Apply-preflight timing row complete and record
the measured median.

In `docs/testing.md`, state that the generated benchmark records one discarded
warm-up and five Apply-preflight runs and proves no mutation.

In `docs/HANDOFF.md`, record the exact command, output path, result, code commit,
remaining release status, and recommended next action.

- [x] **Step 5: Run the complete verification gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Expected: 51 unit tests pass, Blender prints
`ALPHA_MATERIAL_SEPARATOR_BENCHMARK_CONTRACTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, source validation succeeds, and
`git diff --check` reports no errors.

- [x] **Step 6: Commit the measured documentation**

```powershell
git add -- `
  docs/performance.md `
  docs/testing.md `
  PLAN.md `
  docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: record Apply preflight baseline"
```

- [x] **Step 7: Mark this implementation plan complete**

Change every checkbox in this plan to `[x]`, then commit only the plan:

```powershell
git add -- docs/superpowers/plans/2026-08-01-apply-preflight-benchmark.md
git diff --cached --check
git commit -m "docs: complete Apply preflight benchmark plan"
```
