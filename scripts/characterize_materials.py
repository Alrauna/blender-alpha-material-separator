# SPDX-License-Identifier: GPL-3.0-or-later
"""Create an anonymous aggregate of Blender material graph shapes.

Run this script inside Blender. It reads only ``.blend`` files already placed in
the ignored ``.local-references`` directory and writes an aggregate JSON file
back into that ignored directory. Names, paths, node labels, image pixels, and
per-material records are intentionally absent from the output.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable

import bpy

SCHEMA_VERSION = 1

FEATURE_KEYS = (
    "active_output_uses_principled",
    "direct_image_alpha_to_principled_alpha",
    "image_color_to_principled_alpha",
    "image_color_to_principled_base_color",
    "separate_color_mask_and_base_color_images",
    "image_metadata_has_alpha_channel",
    "unlinked_image_vector",
    "direct_uv_map_to_image_vector",
    "direct_texture_coordinate_uv_to_image_vector",
    "mapping_node_upstream_of_image",
    "reroute_node_present",
    "node_group_present",
    "math_or_mix_node_present",
    "multiple_image_nodes",
)


def _incoming_link(node_tree: bpy.types.NodeTree, socket: bpy.types.NodeSocket):
    for link in node_tree.links:
        if link.to_socket == socket:
            return link
    return None


def _active_principled(material: bpy.types.Material):
    node_tree = material.node_tree
    if node_tree is None:
        return None
    for node in node_tree.nodes:
        if node.bl_idname != "ShaderNodeOutputMaterial" or not node.is_active_output:
            continue
        surface = node.inputs.get("Surface")
        link = _incoming_link(node_tree, surface) if surface is not None else None
        if link is not None and link.from_node.bl_idname == "ShaderNodeBsdfPrincipled":
            return link.from_node
    return None


def characterize_material(material: bpy.types.Material) -> dict[str, object]:
    """Return anonymous booleans and counts for one material."""
    features = {key: False for key in FEATURE_KEYS}
    features["image_node_count"] = 0

    node_tree = material.node_tree if material.use_nodes else None
    if node_tree is None:
        return features

    nodes = tuple(node_tree.nodes)
    image_nodes = tuple(
        node for node in nodes if node.bl_idname == "ShaderNodeTexImage"
    )
    features["image_node_count"] = len(image_nodes)
    features["multiple_image_nodes"] = len(image_nodes) > 1
    features["reroute_node_present"] = any(
        node.bl_idname == "NodeReroute" for node in nodes
    )
    features["node_group_present"] = any(
        node.bl_idname == "ShaderNodeGroup" for node in nodes
    )
    features["math_or_mix_node_present"] = any(
        node.bl_idname in {"ShaderNodeMath", "ShaderNodeMix", "ShaderNodeMixRGB"}
        for node in nodes
    )
    features["image_metadata_has_alpha_channel"] = any(
        node.image is not None
        and node.image.channels >= 4
        and node.image.alpha_mode != "NONE"
        for node in image_nodes
    )

    for image_node in image_nodes:
        vector = image_node.inputs.get("Vector")
        vector_link = _incoming_link(node_tree, vector) if vector is not None else None
        if vector_link is None:
            features["unlinked_image_vector"] = True
        elif vector_link.from_node.bl_idname == "ShaderNodeUVMap":
            features["direct_uv_map_to_image_vector"] = True
        elif (
            vector_link.from_node.bl_idname == "ShaderNodeTexCoord"
            and vector_link.from_socket.name == "UV"
        ):
            features["direct_texture_coordinate_uv_to_image_vector"] = True
        elif vector_link.from_node.bl_idname == "ShaderNodeMapping":
            features["mapping_node_upstream_of_image"] = True

    principled = _active_principled(material)
    if principled is None:
        return features

    features["active_output_uses_principled"] = True
    alpha = principled.inputs.get("Alpha")
    base_color = principled.inputs.get("Base Color")
    alpha_link = _incoming_link(node_tree, alpha) if alpha is not None else None
    color_link = (
        _incoming_link(node_tree, base_color) if base_color is not None else None
    )

    if alpha_link is not None and alpha_link.from_node.bl_idname == "ShaderNodeTexImage":
        if alpha_link.from_socket.name == "Alpha":
            features["direct_image_alpha_to_principled_alpha"] = True
        elif alpha_link.from_socket.name == "Color":
            features["image_color_to_principled_alpha"] = True

    if color_link is not None and color_link.from_node.bl_idname == "ShaderNodeTexImage":
        features["image_color_to_principled_base_color"] = True

    if (
        alpha_link is not None
        and color_link is not None
        and alpha_link.from_node.bl_idname == "ShaderNodeTexImage"
        and color_link.from_node.bl_idname == "ShaderNodeTexImage"
        and alpha_link.from_node != color_link.from_node
    ):
        features["separate_color_mask_and_base_color_images"] = True

    return features


def summarize_materials(
    materials: Iterable[bpy.types.Material], *, files_scanned: int = 1, files_failed: int = 0
) -> dict[str, object]:
    """Aggregate graph features without retaining identifying records."""
    feature_counts = Counter({key: 0 for key in FEATURE_KEYS})
    image_count_histogram: Counter[str] = Counter()
    material_count = 0

    for material in materials:
        material_count += 1
        features = characterize_material(material)
        for key in FEATURE_KEYS:
            feature_counts[key] += int(bool(features[key]))
        image_count_histogram[str(features["image_node_count"])] += 1

    return {
        "feature_material_counts": dict(sorted(feature_counts.items())),
        "files_failed": files_failed,
        "files_scanned": files_scanned,
        "image_node_count_histogram": dict(sorted(image_count_histogram.items())),
        "materials_scanned": material_count,
        "schema_version": SCHEMA_VERSION,
    }


def summarize_current_file() -> dict[str, object]:
    """Aggregate materials currently loaded in Blender."""
    return summarize_materials(tuple(bpy.data.materials))


def characterize_reference_files(paths: Iterable[Path]) -> dict[str, object]:
    """Open each lawful private reference and return one anonymous aggregate."""
    feature_counts = Counter({key: 0 for key in FEATURE_KEYS})
    histogram: Counter[str] = Counter()
    files_scanned = 0
    files_failed = 0
    materials_scanned = 0

    for path in paths:
        try:
            bpy.ops.wm.open_mainfile(
                filepath=str(path),
                load_ui=False,
                use_scripts=False,
            )
        except Exception:
            files_failed += 1
            continue

        summary = summarize_current_file()
        files_scanned += 1
        materials_scanned += int(summary["materials_scanned"])
        feature_counts.update(summary["feature_material_counts"])
        histogram.update(summary["image_node_count_histogram"])

    return {
        "feature_material_counts": dict(sorted(feature_counts.items())),
        "files_failed": files_failed,
        "files_scanned": files_scanned,
        "image_node_count_histogram": dict(sorted(histogram.items())),
        "materials_scanned": materials_scanned,
        "schema_version": SCHEMA_VERSION,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    repository_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repository_root / ".local-references",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root
        / ".local-references"
        / "characterization"
        / "aggregate.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv or []))
    paths = sorted(args.input_dir.rglob("*.blend")) if args.input_dir.exists() else []
    aggregate = characterize_reference_files(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, sort_keys=True))
    return 0


if __name__ == "__main__":
    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    raise SystemExit(main(script_args))
