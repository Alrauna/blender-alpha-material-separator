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
