# Apply Preflight Benchmark Design

**Status:** Proposed for user review
**Date:** 2026-08-01

## Goal

Record a distinct, reproducible timing row for the safety work performed after
the user invokes **Apply Material Separation** and before any mutation begins.

## Approved measurement

Extend the existing generated structural-revalidation benchmark in
`tests/blender/run_benchmarks.py`.

The new row will:

- reuse its 4,900-polygon mesh and clean file-backed 1K image;
- call the real `_validated_plan()` preflight boundary;
- include authoritative report validation, assignment-plan rebuilding, public
  plan creation, and review-signature comparison;
- discard one warm-up and record the median of five measured runs;
- require every preflight to return a valid report and actionable plan;
- snapshot polygon material indices, material slots, material datablocks, and
  report identity before measurement and prove they remain unchanged;
- record the individual runs, median, ratio to cold analysis, and existing
  validation instrumentation counters in the ignored benchmark JSON;
- add an **Apply preflight median** row to `docs/performance.md`.

## Implementation boundary

The benchmark may use a minimal operator-shaped object and context-shaped object
to call `_validated_plan()` exactly as the Blender operator does. Test-only
shapes remain in the benchmark module.

No production timer, public API field, runtime status field, dependency, new
fixture family, or material mutation is added.

## Verification

- Add a generated benchmark contract that fails while the Apply-preflight
  metrics are absent.
- Run the focused revalidation benchmark with one warm-up and five measurements.
- Confirm the preflight succeeds, remains mutation-free, and records five
  non-negative durations plus their median.
- Run the complete unit and headless Blender suites.
- Validate the extension source.
- Update `PLAN.md`, `docs/testing.md`, `docs/performance.md`, and
  `docs/HANDOFF.md` with the measured result and close only this release item.

## Non-goals

- Do not time confirmation-dialog drawing or user response.
- Do not time material creation, slot appending, face reassignment, or Undo.
- Do not establish a new arbitrary pass/fail latency threshold from one
  baseline.
- Do not change analysis, preflight, assignment, or cache behavior.
