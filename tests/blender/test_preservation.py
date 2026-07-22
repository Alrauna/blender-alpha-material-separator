# SPDX-License-Identifier: GPL-3.0-or-later
"""Preservation acceptance test for rigged and attributed base meshes."""

from __future__ import annotations

import bpy

from addon.adapters.fingerprints import material_fingerprint
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad
from tests.blender.test_assignment import _analyze, _assign, _select_only


def _all_uvs(mesh):
    values = []
    for layer in mesh.uv_layers:
        modern = getattr(layer, "uv", None)
        for item in modern if modern is not None else layer.data:
            values.append(tuple(item.vector if modern is not None else item.uv))
    return tuple(values)


def _preserved_snapshot(object_):
    mesh = object_.data
    return {
        "vertices": tuple(tuple(vertex.co) for vertex in mesh.vertices),
        "edges": tuple(tuple(edge.vertices) for edge in mesh.edges),
        "loops": tuple(loop.vertex_index for loop in mesh.loops),
        "polygon_ranges": tuple(
            (polygon.loop_start, polygon.loop_total) for polygon in mesh.polygons
        ),
        "uvs": _all_uvs(mesh),
        "shape_keys": tuple(
            tuple(tuple(point.co) for point in key.data)
            for key in (mesh.shape_keys.key_blocks if mesh.shape_keys else ())
        ),
        "vertex_groups": tuple(
            tuple((membership.group, membership.weight) for membership in vertex.groups)
            for vertex in mesh.vertices
        ),
        "attributes": tuple(
            (
                attribute.name,
                attribute.data_type,
                attribute.domain,
                tuple(getattr(item, "value", None) for item in attribute.data),
            )
            for attribute in mesh.attributes
            if not attribute.is_internal and attribute.name != "material_index"
        ),
        "modifiers": tuple(
            (modifier.type, modifier.name, modifier.show_viewport)
            for modifier in object_.modifiers
        ),
        "parent": object_.parent.as_pointer() if object_.parent else 0,
        "parent_type": object_.parent_type,
    }


def _full_unselected_snapshot(object_):
    return {
        "preserved": _preserved_snapshot(object_),
        "materials": tuple(slot.material.as_pointer() for slot in object_.material_slots),
        "material_indices": tuple(
            polygon.material_index for polygon in object_.data.polygons
        ),
    }


def _assert_preserved(before, after):
    differences = {
        key: (before[key], after[key])
        for key in before
        if before[key] != after[key]
    }
    assert not differences, differences


def run() -> None:
    _clear_scene()
    image = _image("AMS_PRESERVE_IMAGE")
    source, _tree, _principled, _texture = _material("AMS_PRESERVE_SOURCE", image)
    object_ = _quad("AMS_PRESERVE_OBJECT", source)
    unselected = _quad("AMS_PRESERVE_UNSELECTED", source)

    group = object_.vertex_groups.new(name="AMS_WEIGHT")
    group.add([0, 1], 0.75, "REPLACE")
    object_.shape_key_add(name="Basis")
    shape = object_.shape_key_add(name="AMS_SHAPE")
    shape.data[0].co.z = 0.25
    attribute = object_.data.attributes.new("AMS_ATTRIBUTE", "FLOAT", "POINT")
    attribute.data.foreach_set("value", (0.1, 0.2, 0.3, 0.4))

    armature_data = bpy.data.armatures.new("AMS_PRESERVE_ARMATURE_DATA")
    armature = bpy.data.objects.new("AMS_PRESERVE_ARMATURE", armature_data)
    bpy.context.collection.objects.link(armature)
    _select_only(armature)
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armature_data.edit_bones.new("AMS_BONE")
    bone.head = (0.0, 0.0, 0.0)
    bone.tail = (0.0, 0.0, 1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    object_.parent = armature
    modifier = object_.modifiers.new("AMS_ARMATURE_MODIFIER", "ARMATURE")
    modifier.object = armature

    _select_only(object_)
    before = _preserved_snapshot(object_)
    unselected_before = _full_unselected_snapshot(unselected)
    source_before = material_fingerprint(source)
    image_before = tuple(image.pixels)
    armature_before = tuple(
        (bone.name, tuple(bone.head_local), tuple(bone.tail_local))
        for bone in armature_data.bones
    )

    analysis_id = _analyze(object_)
    _assert_preserved(before, _preserved_snapshot(object_))
    assigned, state = _assign(analysis_id)
    assert assigned == {"FINISHED"}, state.last_status_json

    _assert_preserved(before, _preserved_snapshot(object_))
    assert unselected_before == _full_unselected_snapshot(unselected)
    assert source_before == material_fingerprint(source)
    assert image_before == tuple(image.pixels)
    assert armature_before == tuple(
        (bone.name, tuple(bone.head_local), tuple(bone.tail_local))
        for bone in armature_data.bones
    )
    print("ALPHA_MATERIAL_SEPARATOR_PRESERVATION_TESTS_OK")
