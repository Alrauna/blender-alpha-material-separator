# SPDX-License-Identifier: GPL-3.0-or-later
"""FBX material-section export/reimport acceptance test."""

from __future__ import annotations

from pathlib import Path

import bpy

from tests.blender.test_analysis_preview import _clear_scene, _material
from tests.blender.test_assignment import _analyze, _assign, _select_only


def _two_section_fixture():
    image = bpy.data.images.new("AMS_FBX_IMAGE", width=2, height=1, alpha=True)
    image.pixels.foreach_set(
        (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0)
    )
    material, _tree, _principled, _texture = _material("AMS_FBX_SOURCE", image)
    mesh = bpy.data.meshes.new("AMS_FBX_MESH")
    mesh.from_pydata(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
        ),
        (),
        ((0, 1, 2, 3), (4, 5, 6, 7)),
    )
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    coordinates = (
        (0.0, 0.0),
        (0.5, 0.0),
        (0.5, 1.0),
        (0.0, 1.0),
        (0.5, 0.0),
        (1.0, 0.0),
        (1.0, 1.0),
        (0.5, 1.0),
    )
    modern = getattr(uv_layer, "uv", None)
    for loop in mesh.loops:
        if modern is not None:
            modern[loop.index].vector = coordinates[loop.vertex_index]
        else:
            uv_layer.data[loop.index].uv = coordinates[loop.vertex_index]
    object_ = bpy.data.objects.new("AMS_FBX_OBJECT", mesh)
    bpy.context.collection.objects.link(object_)
    _select_only(object_)
    return object_


def run() -> None:
    _clear_scene()
    object_ = _two_section_fixture()
    analysis_id = _analyze(object_)
    assigned, state = _assign(analysis_id)
    assert assigned == {"FINISHED"}, state.last_status_json
    assert len(object_.material_slots) == 2
    assert {polygon.material_index for polygon in object_.data.polygons} == {0, 1}

    output = Path(__file__).resolve().parents[2] / ".test-output" / "ams-sections.fbx"
    output.parent.mkdir(parents=True, exist_ok=True)
    _select_only(object_)
    result = bpy.ops.export_scene.fbx(
        filepath=str(output),
        use_selection=True,
        add_leaf_bones=False,
        bake_anim=False,
    )
    assert result == {"FINISHED"}, result
    _clear_scene()
    imported = bpy.ops.wm.fbx_import(filepath=str(output))
    assert imported == {"FINISHED"}, imported
    mesh_objects = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    assert len(mesh_objects) == 1, mesh_objects
    imported_object = mesh_objects[0]
    used_indices = {polygon.material_index for polygon in imported_object.data.polygons}
    assert len(imported_object.material_slots) >= 2
    assert len(used_indices) == 2, used_indices
    assert all(imported_object.material_slots[index].material for index in used_indices)
    print("ALPHA_MATERIAL_SEPARATOR_FBX_EXPORT_TESTS_OK")
