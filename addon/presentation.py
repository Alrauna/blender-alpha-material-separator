# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure presentation rules shared by Blender UI and ordinary tests."""

from __future__ import annotations

import hashlib
import json

CLASS_COPY = {
    "OPAQUE": ("Stay on opaque material", "No covered image pixel is below the threshold."),
    "ALPHA_AFFECTED": ("Move to alpha material", "Every covered image pixel needs alpha."),
    "MIXED": (
        "Mixed—must use alpha without cutting geometry",
        "This face covers opaque and alpha pixels, so it cannot be split without changing topology.",
    ),
    "SUPPRESSED": (
        "Below significance—needs review",
        "Alpha evidence exists but is below the configured minimum.",
    ),
    "UNSUPPORTED": (
        "Could not analyze",
        "The extension could not produce a trustworthy result.",
    ),
}

_GUIDANCE = {
    "NO_ELIGIBLE_OBJECTS": ("No mesh objects selected", "Select one or more Mesh objects in Object Mode."),
    "MATERIAL_HAS_NO_NODE_TREE": ("Material has no supported nodes", "Use an explicit image override or add a supported Principled material path."),
    "NO_ACTIVE_PRINCIPLED_OUTPUT": ("No active Principled output", "Choose an explicit image override for this material."),
    "NO_AUTHORITATIVE_ALPHA_IMAGE": ("No clear alpha image was found", "Set a manual alpha source for this material."),
    "UNSUPPORTED_ALPHA_PATH": ("Alpha uses unsupported shader processing", "Bake the final mask to an image and set it as the manual source."),
    "COLOR_TO_ALPHA_REQUIRES_OVERRIDE": ("Alpha comes from an image color channel", "Set that image and choose its Red, Green, Blue, Alpha, or Luminance channel."),
    "IMAGE_MISSING": ("Image node has no image", "Load or select the intended image, then analyze again."),
    "IMAGE_OVERRIDE_NOT_FOUND": ("Override image is unavailable", "Choose an image that exists in the current Blender file."),
    "IMAGE_HAS_NO_PIXELS": ("Image has no readable pixels", "Reload or replace the image, then analyze again."),
    "UNSUPPORTED_IMAGE_SOURCE": ("Image type is not supported", "Use a static file, packed image, or generated image."),
    "NO_ACTIVE_RENDER_UV": ("No active render UV map", "Choose the intended UV map in Expert mode or mark one as active for rendering."),
    "UV_MAP_NOT_FOUND": ("Material UV map is missing", "Correct the material's UV Map node or set a manual UV map."),
    "UV_OVERRIDE_NOT_FOUND": ("Override UV map is missing", "Choose a UV map that exists on every affected mesh."),
    "UNSUPPORTED_VECTOR_PATH": ("Texture coordinates are not a supported UV path", "Choose a raw UV map manually or bake the mapped result."),
    "UNSUPPORTED_PROJECTION": ("Image projection is not Flat", "Use a flat UV image source or bake the projected result."),
    "MULTI_USER_MESH": ("Mesh data is shared by multiple objects", "Make a deliberate single-user copy before using material assignment."),
    "LINKED_MESH": ("Mesh comes from a linked library", "Use a local editable copy; the extension never localizes data automatically."),
    "READ_ONLY_MESH": ("Mesh is read-only", "Use an editable local mesh."),
    "OVERRIDE_RESTRICTED_MESH": ("Library override cannot be edited safely", "Use an editable local copy or adjust the library override manually."),
    "MATERIAL_SLOT_EMPTY": ("A face uses an empty material slot", "Assign a material to the slot, then analyze again."),
    "MATERIAL_UNRESOLVED": ("A face material could not be resolved", "Assign a supported material or set a manual alpha source."),
    "IMAGE_SNAPSHOT_MISSING": ("Image pixels were not available", "Reload the image and analyze again."),
    "INVALID_UV": ("UV coordinates are invalid", "Repair non-finite or malformed UV coordinates."),
    "UV_TRIANGLES_UNAVAILABLE": ("Face UV triangles are unavailable", "Check the mesh and UV map for invalid geometry."),
    "NO_POSITIVE_AREA_UV_COVERAGE": ("Face has no positive UV area", "Fix collapsed or degenerate UVs for this face."),
    "SUPPRESSED_FACES": ("Alpha evidence is below the significance setting", "Review the affected material group or change its Expert policy deliberately."),
    "UNSUPPORTED_FACES": ("Some faces could not be analyzed", "Resolve the listed material source before applying this material group."),
    "MIXED_FACES": ("Mixed faces are blocked by policy", "Move mixed faces to alpha or keep them on the source after review."),
    "SOURCE_CHANGED": ("Source material changed", "Analyze again and explicitly choose whether to reuse or create a new alpha variant."),
    "DERIVED_CHANGED": ("Alpha material was edited", "Choose whether to reuse it or preserve it and create a new variant."),
    "DUPLICATED_DERIVED": ("Alpha material metadata was duplicated", "Resolve the duplicate deliberately or create a fresh variant."),
    "METADATA_CONFLICT": ("Alpha material metadata is ambiguous", "Preserve the materials and resolve the conflict manually."),
    "SOURCE_METADATA_CONFLICT": ("Source material contains conflicting extension metadata", "Remove or repair the conflicting metadata before assignment."),
    "SOURCE_POINTER_LOST": ("Alpha material lost its source reference", "Treat it as an orphan and create a new reviewed variant from the real source."),
    "POINTER_WITHOUT_METADATA": ("Material has an unexplained source pointer", "Preserve the material and remove or repair the conflicting metadata manually."),
    "UNKNOWN_METADATA_KEYS": ("Material has unknown extension metadata", "Preserve the material and resolve the custom properties manually."),
    "UNKNOWN_METADATA_SCHEMA": ("Material metadata is from an unknown schema", "Do not reuse it automatically; preserve or replace it deliberately."),
    "UNKNOWN_METADATA_ROLE": ("Material metadata has an unknown role", "Preserve the material and resolve the custom properties manually."),
    "INVALID_METADATA_UUID": ("Material identity metadata is invalid", "Preserve the material and create a fresh reviewed variant."),
    "INVALID_METADATA_FINGERPRINT": ("Material fingerprint metadata is invalid", "Preserve the material and create a fresh reviewed variant."),
    "SOURCE_NOT_IN_ANALYZED_SLOTS": ("Derived material source is not present", "Restore the source material to an analyzed slot before rerunning."),
    "MULTIPLE_DERIVED_MATCHES": ("Several alpha materials match the source", "Choose one deliberately or create a fresh variant."),
    "MULTIPLE_DERIVED_VARIANTS": ("Several changed alpha variants exist", "Choose a variant explicitly before applying."),
    "SOURCE_OR_DERIVED_CHANGED": ("Source or alpha material changed", "Choose whether to reuse the edited alpha material or create a fresh variant."),
    "DERIVED_CONFLICT": ("Alpha material identity is ambiguous", "Preserve the material and create a fresh variant."),
    "INPUT_DATABLOCK_UNAVAILABLE": ("An analyzed Blender datablock is unavailable", "Restore the object, mesh, material, image, or UV input and analyze again."),
    "INPUTS_CHANGED": ("Analyzed inputs changed", "Analyze again before previewing or applying."),
    "OBJECT_DELETED_OR_REPLACED": ("An analyzed object was deleted or replaced", "Select the current mesh objects and analyze again."),
    "STALE_ANALYSIS": ("Inputs changed after analysis", "Analyze again before previewing or applying."),
    "ANALYSIS_ID_MISMATCH": ("The reviewed result is unavailable", "Run Analyze Selected Meshes again."),
    "OVERRIDE_CONFLICT": ("Override styles cannot be combined", "Use either legacy selection-wide image override or per-material overrides, not both."),
    "INVALID_MATERIAL_OVERRIDES": ("Manual alpha-source settings are invalid", "Review the target material, image, channel, UV map, and addressing."),
    "DUPLICATE_MATERIAL_OVERRIDE": ("A material has more than one override", "Keep only one manual alpha-source record for that material."),
    "CHANNEL_REQUIRES_IMAGE_OVERRIDE": ("Image channel needs an explicit image", "Choose an image before selecting Red, Green, Blue, or Luminance."),
    "OVERRIDE_TARGET_NOT_SELECTED": ("Override material is not in the selection", "Select an object using that material or remove the unused override."),
    "ANALYSIS_ALREADY_RUNNING": ("Analysis is already running", "Wait for it to finish or use Cancel Analysis."),
    "ANALYSIS_CANCELLED": ("Analysis canceled", "No partial result was kept; any earlier completed report is still available."),
    "ANALYSIS_PREPARE_FAILED": ("Analysis could not start", "Review the selected meshes and manual sources, then try again."),
    "ANALYSIS_FAILED": ("Analysis did not complete", "Review Technical Details, correct the input, and analyze again."),
    "API_INCOMPATIBLE": ("This integration version is incompatible", "Update the calling script or use API major 1."),
    "NO_PREVIEW_OBJECTS": ("No safe objects are available to preview", "Resolve the skipped objects, then analyze again."),
    "ASSIGNMENT_BLOCKED": ("No safe material assignment is available", "Resolve the listed skipped material groups before applying."),
    "ASSIGNMENT_FAILED": ("Material separation did not complete", "Undo if needed, review Technical Details, and analyze again."),
}

KNOWN_GUIDANCE_CODES = frozenset(_GUIDANCE)


def guidance_for(reason: str | None) -> tuple[str, str]:
    """Return short user copy and a safe next action for an internal reason."""
    code = (reason or "").split(":", 1)[0]
    if code.startswith("BUDGET_"):
        return (
            "Analysis safety limit was reached",
            "Reduce the UV footprint or raise the matching Expert budget deliberately.",
        )
    if code == "IMAGE_READ_ERROR":
        return ("Image pixels could not be read", "Reload or replace the image, then analyze again.")
    return _GUIDANCE.get(
        code,
        ("This input needs review", "Open Technical Details, correct the input, and analyze again."),
    )


def classes_to_move(mixed_policy: str, suppressed_policy: str) -> tuple[str, ...]:
    classes = ["ALPHA_AFFECTED"]
    if mixed_policy == "TO_ALPHA":
        classes.append("MIXED")
    if suppressed_policy == "TO_ALPHA":
        classes.append("SUPPRESSED")
    return tuple(classes)


def review_signature(
    analysis_id: str,
    mixed_policy: str,
    suppressed_policy: str,
    unsupported_policy: str,
    conflict_policy: str,
) -> str:
    payload = json.dumps(
        [analysis_id, mixed_policy, suppressed_policy, unsupported_policy, conflict_policy],
        separators=(",", ":"),
    )
    return hashlib.blake2b(payload.encode("utf8"), digest_size=16).hexdigest()


def requires_confirmation(report: dict, plan: dict) -> bool:
    counts = report.get("counts", {})
    return bool(
        counts.get("MIXED", 0)
        or counts.get("SUPPRESSED", 0)
        or counts.get("UNSUPPORTED", 0)
        or report.get("skip_counts")
        or plan.get("blocked")
    )


def workflow_view(
    *,
    eligible_objects: int,
    running: bool,
    has_report: bool,
    stale: bool,
    reviewed: bool,
    actionable: bool,
    completed: bool,
) -> dict[str, object]:
    """Build a deterministic high-level state for UI and tests."""
    if running:
        state = "RUNNING"
    elif stale and has_report:
        state = "STALE"
    elif completed:
        state = "COMPLETED"
    elif has_report and not actionable:
        state = "NO_CHANGE"
    elif has_report and reviewed:
        state = "REVIEWED"
    elif has_report:
        state = "READY_TO_REVIEW"
    elif eligible_objects:
        state = "READY_TO_ANALYZE"
    else:
        state = "IDLE"
    return {
        "state": state,
        "can_analyze": not running and eligible_objects > 0,
        "can_preview": has_report and not running and not stale,
        "can_apply": has_report and reviewed and actionable and not running and not stale,
    }
