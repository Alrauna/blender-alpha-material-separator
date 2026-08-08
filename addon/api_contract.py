# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned, JSON-compatible public integration contract."""

from __future__ import annotations

import json
from typing import Any

from .manifest import version_tuple as _manifest_version
from .overrides import ADDRESS_MODES as OVERRIDE_ADDRESS_MODES

API_VERSION = (1, 3)
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

# Published so a consumer does not reimplement the panel's private set by hand.
# Only non-error codes are listed; an unlisted code is an error, which keeps the
# world closed exactly as the panel's previous `normal` set did. There is no
# WARNING level because no current code needs one.
STATUS_SEVERITIES = {
    "NOT_QUERIED": "OK",
    "OK": "OK",
    "ANALYSIS_COMPLETE": "OK",
    "PREVIEW_COMPLETE": "OK",
    "ASSIGNMENT_COMPLETE": "OK",
    "ASSIGNMENT_NO_CHANGES": "OK",
    "CLEARED": "OK",
    "ASSIGNMENT_COMPLETE_WITH_SKIPS": "INFO",
    "RESULT_STALE": "INFO",
}
DEFAULT_STATUS_SEVERITY = "ERROR"


def severity_for(code: str) -> str:
    """Classify a public status code. Unknown codes are errors."""
    return STATUS_SEVERITIES.get(code, DEFAULT_STATUS_SEVERITY)


# The published guided-workflow surface. WORKFLOW_FIELDS is the exact key set of
# `WindowManager.alpha_material_separator_api.workflow_json` minus api_version,
# so a consumer can validate a payload without version-sniffing.
WORKFLOW_STATES = (
    "IDLE",
    "READY_TO_ANALYZE",
    "READY_TO_REVIEW",
    "REVIEWED",
    "NO_CHANGE",
    "STALE",
    "RUNNING",
    "COMPLETED",
)
WORKFLOW_FIELDS = (
    "state",
    "can_analyze",
    "can_preview",
    "can_apply",
    "running",
    "stale",
    "reviewed",
    "actionable",
    "already_separated",
    "eligible_object_count",
    "analysis_id",
    "validation_state",
    "expected_review_signature",
)

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
            "published_workflow_state": True,
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


def workflow_payload(view: dict[str, Any]) -> dict[str, Any]:
    """Project a live workflow snapshot onto the published field set.

    The snapshot the panel draws from also carries live Blender objects. Only
    the JSON-compatible fields listed in WORKFLOW_FIELDS are published.
    """
    payload: dict[str, Any] = {"api_version": dotted(API_VERSION)}
    payload.update({name: view[name] for name in WORKFLOW_FIELDS})
    return payload


def degraded_workflow_payload() -> dict[str, Any]:
    """Offer no operation when the live snapshot could not be computed.

    A get= callback runs during panel draw and must never raise, so an
    unexpected failure publishes a payload that gates every action off rather
    than an optimistic or absent one.
    """
    return workflow_payload(
        {
            "state": "STALE",
            "can_analyze": False,
            "can_preview": False,
            "can_apply": False,
            "running": False,
            "stale": True,
            "reviewed": False,
            "actionable": False,
            "already_separated": False,
            "eligible_object_count": 0,
            "analysis_id": "",
            "validation_state": "STALE",
            "expected_review_signature": "",
        }
    )


def status_payload(code: str, message: str, **details: Any) -> dict[str, Any]:
    """Create a stable public status object."""
    payload: dict[str, Any] = {
        "api_version": dotted(API_VERSION),
        "code": code,
        "message": message,
        "severity": severity_for(code),
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
