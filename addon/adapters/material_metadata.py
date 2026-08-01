# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe, derived-only material identity metadata and conflict detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import bpy

from ..api_contract import EXTENSION_VERSION, dotted
from .fingerprints import material_fingerprint

PREFIX = "alpha_material_separator."
SCHEMA_VERSION = PREFIX + "schema_version"
ROLE = PREFIX + "role"
VARIANT_UUID = PREFIX + "variant_uuid"
SOURCE_UUID_REF = PREFIX + "source_uuid_ref"
SOURCE_FINGERPRINT = PREFIX + "source_fingerprint"
DERIVED_FINGERPRINT = PREFIX + "derived_fingerprint_at_creation"
CREATED_BY_VERSION = PREFIX + "created_by_version"
SOURCE_NAME = PREFIX + "source_name_at_last_assignment"
POINTER_PROPERTY = "alpha_material_separator_source"
ROLE_ALPHA_VARIANT = "ALPHA_VARIANT"
CURRENT_SCHEMA = 1

ALLOWED_KEYS = {
    SCHEMA_VERSION,
    ROLE,
    VARIANT_UUID,
    SOURCE_UUID_REF,
    SOURCE_FINGERPRINT,
    DERIVED_FINGERPRINT,
    CREATED_BY_VERSION,
    SOURCE_NAME,
}


@dataclass(frozen=True, slots=True)
class MetadataState:
    kind: str
    reason: str = ""
    source: bpy.types.Material | None = None
    variant_uuid: str = ""
    source_uuid_ref: str = ""
    source_fingerprint: str = ""
    derived_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class DerivedDecision:
    action: str
    reason: str
    material: bpy.types.Material | None = None
    source_uuid_ref: str = ""


def _valid_uuid(value) -> bool:
    try:
        return str(uuid.UUID(str(value))) == str(value).lower()
    except (ValueError, TypeError, AttributeError):
        return False


def inspect_metadata(material: bpy.types.Material) -> MetadataState:
    keys = {key for key in material.keys() if key.startswith(PREFIX)}
    source = getattr(material, POINTER_PROPERTY, None)
    if not keys:
        if source is not None:
            return MetadataState("CONFLICT", "POINTER_WITHOUT_METADATA")
        return MetadataState("SOURCE")
    if keys - ALLOWED_KEYS:
        return MetadataState("CONFLICT", "UNKNOWN_METADATA_KEYS")
    if material.get(SCHEMA_VERSION) != CURRENT_SCHEMA:
        return MetadataState("CONFLICT", "UNKNOWN_METADATA_SCHEMA")
    if material.get(ROLE) != ROLE_ALPHA_VARIANT:
        return MetadataState("CONFLICT", "UNKNOWN_METADATA_ROLE")
    variant_uuid = material.get(VARIANT_UUID, "")
    source_uuid_ref = material.get(SOURCE_UUID_REF, "")
    if not _valid_uuid(variant_uuid) or not _valid_uuid(source_uuid_ref):
        return MetadataState("CONFLICT", "INVALID_METADATA_UUID")
    source_fingerprint_value = material.get(SOURCE_FINGERPRINT, "")
    derived_fingerprint = material.get(DERIVED_FINGERPRINT, "")
    if not isinstance(source_fingerprint_value, str) or not isinstance(
        derived_fingerprint, str
    ):
        return MetadataState("CONFLICT", "INVALID_METADATA_FINGERPRINT")
    if source is None:
        return MetadataState(
            "ORPHAN",
            "SOURCE_POINTER_LOST",
            variant_uuid=variant_uuid,
            source_uuid_ref=source_uuid_ref,
            source_fingerprint=source_fingerprint_value,
            derived_fingerprint=derived_fingerprint,
        )
    return MetadataState(
        "DERIVED",
        source=source,
        variant_uuid=variant_uuid,
        source_uuid_ref=source_uuid_ref,
        source_fingerprint=source_fingerprint_value,
        derived_fingerprint=derived_fingerprint,
    )


def _variants_for_source(source: bpy.types.Material):
    result = []
    conflicts = []
    for material in bpy.data.materials:
        if getattr(material, POINTER_PROPERTY, None) != source:
            continue
        state = inspect_metadata(material)
        if state.kind == "DERIVED":
            result.append((material, state))
        else:
            conflicts.append((material, state))
    return result, conflicts


def _duplicated_variant_uuids() -> set[str]:
    owners: dict[str, int] = {}
    duplicates = set()
    for material in bpy.data.materials:
        value = material.get(VARIANT_UUID)
        if not value:
            continue
        value = str(value)
        owners[value] = owners.get(value, 0) + 1
        if owners[value] > 1:
            duplicates.add(value)
    return duplicates


def resolve_derived_material(
    source: bpy.types.Material,
    current_source_fingerprint: str,
    *,
    conflict_policy: str,
) -> DerivedDecision:
    source_state = inspect_metadata(source)
    if source_state.kind != "SOURCE":
        return DerivedDecision("BLOCK", "SOURCE_METADATA_CONFLICT")
    variants, conflicts = _variants_for_source(source)
    if conflicts:
        return DerivedDecision("BLOCK", "METADATA_CONFLICT")
    if not variants:
        return DerivedDecision("CREATE", "DERIVED_NOT_FOUND")

    duplicates = _duplicated_variant_uuids()
    if any(state.variant_uuid in duplicates for _material, state in variants):
        if conflict_policy == "CREATE_NEW_VARIANT":
            return DerivedDecision(
                "CREATE",
                "DUPLICATED_DERIVED",
                source_uuid_ref=variants[0][1].source_uuid_ref,
            )
        return DerivedDecision("BLOCK", "DUPLICATED_DERIVED")

    exact = []
    changed = []
    for material, state in variants:
        if material.library is not None or not getattr(material, "is_editable", True):
            return DerivedDecision("BLOCK", "DERIVED_NOT_EDITABLE")
        source_matches = state.source_fingerprint == current_source_fingerprint
        derived_matches = material_fingerprint(material) == state.derived_fingerprint
        if source_matches and derived_matches:
            exact.append((material, state))
        else:
            changed.append((material, state, source_matches, derived_matches))
    if len(exact) == 1:
        return DerivedDecision(
            "REUSE", "EXACT_DERIVED_MATCH", exact[0][0], exact[0][1].source_uuid_ref
        )
    if len(exact) > 1:
        return DerivedDecision("BLOCK", "MULTIPLE_DERIVED_MATCHES")

    if conflict_policy == "CREATE_NEW_VARIANT":
        return DerivedDecision(
            "CREATE",
            "SOURCE_OR_DERIVED_CHANGED",
            source_uuid_ref=variants[0][1].source_uuid_ref,
        )
    if conflict_policy == "REUSE_EXISTING" and len(changed) == 1:
        material, state, source_matches, derived_matches = changed[0]
        if not source_matches:
            reason = "SOURCE_CHANGED"
        elif not derived_matches:
            reason = "DERIVED_CHANGED"
        else:
            reason = "DERIVED_CONFLICT"
        return DerivedDecision("REUSE", reason, material, state.source_uuid_ref)
    if len(changed) == 1:
        _material, _state, source_matches, derived_matches = changed[0]
        if not source_matches:
            return DerivedDecision("BLOCK", "SOURCE_CHANGED")
        if not derived_matches:
            return DerivedDecision("BLOCK", "DERIVED_CHANGED")
    return DerivedDecision("BLOCK", "MULTIPLE_DERIVED_VARIANTS")


def create_derived_material(
    source: bpy.types.Material,
    source_fingerprint_value: str,
    *,
    source_uuid_ref: str = "",
) -> bpy.types.Material:
    derived = None
    try:
        derived = source.copy()
        derived.name = f"{source.name}__AMS_ALPHA"
        setattr(derived, POINTER_PROPERTY, source)
        derived[SCHEMA_VERSION] = CURRENT_SCHEMA
        derived[ROLE] = ROLE_ALPHA_VARIANT
        derived[VARIANT_UUID] = str(uuid.uuid4())
        derived[SOURCE_UUID_REF] = source_uuid_ref or str(uuid.uuid4())
        derived[SOURCE_FINGERPRINT] = source_fingerprint_value
        derived[CREATED_BY_VERSION] = dotted(EXTENSION_VERSION)
        derived[SOURCE_NAME] = source.name
        derived[DERIVED_FINGERPRINT] = material_fingerprint(derived)
        return derived
    except Exception:
        if derived is not None:
            try:
                bpy.data.materials.remove(derived, do_unlink=True)
            except (ReferenceError, RuntimeError):
                pass
        raise


def refresh_diagnostic_name(derived: bpy.types.Material, source: bpy.types.Material) -> None:
    derived[SOURCE_NAME] = source.name
