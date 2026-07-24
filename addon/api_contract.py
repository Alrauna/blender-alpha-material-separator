# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, JSON-compatible public integration contract."""

from __future__ import annotations

import json
from typing import Any

API_VERSION = (1, 2)
EXTENSION_VERSION = (0, 1, 0)

PUBLIC_OPERATOR_IDS = (
    "alpha_material_separator.query_capabilities",
    "alpha_material_separator.analyze",
    "alpha_material_separator.select_faces",
    "alpha_material_separator.assign_materials",
    "alpha_material_separator.clear_results",
)

CLASSIFICATIONS = (
    "OPAQUE",
    "ALPHA_AFFECTED",
    "MIXED",
    "SUPPRESSED",
    "UNSUPPORTED",
)

ADDRESS_MODES = ("REPEAT", "EXTEND", "CLIP", "MIRROR")
UNSUPPORTED_SCOPES = ("FACE_LOCAL", "MATERIAL_SOURCE", "DATA_SAFETY")
UNSUPPORTED_POLICIES = ("CANCEL_SOURCE_MATERIAL", "KEEP_SOURCE", "TO_ALPHA")
VALIDATION_STATES = ("CLEAN", "RECHECK_PENDING", "STALE")

GUARANTEED_MATERIAL_PATTERNS = (
    "DIRECT_IMAGE_ALPHA_TO_ACTIVE_PRINCIPLED_ALPHA",
    "EXPLICIT_IMAGE_UV_AND_CHANNEL_OVERRIDE",
    "ACTIVE_RENDER_UV_FOR_UNLINKED_IMAGE_VECTOR",
    "DIRECT_UV_MAP_NODE",
    "DIRECT_TEXTURE_COORDINATE_UV",
    "SIMPLE_REROUTE_IN_ALPHA_PATH",
    "UNIQUE_BASE_COLOR_IMAGE_STORED_ALPHA",
)


def dotted(version: tuple[int, ...]) -> str:
    """Return a deterministic dotted version string."""
    return ".".join(str(part) for part in version)


def capability_payload() -> dict[str, Any]:
    """Describe the currently implemented checkpoint capabilities.

    Capabilities remain false until their implementation milestone is complete;
    operator IDs are reserved here so future callers can feature-detect instead
    of importing private modules.
    """
    return {
        "address_modes": list(ADDRESS_MODES),
        "api_version": dotted(API_VERSION),
        "capabilities": {
            "analysis": True,
            "component_revalidation": True,
            "explicit_channel_override": True,
            "face_selection_preview": True,
            "material_assignment": True,
            "per_material_overrides": True,
            "partial_material_assignment": True,
            "plan_derived_preview": True,
            "material_support_matrix_ready": True,
            "query_capabilities": True,
            "reason_scoped_unsupported": True,
        },
        "classifications": list(CLASSIFICATIONS),
        "extension_version": dotted(EXTENSION_VERSION),
        "guaranteed_material_patterns": list(GUARANTEED_MATERIAL_PATTERNS),
        "operator_ids": list(PUBLIC_OPERATOR_IDS),
        "supported_material_patterns": list(GUARANTEED_MATERIAL_PATTERNS),
        "supported_blender": {"minimum": "5.2.0"},
        "unsupported_policies": list(UNSUPPORTED_POLICIES),
        "unsupported_scopes": list(UNSUPPORTED_SCOPES),
        "validation_states": list(VALIDATION_STATES),
    }


def status_payload(code: str, message: str, **details: Any) -> dict[str, Any]:
    """Create a stable public status object."""
    payload: dict[str, Any] = {
        "api_version": dotted(API_VERSION),
        "code": code,
        "message": message,
    }
    payload.update(details)
    return payload


def dumps(payload: dict[str, Any]) -> str:
    """Serialize public payloads deterministically."""
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
