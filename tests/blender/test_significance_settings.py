# SPDX-License-Identifier: GPL-3.0-or-later
"""Below-significance faces must not cancel their material group."""

from __future__ import annotations

import bpy

from addon import runtime
from addon.adapters.assignment import build_assignment_plan
from tests.blender.test_analysis_preview import _clear_scene

WIDTH = HEIGHT = 4


def _image():
    image = bpy.data.images.new("AMS_GATE_IMAGE", width=WIDTH, height=HEIGHT, alpha=True)
    pixels = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            transparent = x < 2 and y < 2
            pixels.extend((1.0, 1.0, 1.0, 0.0 if transparent else 1.0))
    image.pixels.foreach_set(pixels)
    return image


def _material(image):
    material = bpy.data.materials.new("AMS_GATE_SOURCE")
    material.use_nodes = True
    tree = material.node_tree
    principled = tree.nodes["Principled BSDF"]
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    tree.links.new(texture.outputs["Alpha"], principled.inputs["Alpha"])
    material.blend_method = "BLEND"
    return material


def _two_face_object(material):
    """Face 0 covers four affected texels. Face 1 covers one."""
    mesh = bpy.data.meshes.new("AMS_GATE_MESH")
    mesh.from_pydata(
        (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
            (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0), (2.0, 1.0, 0.0),
        ),
        (),
        ((0, 1, 2, 3), (4, 5, 6, 7)),
    )
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    quarter = 1.0 / WIDTH
    face_uvs = {
        0: ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        1: ((0.0, 0.0), (quarter, 0.0), (quarter, quarter), (0.0, quarter)),
    }
    for polygon in mesh.polygons:
        corners = face_uvs[polygon.index]
        for corner, loop_index in enumerate(polygon.loop_indices):
            uv_layer.uv[loop_index].vector = corners[corner]
    object_ = bpy.data.objects.new("AMS_GATE_OBJECT", mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_
    return object_


def _plan(suppressed_policy):
    state = bpy.context.window_manager.alpha_material_separator_api
    report = runtime.report(state.analysis_id)
    return build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy=suppressed_policy,
        unsupported_policy="CANCEL_SOURCE_MATERIAL",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    ).public_payload()


def _assert_defaults_keep_source():
    settings = bpy.context.window_manager.alpha_material_separator_settings
    assert settings.bl_rna.properties["suppressed_policy"].default == "KEEP_SOURCE"
    # Operator properties are exposed through get_rna_type(), not the class
    # bl_rna, which never carries the annotation-defined properties.
    for operator in (
        bpy.ops.alpha_material_separator.assign_materials,
        bpy.ops.alpha_material_separator.select_faces,
    ):
        rna = operator.get_rna_type()
        assert (
            rna.properties["suppressed_policy"].default == "KEEP_SOURCE"
        ), rna.identifier


def _assert_sibling_face_survives():
    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}, result

    default_plan = _plan("KEEP_SOURCE")
    assert default_plan["blocked"] == [], default_plan["blocked"]
    assert default_plan["faces_to_reassign"] == 1, default_plan

    blocked_plan = _plan("CANCEL_SOURCE_MATERIAL")
    reasons = [entry.get("reason") for entry in blocked_plan["blocked"]]
    assert reasons == ["SUPPRESSED_FACES"], reasons
    assert blocked_plan["faces_to_reassign"] == 0, blocked_plan


def _assert_default_assignment_moves_only_the_qualifying_face(object_):
    """The shipped default must assign the group without naming a policy."""
    state = bpy.context.window_manager.alpha_material_separator_api
    result = bpy.ops.alpha_material_separator.assign_materials(
        expected_analysis_id=state.analysis_id,
    )
    assert result == {"FINISHED"}, state.last_status_json
    indices = tuple(polygon.material_index for polygon in object_.data.polygons)
    assert indices == (1, 0), indices


def run() -> None:
    _clear_scene()
    object_ = _two_face_object(_material(_image()))
    _assert_defaults_keep_source()
    _assert_sibling_face_survives()
    _assert_default_assignment_moves_only_the_qualifying_face(object_)
    _clear_scene()
    print("ALPHA_MATERIAL_SEPARATOR_SIGNIFICANCE_TESTS_OK")
