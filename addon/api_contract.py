# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, JSON-compatible public integration contract."""

from __future__ import annotations

import json
from typing import Any

API_VERSION = (1, 0)
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

GUARANTEED_MATERIAL_PATTERNS = (
    "DIRECT_IMAGE_ALPHA_TO_ACTIVE_PRINCIPLED_ALPHA",
    "EXPLICIT_IMAGE_AND_UV_OVERRIDE",
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
            "analysis": False,
            "face_selection_preview": False,
            "material_assignment": False,
            "material_support_matrix_ready": False,
            "query_capabilities": True,
        },
        "classifications": list(CLASSIFICATIONS),
        "extension_version": dotted(EXTENSION_VERSION),
        "guaranteed_material_patterns": list(GUARANTEED_MATERIAL_PATTERNS),
        "operator_ids": list(PUBLIC_OPERATOR_IDS),
        "supported_blender": {"minimum": "5.2.0"},
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
