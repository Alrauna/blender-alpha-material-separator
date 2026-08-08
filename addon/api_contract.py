# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, JSON-compatible public integration contract."""

from __future__ import annotations

import json
from typing import Any

from .manifest import version_tuple as _manifest_version
from .overrides import ADDRESS_MODES as OVERRIDE_ADDRESS_MODES

API_VERSION = (1, 2)
# Derived so a release bumps blender_manifest.toml and nothing else.
EXTENSION_VERSION = _manifest_version()

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

# Public: these are analyze() keyword arguments. Renaming one inside API major 1
# breaks scripted callers silently, so the names are guarded here rather than in
# the panel module that happens to draw them.
ANALYSIS_SETTING_NAMES = (
    "alpha_threshold",
    "min_affected_texels",
    "min_affected_fraction",
    "margin_texels",
    "address_mode",
    "max_scanlines",
    "max_run_emissions",
)

# Published unfiltered: AUTO is parser-accepted, documented since API 1.2, and
# the default every override starts at. A resolved report never reports AUTO.
ADDRESS_MODES = OVERRIDE_ADDRESS_MODES
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


def publish_status(
    state, code: str, message: str, **details: Any
) -> dict[str, Any]:
    """Publish one status payload to Blender's duck-typed API state."""
    payload = status_payload(code, message, **details)
    state.last_status_code = code
    state.last_status_json = dumps(payload)
    return payload
