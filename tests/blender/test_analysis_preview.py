# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless Blender analysis, resolver, stale-check, and preview tests."""

from __future__ import annotations

import json
from array import array

import bmesh
import bpy

from addon import runtime
from addon.adapters import analysis as analysis_module
from addon.adapters import image_data
from addon.adapters.analysis import (
    AnalysisConfig,
    AnalysisEngine,
)
from addon.adapters.assignment import build_assignment_plan
from addon.adapters.image_data import ImageReadError, read_image_snapshot
from addon.adapters.material_resolver import resolve_material
from addon.core import FaceClass
from addon.operators import analyze as analyze_operator


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


def _polygon_strip(name: str, count: int):
    vertices = []
    faces = []
    for index in range(count):
        offset = len(vertices)
        x = float(index)
        vertices.extend(
            ((x, 0.0, 0.0), (x + 0.5, 0.0, 0.0), (x, 0.5, 0.0))
        )
        faces.append((offset, offset + 1, offset + 2))
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, (), faces)
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    return object_


def _preview_component_object(name: str):
    image = bpy.data.images.new(f"{name}_IMAGE", width=2, height=1, alpha=True)
    image.pixels.foreach_set(
        (1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0)
    )
    material, _tree, _principled, _texture = _material(
        f"{name}_MATERIAL",
        image,
    )
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(
        (
            (0, 0, 0),
            (1, 0, 0),
            (2, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (2, 1, 0),
            (3, 0, 0),
            (4, 0, 0),
            (3, 1, 0),
            (4, 1, 0),
        ),
        (),
        ((0, 1, 4, 3), (1, 2, 5, 4), (6, 7, 9, 8)),
    )
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    coordinates = (
        ((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)),
        ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)),
        ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)),
    )
    modern = getattr(uv_layer, "uv", None)
    for polygon in mesh.polygons:
        for offset, loop_index in enumerate(polygon.loop_indices):
            value = coordinates[polygon.index][offset]
            if modern is not None:
                modern[loop_index].vector = value
            else:
                uv_layer.data[loop_index].uv = value
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    return object_


def _seed_component_selection(object_, selected_faces) -> None:
    for vertex in object_.data.vertices:
        vertex.select = True
    for edge in object_.data.edges:
        edge.select = True
    for polygon in object_.data.polygons:
        polygon.select = polygon.index in selected_faces
    object_.data.update()


def _component_selection(object_):
    return (
        tuple(vertex.select for vertex in object_.data.vertices),
        tuple(edge.select for edge in object_.data.edges),
    )


def _assert_face_derived_component_selection(object_, expected_faces) -> None:
    edit_mesh = bmesh.from_edit_mesh(object_.data)
    selected_faces = {face.index for face in edit_mesh.faces if face.select}
    assert selected_faces == set(expected_faces), selected_faces
    assert all(
        any(face.select for face in edge.link_faces)
        for edge in edit_mesh.edges
        if edge.select
    ), "selected edge belongs only to unselected faces"
    assert all(
        any(face.select for face in vertex.link_faces)
        for vertex in edit_mesh.verts
        if vertex.select
    ), "selected vertex belongs only to unselected faces"


def _preview_component_selection_test() -> None:
    _clear_scene()
    first = _preview_component_object("AMS_PREVIEW_COMPONENT_A")
    second = _preview_component_object("AMS_PREVIEW_COMPONENT_B")
    bpy.context.view_layer.objects.active = first
    analyzed = bpy.ops.alpha_material_separator.analyze()
    state = bpy.context.window_manager.alpha_material_separator_api
    assert analyzed == {"FINISHED"}, state.last_status_json
    payload = json.loads(state.report_json)
    assert payload["counts"]["ALPHA_AFFECTED"] == 2, payload
    assert payload["counts"]["OPAQUE"] == 4, payload
    for object_ in (first, second):
        _seed_component_selection(object_, {0, 1, 2})

    preview_arguments = {
        "expected_analysis_id": state.analysis_id,
        "preview_assignment_plan": True,
        "mixed_policy": "TO_ALPHA",
        "suppressed_policy": "CANCEL_SOURCE_MATERIAL",
        "unsupported_policy": "TO_ALPHA",
        "derived_conflict_policy": "CANCEL_SOURCE_MATERIAL",
        "selection_mode": "REPLACE",
        "enter_edit_mode": True,
    }
    previewed = bpy.ops.alpha_material_separator.select_faces(**preview_arguments)
    assert previewed == {"FINISHED"}, state.last_status_json
    _assert_face_derived_component_selection(first, {0})
    _assert_face_derived_component_selection(second, {0})
    ui = bpy.context.window_manager.alpha_material_separator_ui
    reviewed = (ui.reviewed_analysis_id, ui.reviewed_policy_signature)
    repeated = bpy.ops.alpha_material_separator.select_faces(**preview_arguments)
    assert repeated == {"FINISHED"}, state.last_status_json
    assert state.analysis_id == preview_arguments["expected_analysis_id"]
    assert reviewed == (ui.reviewed_analysis_id, ui.reviewed_policy_signature)
    _assert_face_derived_component_selection(first, {0})
    _assert_face_derived_component_selection(second, {0})
    bpy.ops.object.mode_set(mode="OBJECT")

    for selection_mode, initially_selected, expected_faces in (
        ("REPLACE", {0, 1, 2}, {0}),
        ("ADD", {1}, {0, 1}),
        ("SUBTRACT", {0, 1, 2}, {1, 2}),
    ):
        _clear_scene()
        object_ = _preview_component_object(
            f"AMS_PREVIEW_COMPONENT_{selection_mode}"
        )
        bpy.context.view_layer.objects.active = object_
        analyzed = bpy.ops.alpha_material_separator.analyze()
        assert analyzed == {"FINISHED"}, state.last_status_json
        _seed_component_selection(object_, initially_selected)
        previewed = bpy.ops.alpha_material_separator.select_faces(
            expected_analysis_id=state.analysis_id,
            classes={"ALPHA_AFFECTED"},
            selection_mode=selection_mode,
            enter_edit_mode=True,
        )
        assert previewed == {"FINISHED"}, state.last_status_json
        _assert_face_derived_component_selection(object_, expected_faces)
        bpy.ops.object.mode_set(mode="OBJECT")

    _clear_scene()
    object_ = _preview_component_object("AMS_PREVIEW_COMPONENT_OBJECT_MODE")
    bpy.context.view_layer.objects.active = object_
    analyzed = bpy.ops.alpha_material_separator.analyze()
    assert analyzed == {"FINISHED"}, state.last_status_json
    _seed_component_selection(object_, {1})
    components_before = _component_selection(object_)
    previewed = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        classes={"ALPHA_AFFECTED"},
        selection_mode="REPLACE",
        enter_edit_mode=False,
    )
    assert previewed == {"FINISHED"}, state.last_status_json
    assert _component_selection(object_) == components_before


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


class _Pixels:
    def __init__(self, values, *, reject_slices=False, reject_bulk=False):
        self.values = tuple(array("f", values))
        self.reject_slices = reject_slices
        self.reject_bulk = reject_bulk
        self.bulk_reads = 0
        self.slice_reads = 0

    def __len__(self):
        return len(self.values)

    def __getitem__(self, item):
        self.slice_reads += 1
        if self.reject_slices:
            raise AssertionError("chunked pixel access was used")
        return self.values[item]

    def foreach_get(self, destination):
        self.bulk_reads += 1
        if self.reject_bulk:
            raise RuntimeError("bulk pixel access unavailable")
        destination[:] = array("f", self.values)


class _Image:
    def __init__(
        self,
        values,
        component_count,
        *,
        size=(2, 1),
        **pixel_options,
    ):
        self.size = size
        self.pixels = _Pixels(values, **pixel_options)
        self.component_count = component_count


def _bulk_image_reader_tests() -> None:
    assert hasattr(
        image_data, "MAX_BULK_WORKING_BYTES"
    ), "bounded native bulk image reader is missing"
    original_limit = image_data.MAX_BULK_WORKING_BYTES
    try:
        for component_count in (1, 2, 3, 4):
            values = tuple(
                (index + 1) / 10
                for index in range(2 * component_count)
            )
            channels = ["ALPHA", "RED"]
            if component_count >= 2:
                channels.append("GREEN")
            if component_count >= 3:
                channels.extend(("BLUE", "LUMINANCE"))
            for channel in channels:
                image_data.MAX_BULK_WORKING_BYTES = original_limit
                bulk_image = _Image(
                    values,
                    component_count,
                    reject_slices=True,
                )
                bulk = read_image_snapshot(
                    bulk_image,
                    channel=channel,
                    threshold=0.5,
                )
                assert bulk_image.pixels.bulk_reads == 1
                assert bulk_image.pixels.slice_reads == 0

                image_data.MAX_BULK_WORKING_BYTES = 0
                chunked_image = _Image(
                    values,
                    component_count,
                    reject_bulk=True,
                )
                chunked = read_image_snapshot(
                    chunked_image,
                    channel=channel,
                    threshold=0.5,
                )
                assert chunked_image.pixels.bulk_reads == 0
                assert chunked_image.pixels.slice_reads > 0
                assert bulk.digest == chunked.digest, (
                    component_count,
                    channel,
                    bulk.digest,
                    chunked.digest,
                )
                assert bulk.grid.affected == chunked.grid.affected, (
                    component_count,
                    channel,
                )

        image_data.MAX_BULK_WORKING_BYTES = original_limit
        fallback_image = _Image(
            (1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0),
            4,
            reject_bulk=True,
        )
        fallback = read_image_snapshot(
            fallback_image,
            channel="ALPHA",
            threshold=0.999,
        )
        assert fallback_image.pixels.bulk_reads == 1
        assert fallback_image.pixels.slice_reads > 0
        assert fallback.grid.affected == b"\x01\x00"

        invalid_image = _Image((1.0, float("nan")), 1)
        try:
            read_image_snapshot(
                invalid_image,
                channel="RED",
                threshold=0.999,
            )
        except ImageReadError:
            pass
        else:
            raise AssertionError("bulk reader accepted a non-finite channel value")

        texel_count = 131_073
        values = array("f")
        for index in range(texel_count):
            values.extend((0.25, 0.5, 0.75, 0.0 if index % 2 else 1.0))
        image = _Image(
            values,
            4,
            size=(texel_count, 1),
            reject_slices=True,
        )
        builder = image_data.ImageSnapshotBuilder(
            image,
            channel="ALPHA",
            threshold=0.999,
        )
        step_sizes = []
        while not builder.complete:
            before = builder.destination
            builder.step()
            step_sizes.append(builder.destination - before)
        assert step_sizes == [65_536, 65_536, 1], step_sizes
        assert image.pixels.bulk_reads == 1
        assert image.pixels.slice_reads == 0
        assert builder._bulk_pixels is None
        snapshot = builder.finish()
        assert len(snapshot.grid.affected) == texel_count

        boundary_values = array("f", [1.0]) * 65_537
        boundary_values[65_536] = float("nan")
        boundary = image_data.ImageSnapshotBuilder(
            _Image(boundary_values, 1, size=(65_537, 1)),
            channel="RED",
            threshold=0.999,
        )
        boundary.step()
        try:
            boundary.step()
        except ImageReadError:
            pass
        else:
            raise AssertionError("chunk-boundary NaN was accepted")
        assert boundary._bulk_pixels is None

        cancelled = image_data.ImageSnapshotBuilder(
            _Image(array("f", [1.0]) * 65_537, 1, size=(65_537, 1)),
            channel="RED",
            threshold=0.999,
        )
        cancelled.step()
        assert cancelled._bulk_pixels is not None
        cancelled.close()
        assert cancelled._bulk_pixels is None
    finally:
        if hasattr(image_data, "MAX_BULK_WORKING_BYTES"):
            image_data.MAX_BULK_WORKING_BYTES = original_limit


def _single_preparation_pass_test(*objects) -> None:
    calls = 0
    uv_passes = 0
    original_prepare = analysis_module._prepare
    original_uv_values = analysis_module._uv_values

    def counted_prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_prepare(*args, **kwargs)

    def counted_uv_values(layer):
        nonlocal uv_passes
        uv_passes += 1
        yield from original_uv_values(layer)

    analysis_module._prepare = counted_prepare
    analysis_module._uv_values = counted_uv_values
    try:
        engine = AnalysisEngine(objects, AnalysisConfig(), defer_images=True)
        while not engine.step(32):
            pass
        engine.finish()
    finally:
        analysis_module._prepare = original_prepare
        analysis_module._uv_values = original_uv_values
    assert calls == 1, f"modal analysis prepared the same inputs {calls} times"
    expected_uv_passes = sum(len(object_.data.uv_layers) for object_ in objects)
    assert uv_passes == expected_uv_passes, (
        f"modal analysis traversed UV layers {uv_passes} times; "
        f"expected {expected_uv_passes}"
    )

    fingerprint_calls = {}
    original_fingerprint = analysis_module.material_fingerprint

    def counted_fingerprint(material):
        pointer = material.as_pointer()
        fingerprint_calls[pointer] = fingerprint_calls.get(pointer, 0) + 1
        return original_fingerprint(material)

    analysis_module.material_fingerprint = counted_fingerprint
    try:
        analysis_module._assignment_signature(objects)
    finally:
        analysis_module.material_fingerprint = original_fingerprint
    assert max(fingerprint_calls.values(), default=0) == 1, fingerprint_calls


def _analysis_cadence_tests() -> None:
    timed_object = _polygon_strip("AMS_TIMED_ENGINE", 5)
    timed = AnalysisEngine((timed_object,), AnalysisConfig())
    analyzed = []
    timed._analyze_polygon = (
        lambda _prepared, polygon: analyzed.append(polygon.index)
    )
    ticks = iter((0.0, 0.004, 0.008, 0.012))
    assert not timed.step(
        4_096,
        time_budget_seconds=0.010,
        clock=lambda: next(ticks),
    )
    assert analyzed == [0, 1, 2], analyzed

    capped_object = _polygon_strip("AMS_CAPPED_ENGINE", 4_100)
    capped = AnalysisEngine((capped_object,), AnalysisConfig())
    capped_count = 0

    def count_polygon(_prepared, _polygon):
        nonlocal capped_count
        capped_count += 1

    capped._analyze_polygon = count_polygon
    assert not capped.step(4_096)
    assert capped_count == 4_096

    synchronous = AnalysisEngine((timed_object,), AnalysisConfig())
    synchronous._analyze_polygon = lambda _prepared, _polygon: None
    assert synchronous.step(
        5,
        clock=lambda: (_ for _ in ()).throw(
            AssertionError("clock used without a time budget")
        ),
    )


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
    _bulk_image_reader_tests()
    _out_of_range_uv_test()
    _preview_component_selection_test()
    _clear_scene()
    _analysis_cadence_tests()
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

    _single_preparation_pass_test(first, second)
    before = (_mesh_snapshot(first), _mesh_snapshot(second))
    deferred = AnalysisEngine((first, second), AnalysisConfig(), defer_images=True)
    assert deferred.completed == 0
    assert deferred.stage == "Reading Textures"
    while deferred.stage == "Reading Textures":
        assert deferred.step(1) is False
    assert deferred.stage == "Analyzing Faces"
    assert deferred.completed > 0
    deferred.cancel()
    assert all(builder._bulk_pixels is None for builder in deferred._image_builders)
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

    stages = []
    original_update_analysis = runtime.update_analysis

    def record_progress(window_manager, completed, total, stage, **kwargs):
        stages.append((stage, kwargs.get("show_progress", True)))
        return original_update_analysis(
            window_manager,
            completed,
            total,
            stage,
            **kwargs,
        )

    runtime.update_analysis = record_progress
    try:
        result = bpy.ops.alpha_material_separator.analyze(
            api_major=1,
            alpha_threshold=0.999,
            min_affected_texels=1,
            min_affected_fraction=0.0,
            margin_texels=0,
        )
    finally:
        runtime.update_analysis = original_update_analysis
    assert result == {"FINISHED"}, result
    assert ("Validating Inputs", False) in stages, stages
    assert stages[-1] == ("Analysis Complete", True), stages
    assert analyze_operator.MODAL_TIMER_SECONDS == 0.001
    assert analyze_operator.MODAL_FACE_TIME_BUDGET_SECONDS == 0.012
    assert analyze_operator.MODAL_POLYGON_BUDGET == 4_096
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
    _seed_component_selection(first, {0})
    skipped_components_before = _component_selection(first)
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
    assert _component_selection(first) == skipped_components_before
    bpy.ops.object.mode_set(mode="OBJECT")
    print("ALPHA_MATERIAL_SEPARATOR_ANALYSIS_PREVIEW_TESTS_OK")
