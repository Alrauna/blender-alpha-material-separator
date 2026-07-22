# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative material image and UV resolver for approved graph patterns."""

from __future__ import annotations

from dataclasses import dataclass

import bpy

from ..core import AddressMode


@dataclass(frozen=True, slots=True)
class MaterialResolution:
    material: bpy.types.Material
    supported: bool
    reason: str
    image: bpy.types.Image | None = None
    uv_map_name: str = ""
    address_mode: AddressMode = AddressMode.REPEAT
    channel: str = "ALPHA"
    source_kind: str = ""


def _incoming_link(tree: bpy.types.NodeTree, socket: bpy.types.NodeSocket | None):
    if socket is None:
        return None
    links = tuple(link for link in tree.links if link.to_socket == socket)
    return links[0] if len(links) == 1 else None


def _trace_reroutes(tree: bpy.types.NodeTree, socket: bpy.types.NodeSocket | None):
    link = _incoming_link(tree, socket)
    visited: set[int] = set()
    while link is not None and link.from_node.bl_idname == "NodeReroute":
        pointer = link.from_node.as_pointer()
        if pointer in visited:
            return None
        visited.add(pointer)
        link = _incoming_link(tree, link.from_node.inputs[0])
    return link


def _active_principled(material: bpy.types.Material):
    tree = material.node_tree
    if tree is None:
        return None
    outputs = tuple(
        node
        for node in tree.nodes
        if node.bl_idname == "ShaderNodeOutputMaterial" and node.is_active_output
    )
    if len(outputs) != 1:
        return None
    surface = outputs[0].inputs.get("Surface")
    link = _incoming_link(tree, surface)
    if link is None or link.from_node.bl_idname != "ShaderNodeBsdfPrincipled":
        return None
    return link.from_node


def _active_render_uv(mesh: bpy.types.Mesh) -> str:
    for layer in mesh.uv_layers:
        if getattr(layer, "active_render", False):
            return layer.name
    active = mesh.uv_layers.active
    return active.name if active is not None else ""


def _resolve_uv(
    mesh: bpy.types.Mesh,
    image_node: bpy.types.ShaderNodeTexImage,
    explicit_uv: str,
) -> tuple[str, str | None]:
    if explicit_uv:
        return explicit_uv, None if mesh.uv_layers.get(explicit_uv) else "UV_OVERRIDE_NOT_FOUND"

    vector = image_node.inputs.get("Vector")
    link = _incoming_link(image_node.id_data, vector)
    if link is None:
        name = _active_render_uv(mesh)
        return name, None if name else "NO_ACTIVE_RENDER_UV"
    if link.from_node.bl_idname == "ShaderNodeUVMap":
        name = link.from_node.uv_map
        return name, None if name and mesh.uv_layers.get(name) else "UV_MAP_NOT_FOUND"
    if (
        link.from_node.bl_idname == "ShaderNodeTexCoord"
        and link.from_socket.identifier == "UV"
    ):
        name = _active_render_uv(mesh)
        return name, None if name else "NO_ACTIVE_RENDER_UV"
    return "", "UNSUPPORTED_VECTOR_PATH"


def _address_mode(image_node, requested: str) -> AddressMode:
    if requested != "AUTO":
        return AddressMode(requested)
    extension = getattr(image_node, "extension", "REPEAT")
    return AddressMode(extension) if extension in AddressMode._value2member_map_ else AddressMode.REPEAT


def _validate_image(image: bpy.types.Image | None) -> str | None:
    if image is None:
        return "IMAGE_MISSING"
    if image.source not in {"FILE", "GENERATED"}:
        return "UNSUPPORTED_IMAGE_SOURCE"
    if int(image.size[0]) <= 0 or int(image.size[1]) <= 0:
        return "IMAGE_HAS_NO_PIXELS"
    return None


def resolve_material(
    material: bpy.types.Material,
    mesh: bpy.types.Mesh,
    *,
    explicit_image: bpy.types.Image | None = None,
    explicit_uv: str = "",
    explicit_channel: str = "ALPHA",
    requested_address_mode: str = "AUTO",
) -> MaterialResolution:
    if explicit_image is not None:
        reason = _validate_image(explicit_image)
        uv_name = explicit_uv or _active_render_uv(mesh)
        if reason is None and not uv_name:
            reason = "NO_ACTIVE_RENDER_UV"
        if reason is None and mesh.uv_layers.get(uv_name) is None:
            reason = "UV_OVERRIDE_NOT_FOUND"
        return MaterialResolution(
            material=material,
            supported=reason is None,
            reason=reason or "OK",
            image=explicit_image,
            uv_map_name=uv_name,
            address_mode=(
                AddressMode.REPEAT
                if requested_address_mode == "AUTO"
                else AddressMode(requested_address_mode)
            ),
            channel=explicit_channel,
            source_kind="EXPLICIT_OVERRIDE",
        )

    tree = material.node_tree if material.use_nodes else None
    if tree is None:
        return MaterialResolution(material, False, "MATERIAL_HAS_NO_NODE_TREE")
    principled = _active_principled(material)
    if principled is None:
        return MaterialResolution(material, False, "NO_ACTIVE_PRINCIPLED_OUTPUT")

    alpha_link = _trace_reroutes(tree, principled.inputs.get("Alpha"))
    image_node = None
    source_kind = ""
    if alpha_link is not None:
        if alpha_link.from_node.bl_idname != "ShaderNodeTexImage":
            return MaterialResolution(material, False, "UNSUPPORTED_ALPHA_PATH")
        if alpha_link.from_socket.identifier == "Alpha":
            image_node = alpha_link.from_node
            source_kind = "DIRECT_IMAGE_ALPHA"
        else:
            return MaterialResolution(material, False, "COLOR_TO_ALPHA_REQUIRES_OVERRIDE")
    else:
        image_nodes = tuple(
            node for node in tree.nodes if node.bl_idname == "ShaderNodeTexImage"
        )
        base_link = _trace_reroutes(tree, principled.inputs.get("Base Color"))
        if (
            len(image_nodes) == 1
            and base_link is not None
            and base_link.from_node == image_nodes[0]
            and base_link.from_socket.identifier == "Color"
        ):
            image_node = image_nodes[0]
            source_kind = "UNIQUE_BASE_COLOR_IMAGE_ALPHA"
        else:
            return MaterialResolution(material, False, "NO_AUTHORITATIVE_ALPHA_IMAGE")

    reason = _validate_image(image_node.image)
    if reason is not None:
        return MaterialResolution(material, False, reason)
    if getattr(image_node, "projection", "FLAT") != "FLAT":
        return MaterialResolution(material, False, "UNSUPPORTED_PROJECTION")
    uv_name, uv_error = _resolve_uv(mesh, image_node, explicit_uv)
    if uv_error is not None:
        return MaterialResolution(material, False, uv_error)
    return MaterialResolution(
        material=material,
        supported=True,
        reason="OK",
        image=image_node.image,
        uv_map_name=uv_name,
        address_mode=_address_mode(image_node, requested_address_mode),
        channel="ALPHA",
        source_kind=source_kind,
    )
