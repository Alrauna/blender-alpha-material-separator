# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare a generated, redistributable scene for the manual UI smoke test."""

from __future__ import annotations

import sys
from array import array
from pathlib import Path

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import addon  # noqa: E402


def _alpha_image(size: int = 1024) -> bpy.types.Image:
    image = bpy.data.images.new("AMS_UI_ALPHA", width=size, height=size, alpha=True)
    row = array("f")
    for x in range(size):
        alpha = 0.25 if x < size // 2 else 1.0
        row.extend((1.0, 1.0, 1.0, alpha))
    pixels = row * size
    image.pixels.foreach_set(pixels)
    image.update()
    return image


def _material(image: bpy.types.Image) -> bpy.types.Material:
    material = bpy.data.materials.new("AMS_UI_SOURCE")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.is_active_output = True
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    material.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    material.node_tree.links.new(texture.outputs["Color"], principled.inputs["Base Color"])
    return material


def _grid(name: str, segments: int, x_offset: float, material) -> bpy.types.Object:
    stride = segments + 1
    vertices = [
        (x_offset + x / segments * 4.0, y / segments * 4.0, 0.0)
        for y in range(stride)
        for x in range(stride)
    ]
    faces = []
    for y in range(segments):
        for x in range(segments):
            first = y * stride + x
            faces.append((first, first + 1, first + stride + 1, first + stride))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, (), faces)
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    modern_uv = getattr(uv_layer, "uv", None)
    for loop in mesh.loops:
        vertex = vertices[loop.vertex_index]
        uv = ((vertex[0] - x_offset) / 4.0, vertex[1] / 4.0)
        if modern_uv is not None:
            modern_uv[loop.index].vector = uv
        else:
            uv_layer.data[loop.index].uv = uv
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    return object_


def main() -> None:
    bpy.ops.object.mode_set(mode="OBJECT") if bpy.context.object else None
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    image = _alpha_image()
    material = _material(image)
    objects = (
        _grid("AMS_UI_LEFT", 96, -4.5, material),
        _grid("AMS_UI_RIGHT", 96, 0.5, material),
    )
    bpy.ops.object.select_all(action="DESELECT")
    for object_ in objects:
        object_.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    addon.register()
    bpy.context.window_manager.alpha_material_separator_settings.preview_classes = {
        "ALPHA_AFFECTED",
        "MIXED",
    }
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            with bpy.context.temp_override(area=area):
                bpy.ops.view3d.view_selected(use_all_regions=False)
            break
    print("ALPHA_MATERIAL_SEPARATOR_INTERACTIVE_SCENE_READY", flush=True)


if __name__ == "__main__":
    main()
