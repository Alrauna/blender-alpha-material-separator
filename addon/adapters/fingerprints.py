# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable structural fingerprints for material identity and stale checks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import bpy


_NODE_SETTINGS = (
    "blend_type",
    "clamp_factor",
    "clamp_result",
    "data_type",
    "extension",
    "interpolation",
    "operation",
    "projection",
    "projection_blend",
    "uv_map",
    "vector_type",
)


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return [_plain(item) for item in value]
    except TypeError:
        return repr(value)


def node_tree_payload(tree: bpy.types.NodeTree | None, _visited=None) -> dict[str, Any]:
    if tree is None:
        return {"nodes": [], "links": []}
    visited = set() if _visited is None else _visited
    pointer = tree.as_pointer()
    if pointer in visited:
        return {"cycle": True}
    visited.add(pointer)
    nodes = []
    for node in sorted(tree.nodes, key=lambda item: item.name):
        settings = {
            key: _plain(getattr(node, key))
            for key in _NODE_SETTINGS
            if hasattr(node, key)
        }
        inputs = []
        for socket in node.inputs:
            if not socket.is_linked and hasattr(socket, "default_value"):
                inputs.append((socket.identifier, _plain(socket.default_value)))
        image = getattr(node, "image", None)
        image_payload = None
        if image is not None:
            image_payload = {
                "alpha_mode": image.alpha_mode,
                "channels": image.channels,
                "colorspace": image.colorspace_settings.name,
                "dimensions": [int(image.size[0]), int(image.size[1])],
                "source": image.source,
            }
        group_payload = None
        if node.bl_idname == "ShaderNodeGroup":
            group_payload = node_tree_payload(node.node_tree, visited)
        nodes.append(
            {
                "active_output": bool(getattr(node, "is_active_output", False)),
                "group": group_payload,
                "image": image_payload,
                "inputs": inputs,
                "name": node.name,
                "settings": settings,
                "type": node.bl_idname,
            }
        )
    links = sorted(
        (
            link.from_node.name,
            link.from_socket.identifier,
            link.to_node.name,
            link.to_socket.identifier,
        )
        for link in tree.links
    )
    visited.remove(pointer)
    return {"links": links, "nodes": nodes}


def material_fingerprint(material: bpy.types.Material) -> str:
    payload = {
        "diffuse_color": _plain(material.diffuse_color),
        "node_tree": node_tree_payload(material.node_tree),
        "surface_render_method": getattr(material, "surface_render_method", None),
        "use_nodes": bool(material.use_nodes),
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(encoded.encode(), digest_size=32).hexdigest()


def source_fingerprint(material: bpy.types.Material, image_digest: str) -> str:
    payload = f"AMS_SOURCE_V1:{material_fingerprint(material)}:{image_digest}"
    return hashlib.blake2b(payload.encode(), digest_size=32).hexdigest()
