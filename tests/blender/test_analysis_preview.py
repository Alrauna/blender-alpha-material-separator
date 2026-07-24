# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless Blender analysis, resolver, stale-check, and preview tests."""

from __future__ import annotations

import json

import bpy

from addon import runtime
from addon.adapters.analysis import AnalysisConfig, AnalysisEngine
from addon.adapters.material_resolver import resolve_material


def _clear_scene() -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _image(name: str):
    image = bpy.data.images.new(name, width=2, height=2, alpha=True)
    image.pixels.foreach_set(
        (
            1.0,
            1.0,
            1.0,
            0.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
        )
    )
    return image


def _material(name: str, image):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.is_active_output = True
    principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    tree.links.new(texture.outputs["Color"], principled.inputs["Base Color"])
    return material, tree, principled, texture


def _quad(name: str, material):
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        (),
        ((0, 1, 2, 3),),
    )
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    coordinates = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    modern = getattr(uv_layer, "uv", None)
    for loop in mesh.loops:
        if modern is not None:
            modern[loop.index].vector = coordinates[loop.vertex_index]
        else:
            uv_layer.data[loop.index].uv = coordinates[loop.vertex_index]
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    return object_


def _mesh_snapshot(object_):
    mesh = object_.data
    uv_layer = mesh.uv_layers.active
    modern = getattr(uv_layer, "uv", None)
    uvs = tuple(
        tuple(modern[index].vector if modern is not None else uv_layer.data[index].uv)
        for index in range(len(mesh.loops))
    )
    return {
        "vertices": tuple(tuple(vertex.co) for vertex in mesh.vertices),
        "polygons": tuple(
            (polygon.loop_start, polygon.loop_total, polygon.material_index)
            for polygon in mesh.polygons
        ),
        "materials": tuple(material.as_pointer() for material in mesh.materials),
        "uvs": uvs,
    }


def _resolver_tests(material, mesh, image, tree, principled, texture):
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.source_kind == "UNIQUE_BASE_COLOR_IMAGE_ALPHA", resolution
    assert resolution.uv_map_name == "UVMap", resolution

    tree.links.new(texture.outputs["Alpha"], principled.inputs["Alpha"])
    reroute = tree.nodes.new("NodeReroute")
    direct_link = next(
        link for link in tree.links if link.to_socket == principled.inputs["Alpha"]
    )
    tree.links.remove(direct_link)
    tree.links.new(texture.outputs["Alpha"], reroute.inputs[0])
    tree.links.new(reroute.outputs[0], principled.inputs["Alpha"])
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.source_kind == "DIRECT_IMAGE_ALPHA", resolution

    uv_map = tree.nodes.new("ShaderNodeUVMap")
    uv_map.uv_map = "UVMap"
    tree.links.new(uv_map.outputs["UV"], texture.inputs["Vector"])
    assert resolve_material(material, mesh).supported
    tree.links.remove(next(link for link in tree.links if link.to_socket == texture.inputs["Vector"]))
    texcoord = tree.nodes.new("ShaderNodeTexCoord")
    tree.links.new(texcoord.outputs["UV"], texture.inputs["Vector"])
    assert resolve_material(material, mesh).supported

    second = tree.nodes.new("ShaderNodeTexImage")
    second.image = image
    assert resolve_material(material, mesh).supported, "direct alpha remains authoritative"

    direct_alpha = next(
        link for link in tree.links if link.to_socket == principled.inputs["Alpha"]
    )
    tree.links.remove(direct_alpha)
    unsupported = resolve_material(material, mesh)
    assert not unsupported.supported
    assert unsupported.reason == "NO_AUTHORITATIVE_ALPHA_IMAGE", unsupported

    override = resolve_material(
        material,
        mesh,
        explicit_image=image,
        explicit_uv="UVMap",
        explicit_channel="RED",
    )
    assert override.supported and override.channel == "RED", override


def run() -> None:
    _clear_scene()
    image = _image("AMS_ANALYSIS_IMAGE")
    material, tree, principled, texture = _material("AMS_ANALYSIS_MATERIAL", image)
    first = _quad("AMS_ANALYSIS_A", material)
    second = _quad("AMS_ANALYSIS_B", material)
    bpy.context.view_layer.objects.active = first

    _resolver_tests(material, first.data, image, tree, principled, texture)

    # Restore the simple unique-base-color graph used for default analysis.
    for node in tuple(tree.nodes):
        if node not in {principled, texture} and node.bl_idname != "ShaderNodeOutputMaterial":
            tree.nodes.remove(node)
    for link in tuple(tree.links):
        if link.to_socket == principled.inputs["Alpha"] or link.to_socket == texture.inputs["Vector"]:
            tree.links.remove(link)

    before = (_mesh_snapshot(first), _mesh_snapshot(second))
    deferred = AnalysisEngine((first, second), AnalysisConfig(), defer_images=True)
    assert deferred.completed == 0
    assert deferred.step(1) is False
    assert deferred.completed > 0
    deferred.cancel()
    assert deferred.step(1) is True
    try:
        deferred.finish()
    except RuntimeError:
        pass
    else:
        raise AssertionError("cancelled deferred analysis published a report")

    result = bpy.ops.alpha_material_separator.analyze(
        api_major=1,
        alpha_threshold=0.999,
        min_affected_texels=1,
        min_affected_fraction=0.0,
        margin_texels=0,
    )
    assert result == {"FINISHED"}, result
    state = bpy.context.window_manager.alpha_material_separator_api
    payload = json.loads(state.report_json)
    assert payload["validation_state"] == "CLEAN", payload
    assert payload["pending_scopes"] == [], payload
    assert payload["counts"]["MIXED"] == 2, payload
    assert payload["counts"]["OPAQUE"] == 0, payload
    assert before == (_mesh_snapshot(first), _mesh_snapshot(second))
    report = runtime.report(state.analysis_id)
    assert report is not None

    preview = bpy.ops.alpha_material_separator.select_faces(
        api_major=1,
        expected_analysis_id=state.analysis_id,
        classes={"MIXED"},
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert preview == {"FINISHED"}, preview
    assert first.mode == "EDIT" and second.mode == "EDIT"
    repeat_preview = bpy.ops.alpha_material_separator.select_faces(
        api_major=1,
        expected_analysis_id=state.analysis_id,
        classes={"MIXED"},
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert repeat_preview == {"FINISHED"}, repeat_preview
    assert first.mode == "EDIT" and second.mode == "EDIT"
    bpy.ops.object.mode_set(mode="OBJECT")
    assert first.data.polygons[0].select and second.data.polygons[0].select

    uv_layer = first.data.uv_layers.active
    modern = getattr(uv_layer, "uv", None)
    if modern is not None:
        modern[0].vector.x += 0.125
    else:
        uv_layer.data[0].uv.x += 0.125
    runtime.mark_recheck("MESH_UPDATED", "MESH")
    stale = bpy.ops.alpha_material_separator.select_faces(
        api_major=1,
        expected_analysis_id=state.analysis_id,
        classes={"MIXED"},
        enter_edit_mode=False,
    )
    assert stale == {"CANCELLED"}, stale
    assert state.last_status_code == "STALE_ANALYSIS", state.last_status_json
    assert runtime.validation_state() == runtime.VALIDATION_STALE
    assert runtime.dirty_reason() == "INPUTS_CHANGED"
    assert runtime.snapshot()["last_validation_mode"] == "STRUCTURAL"

    shared = bpy.data.objects.new("AMS_ANALYSIS_SHARED", first.data)
    bpy.context.collection.objects.link(shared)
    bpy.ops.object.select_all(action="DESELECT")
    first.select_set(True)
    shared.select_set(True)
    bpy.context.view_layer.objects.active = first
    skipped = bpy.ops.alpha_material_separator.analyze()
    assert skipped == {"FINISHED"}, skipped
    skipped_payload = json.loads(state.report_json)
    assert skipped_payload["skip_counts"]["MULTI_USER_MESH"] == 2, skipped_payload
    assert sum(skipped_payload["counts"].values()) == 0, skipped_payload
    print("ALPHA_MATERIAL_SEPARATOR_ANALYSIS_PREVIEW_TESTS_OK")
