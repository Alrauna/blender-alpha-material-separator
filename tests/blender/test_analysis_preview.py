# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless Blender analysis, resolver, stale-check, and preview tests."""

from __future__ import annotations

import json

import bpy

from addon import runtime
from addon.adapters.analysis import AnalysisConfig, AnalysisEngine
from addon.adapters.assignment import build_assignment_plan
from addon.adapters.image_data import read_image_snapshot
from addon.adapters.material_resolver import resolve_material
from addon.core import FaceClass


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


def _out_of_range_uv_test() -> None:
    image = bpy.data.images.new("AMS_TILED_UV_IMAGE", width=2, height=1, alpha=True)
    image.pixels.foreach_set((1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0))
    material, _tree, _principled, texture = _material("AMS_TILED_UV_MATERIAL", image)
    texture.extension = "REPEAT"
    mesh = bpy.data.meshes.new("AMS_TILED_UV_MESH")
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
    coordinates = (
        (2.0, -1.0), (2.5, -1.0), (2.5, 0.0), (2.0, 0.0),
        (-1.5, 2.0), (-1.0, 2.0), (-1.0, 3.0), (-1.5, 3.0),
    )
    modern = getattr(uv_layer, "uv", None)
    for loop in mesh.loops:
        if modern is not None:
            modern[loop.index].vector = coordinates[loop.vertex_index]
        else:
            uv_layer.data[loop.index].uv = coordinates[loop.vertex_index]
    object_ = bpy.data.objects.new("AMS_TILED_UV_OBJECT", mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_

    assert bpy.ops.alpha_material_separator.analyze() == {"FINISHED"}
    report = runtime.report()
    object_result = next(
        item for item in report.object_results.values() if item.object == object_
    )
    results = [object_result.faces[index].result for index in range(2)]
    assert [item.classification for item in results] == [
        FaceClass.OPAQUE,
        FaceClass.ALPHA_AFFECTED,
    ], results
    assert all(not item.unsupported_reason for item in results), results


def _resolver_tests(material, mesh, image, tree, principled, texture):
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.source_kind == "UNIQUE_BASE_COLOR_IMAGE_ALPHA", resolution
    assert resolution.uv_map_name == "UVMap", resolution

    ancillary_image = _image("AMS_ANCILLARY_IMAGE")
    normal_texture = tree.nodes.new("ShaderNodeTexImage")
    normal_texture.image = ancillary_image
    normal_map = tree.nodes.new("ShaderNodeNormalMap")
    tree.links.new(normal_texture.outputs["Color"], normal_map.inputs["Color"])
    tree.links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
    roughness_texture = tree.nodes.new("ShaderNodeTexImage")
    roughness_texture.image = ancillary_image
    tree.links.new(roughness_texture.outputs["Color"], principled.inputs["Roughness"])
    emission_texture = tree.nodes.new("ShaderNodeTexImage")
    emission_texture.image = ancillary_image
    tree.links.new(emission_texture.outputs["Color"], principled.inputs["Emission Color"])
    disconnected_texture = tree.nodes.new("ShaderNodeTexImage")
    disconnected_texture.image = ancillary_image
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.image == image, resolution
    assert resolution.source_kind == "UNIQUE_BASE_COLOR_IMAGE_ALPHA", resolution

    base_link = next(
        link for link in tree.links if link.to_socket == principled.inputs["Base Color"]
    )
    tree.links.remove(base_link)
    base_reroute = tree.nodes.new("NodeReroute")
    tree.links.new(texture.outputs["Color"], base_reroute.inputs[0])
    tree.links.new(base_reroute.outputs[0], principled.inputs["Base Color"])
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.image == image, resolution
    assert resolution.source_kind == "UNIQUE_BASE_COLOR_IMAGE_ALPHA", resolution

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

    assert resolve_material(material, mesh).supported, "direct alpha remains authoritative"

    direct_alpha = next(
        link for link in tree.links if link.to_socket == principled.inputs["Alpha"]
    )
    tree.links.remove(direct_alpha)
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.image == image, resolution
    assert resolution.source_kind == "UNIQUE_BASE_COLOR_IMAGE_ALPHA", resolution

    dangling_reroute = tree.nodes.new("NodeReroute")
    tree.links.new(dangling_reroute.outputs[0], principled.inputs["Alpha"])
    unsupported = resolve_material(material, mesh)
    assert not unsupported.supported
    assert unsupported.reason == "UNSUPPORTED_ALPHA_PATH", unsupported
    tree.nodes.remove(dangling_reroute)

    base_link = next(
        link for link in tree.links if link.to_socket == principled.inputs["Base Color"]
    )
    tree.links.remove(base_link)
    mix = tree.nodes.new("ShaderNodeMixRGB")
    tree.links.new(texture.outputs["Color"], mix.inputs[1])
    tree.links.new(mix.outputs["Color"], principled.inputs["Base Color"])
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

    tree.nodes.remove(mix)
    tree.links.new(texture.outputs["Color"], principled.inputs["Base Color"])

    original_alpha_mode = image.alpha_mode
    for alpha_mode in ("STRAIGHT", "PREMUL", "CHANNEL_PACKED", "NONE"):
        image.alpha_mode = alpha_mode
        snapshot = read_image_snapshot(image, channel="ALPHA", threshold=0.999)
        assert sum(snapshot.grid.affected) == 1, (alpha_mode, snapshot.grid)
    image.alpha_mode = original_alpha_mode

    opaque_image = bpy.data.images.new(
        "AMS_OPAQUE_BASE_COLOR", width=2, height=2, alpha=False
    )
    opaque_snapshot = read_image_snapshot(
        opaque_image, channel="ALPHA", threshold=0.999
    )
    assert opaque_snapshot.component_count in {3, 4}, opaque_snapshot
    assert not any(opaque_snapshot.grid.affected), opaque_snapshot.grid
    texture.image = opaque_image
    resolution = resolve_material(material, mesh)
    assert resolution.supported, resolution
    assert resolution.source_kind == "UNIQUE_BASE_COLOR_IMAGE_ALPHA", resolution

    texture.image = None
    missing = resolve_material(material, mesh)
    assert not missing.supported and missing.reason == "IMAGE_MISSING", missing
    texture.image = image


def run() -> None:
    _clear_scene()
    _out_of_range_uv_test()
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

    bpy.ops.object.mode_set(mode="EDIT")
    edit_mode_result = bpy.ops.alpha_material_separator.analyze(
        api_major=1,
        alpha_threshold=0.999,
        min_affected_texels=1,
        min_affected_fraction=0.0,
        margin_texels=0,
    )
    state = bpy.context.window_manager.alpha_material_separator_api
    assert edit_mode_result == {"FINISHED"}, state.last_status_json
    assert first.mode == "OBJECT" and second.mode == "OBJECT"

    result = bpy.ops.alpha_material_separator.analyze(
        api_major=1,
        alpha_threshold=0.999,
        min_affected_texels=1,
        min_affected_fraction=0.0,
        margin_texels=0,
    )
    assert result == {"FINISHED"}, result
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

    safe = _quad("AMS_ANALYSIS_SAFE_PREVIEW", material)
    safe.select_set(True)
    first.select_set(True)
    shared.select_set(True)
    bpy.context.view_layer.objects.active = safe
    safe_analysis = bpy.ops.alpha_material_separator.analyze()
    assert safe_analysis == {"FINISHED"}, safe_analysis
    safe_report = runtime.report(state.analysis_id)
    safe_plan = build_assignment_plan(
        safe_report,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    )
    assert len(safe_plan.skipped_objects) == 2, safe_plan.public_payload()
    safe_preview = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        preview_assignment_plan=True,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert safe_preview == {"FINISHED"}, state.last_status_json
    assert safe.mode == "EDIT"
    assert first.mode == "OBJECT" and shared.mode == "OBJECT"
    assert not first.select_get() and not shared.select_get()
    bpy.ops.object.mode_set(mode="OBJECT")
    print("ALPHA_MATERIAL_SEPARATOR_ANALYSIS_PREVIEW_TESTS_OK")
