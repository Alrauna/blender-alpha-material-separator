# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic Blender material graphs with no external assets."""

from __future__ import annotations

import bpy


def _image(name: str) -> bpy.types.Image:
    return bpy.data.images.new(name=name, width=2, height=2, alpha=True)


def _base_material(name: str):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.is_active_output = True
    principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
    tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material, tree, principled


def _image_node(tree: bpy.types.NodeTree, name: str):
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = _image(name)
    return node


def create_characterization_materials() -> tuple[bpy.types.Material, ...]:
    """Create one synthetic example for every surveyed graph family."""
    materials: list[bpy.types.Material] = []

    material, tree, principled = _base_material("AMS_SYNTH_DIRECT_ALPHA")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_DIRECT")
    tree.links.new(image.outputs["Alpha"], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_COLOR_ALPHA")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_COLOR")
    tree.links.new(image.outputs["Color"], principled.inputs["Base Color"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_SEPARATE_MASK")
    color = _image_node(tree, "AMS_SYNTH_COLOR_SOURCE")
    mask = _image_node(tree, "AMS_SYNTH_MASK_SOURCE")
    tree.links.new(color.outputs["Color"], principled.inputs["Base Color"])
    tree.links.new(mask.outputs["Color"], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_MAPPING")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_MAPPING")
    texcoord = tree.nodes.new("ShaderNodeTexCoord")
    mapping = tree.nodes.new("ShaderNodeMapping")
    tree.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])
    tree.links.new(mapping.outputs["Vector"], image.inputs["Vector"])
    tree.links.new(image.outputs["Alpha"], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_REROUTE")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_REROUTE")
    reroute = tree.nodes.new("NodeReroute")
    tree.links.new(image.outputs["Alpha"], reroute.inputs[0])
    tree.links.new(reroute.outputs[0], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_GROUP")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_GROUP")
    group_tree = bpy.data.node_groups.new("AMS_SYNTH_GROUP_TREE", "ShaderNodeTree")
    group = tree.nodes.new("ShaderNodeGroup")
    group.node_tree = group_tree
    tree.links.new(image.outputs["Alpha"], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_MULTIPLY")
    first = _image_node(tree, "AMS_SYNTH_IMAGE_MULTIPLY_A")
    second = _image_node(tree, "AMS_SYNTH_IMAGE_MULTIPLY_B")
    multiply = tree.nodes.new("ShaderNodeMath")
    multiply.operation = "MULTIPLY"
    tree.links.new(first.outputs["Alpha"], multiply.inputs[0])
    tree.links.new(second.outputs["Alpha"], multiply.inputs[1])
    tree.links.new(multiply.outputs[0], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, _principled = _base_material("AMS_SYNTH_AMBIGUOUS")
    _image_node(tree, "AMS_SYNTH_IMAGE_AMBIGUOUS_A")
    _image_node(tree, "AMS_SYNTH_IMAGE_AMBIGUOUS_B")
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_UV_MAP")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_UV_MAP")
    uv_map = tree.nodes.new("ShaderNodeUVMap")
    tree.links.new(uv_map.outputs["UV"], image.inputs["Vector"])
    tree.links.new(image.outputs["Alpha"], principled.inputs["Alpha"])
    materials.append(material)

    material, tree, principled = _base_material("AMS_SYNTH_TEXCOORD")
    image = _image_node(tree, "AMS_SYNTH_IMAGE_TEXCOORD")
    texcoord = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(texcoord.outputs["UV"], image.inputs["Vector"])
    tree.links.new(image.outputs["Alpha"], principled.inputs["Alpha"])
    materials.append(material)

    return tuple(materials)
