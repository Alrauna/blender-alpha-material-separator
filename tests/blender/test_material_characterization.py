# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for anonymous material characterization."""

from __future__ import annotations

import json

from scripts.characterize_materials import summarize_materials
from tests.fixtures.generated_materials import create_characterization_materials


def run() -> None:
    materials = create_characterization_materials()
    summary = summarize_materials(materials)
    counts = summary["feature_material_counts"]

    assert summary["materials_scanned"] == 10, summary
    assert counts["direct_image_alpha_to_principled_alpha"] >= 4, counts
    assert counts["image_color_to_principled_base_color"] >= 2, counts
    assert counts["separate_color_mask_and_base_color_images"] == 1, counts
    assert counts["mapping_node_upstream_of_image"] == 1, counts
    assert counts["reroute_node_present"] == 1, counts
    assert counts["node_group_present"] == 1, counts
    assert counts["math_or_mix_node_present"] == 1, counts
    assert counts["multiple_image_nodes"] >= 3, counts
    assert counts["direct_uv_map_to_image_vector"] == 1, counts
    assert counts["direct_texture_coordinate_uv_to_image_vector"] == 1, counts

    encoded = json.dumps(summary, sort_keys=True)
    assert "AMS_SYNTH" not in encoded, encoded
    assert "filepath" not in encoded, encoded
    assert "material_name" not in encoded, encoded

    print("ALPHA_MATERIAL_SEPARATOR_CHARACTERIZATION_TESTS_OK")
