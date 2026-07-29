# SPDX-License-Identifier: GPL-3.0-or-later
"""Behavior contracts required before simplifying shared Blender state."""

from __future__ import annotations

import json

import bpy

from addon import runtime
from addon.core import FaceClass
from tests.blender.test_analysis_preview import _clear_scene, _image, _material, _quad


def _enum_ids(rna, name: str) -> tuple[str, ...]:
    return tuple(
        item.identifier for item in rna.properties[name].enum_items
    )


def _assert_policy_rna() -> None:
    common = {
        "mixed_policy": (
            ("TO_ALPHA", "KEEP_SOURCE", "CANCEL_SOURCE_MATERIAL"),
            "TO_ALPHA",
        ),
        "suppressed_policy": (
            ("CANCEL_SOURCE_MATERIAL", "TO_ALPHA", "KEEP_SOURCE"),
            "CANCEL_SOURCE_MATERIAL",
        ),
        "derived_conflict_policy": (
            ("CANCEL_SOURCE_MATERIAL", "REUSE_EXISTING", "CREATE_NEW_VARIANT"),
            "CANCEL_SOURCE_MATERIAL",
        ),
    }
    owners = (
        (
            bpy.context.window_manager.alpha_material_separator_settings.bl_rna,
            ("TO_ALPHA", "CANCEL_SOURCE_MATERIAL", "KEEP_SOURCE"),
            "TO_ALPHA",
        ),
        (
            bpy.ops.alpha_material_separator.select_faces.get_rna_type(),
            ("CANCEL_SOURCE_MATERIAL", "KEEP_SOURCE", "TO_ALPHA"),
            "CANCEL_SOURCE_MATERIAL",
        ),
        (
            bpy.ops.alpha_material_separator.assign_materials.get_rna_type(),
            ("CANCEL_SOURCE_MATERIAL", "KEEP_SOURCE", "TO_ALPHA"),
            "CANCEL_SOURCE_MATERIAL",
        ),
    )
    for rna, unsupported_ids, unsupported_default in owners:
        properties = common | {
            "unsupported_policy": (unsupported_ids, unsupported_default)
        }
        for name, (identifiers, default) in properties.items():
            assert _enum_ids(rna, name) == identifiers
            assert rna.properties[name].default == default


def _assert_legacy_analyze_arguments() -> None:
    properties = bpy.ops.alpha_material_separator.analyze.get_rna_type().properties
    for name in (
        "image_name",
        "uv_map_name",
        "image_channel",
        "address_mode",
        "material_overrides_json",
    ):
        assert properties.get(name) is not None, name
    settings_properties = (
        bpy.context.window_manager.alpha_material_separator_settings.bl_rna.properties
    )
    for name in ("image_override", "uv_map_name", "image_channel"):
        assert settings_properties.get(name) is None, name


def _assert_group_counts_match_face_indices() -> None:
    _clear_scene()
    image = _image("AMS_SIMPLIFICATION_IMAGE")
    material, _tree, _principled, _texture = _material(
        "AMS_SIMPLIFICATION_MATERIAL", image
    )
    object_ = _quad("AMS_SIMPLIFICATION_OBJECT", material)
    bpy.context.view_layer.objects.active = object_

    assert bpy.ops.alpha_material_separator.analyze() == {"FINISHED"}
    report = runtime.report()
    object_result = next(
        result for result in report.object_results.values() if result.object == object_
    )
    group = next(iter(object_result.groups.values()))
    for face_class in FaceClass:
        assert group.public_count(face_class) == len(group.face_indices[face_class])
    group_payload = json.loads(
        bpy.context.window_manager.alpha_material_separator_api.report_json
    )["objects"][0]["groups"][0]
    assert group_payload["counts"] == {
        "ALPHA_AFFECTED": 0,
        "MIXED": 1,
        "OPAQUE": 0,
        "SUPPRESSED": 0,
        "UNSUPPORTED": 0,
    }


def run() -> None:
    _assert_policy_rna()
    _assert_legacy_analyze_arguments()
    _assert_group_counts_match_face_indices()
    print("ALPHA_MATERIAL_SEPARATOR_SIMPLIFICATION_CONTRACTS_OK")
