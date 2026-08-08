# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure presentation rules shared by Blender UI and ordinary tests."""

from __future__ import annotations

import hashlib
import json
import textwrap

_UI_AVERAGE_CHARACTER_WIDTH = 7
_UI_HORIZONTAL_PADDING = 32
_UI_MIN_LINE_CHARACTERS = 12


def json_object(value: str) -> dict:
    """Parse a published JSON string, treating anything unusable as empty."""
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


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
    "NO_AUTHORITATIVE_ALPHA_IMAGE": ("No clear alpha image was found", "Set a manual alpha source; automatic detection needs a supported Alpha or Base Color image path."),
    "UNSUPPORTED_ALPHA_PATH": ("Alpha uses unsupported shader processing", "Choose the intended image and channel manually, or bake combined processing to an image."),
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
    "NO_POSITIVE_AREA_UV_COVERAGE": (
        "Face UVs collapse to a line or point",
        "UVs may be outside 0–1; give this face positive UV area, then analyze again.",
    ),
    "SUPPRESSED_FACES": ("Alpha evidence is below the significance setting", "Set Below-Significance Evidence to Keep on source to assign the rest of this material group."),
    "UNSUPPORTED_FACES": ("Some faces could not be analyzed", "Resolve the listed material source before applying this material group."),
    "FACE_LOCAL_UNSUPPORTED_FACES": ("Some faces have uncertain UV coverage", "Move those faces to alpha, keep them on the source, or skip this material group deliberately."),
    "FACE_LOCAL_UNSUPPORTED_TO_ALPHA": ("Uncertain faces will use the alpha material", "This preserves possible transparency at the cost of some additional transparent rendering."),
    "FACE_LOCAL_UNSUPPORTED_KEPT_SOURCE": ("Uncertain faces will stay on the source", "Confirm that these faces do not require transparency before applying."),
    "FACES_RETAINED_BY_POLICY": (
        "Some faces will stay on the source by policy",
        "Preview the exact plan and confirm that the retained faces do not require alpha rendering.",
    ),
    "MATERIAL_ALPHA_SOURCE_UNRESOLVED": ("No alpha source was selected", "This material stays unchanged; set a manual alpha source only if it should be separated."),
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
    "REVIEW_CHANGED": (
        "The reviewed material plan changed",
        "Preview the faces again before applying the updated material plan.",
    ),
    "PREFLIGHT_CHANGED": (
        "The confirmed material plan changed",
        "Review the updated destinations and warnings, then apply again.",
    ),
    "DERIVED_NOT_EDITABLE": (
        "The existing alpha material is not editable",
        "Use a local editable alpha material or choose a new local variant in Expert mode.",
    ),
}

KNOWN_GUIDANCE_CODES = frozenset(_GUIDANCE)

_MATERIAL_CARD_FIELDS = (
    "material",
    "supported",
    "resolution",
    "image",
    "uv_map",
    "channel",
    "address_mode",
    "source_method",
    "alpha_material",
)


def ui_text_lines(text: str, available_width: int) -> tuple[str, ...]:
    """Wrap UI copy conservatively for the available Blender layout width."""

    usable_width = max(1, int(available_width) - _UI_HORIZONTAL_PADDING)
    line_characters = max(
        _UI_MIN_LINE_CHARACTERS,
        usable_width // _UI_AVERAGE_CHARACTER_WIDTH,
    )
    return tuple(
        textwrap.wrap(
            str(text),
            width=line_characters,
            break_long_words=False,
            break_on_hyphens=False,
        )
    ) or ("",)


def review_material_cards(report_payload: dict) -> tuple[dict, ...]:
    """Return the panel's unique material results in report order."""

    cards = []
    seen = set()
    for object_result in report_payload.get("objects", ()):
        if object_result.get("skip_reason"):
            continue
        for group in object_result.get("groups", ()):
            key = tuple(group.get(field) for field in _MATERIAL_CARD_FIELDS)
            if key not in seen:
                seen.add(key)
                cards.append(group)
    return tuple(cards)


def alpha_source_advisory(
    material_cards: tuple[dict, ...],
) -> tuple[str, str] | None:
    """Return concise review guidance when automatic alpha sources are missing."""

    count = sum(not card.get("supported") for card in material_cards)
    if not count:
        return None
    noun = "material" if count == 1 else "materials"
    pronoun = "it" if count == 1 else "them"
    return (
        f"{count} {noun} may need an alpha source.",
        f"Open Material Details below to review {pronoun}.",
    )


def _counted(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count:,} {word}"


def assignment_confirmation_lines(
    plan_payload: dict,
    *,
    previewed: bool = True,
) -> tuple[str, ...]:
    """Describe only the aggregate consequences of an assignment plan."""

    faces = int(plan_payload.get("faces_to_reassign", 0))
    slots = int(plan_payload.get("planned_additional_slots", 0))
    mixed = int(plan_payload.get("mixed_faces_to_alpha", 0))
    uncertain = int(plan_payload.get("face_local_unsupported_to_alpha", 0))
    suppressed = int(plan_payload.get("suppressed_faces_to_alpha", 0))
    retained = int(plan_payload.get("retained_faces_by_policy", 0))
    unresolved = int(
        plan_payload.get("material_source_groups_left_unchanged", 0)
    )
    skipped_groups = int(plan_payload.get("skipped_material_groups", 0))
    skipped_objects = int(plan_payload.get("skipped_object_count", 0))
    lines = [] if previewed else ["Faces have not been previewed."]

    action = ""
    if faces:
        destination = "an alpha material" if faces == 1 else "alpha materials"
        action = f"Move {_counted(faces, 'reviewed face')} to {destination}"
    if slots:
        slot_clause = f"add {_counted(slots, 'material slot')}"
        action = f"{action} and {slot_clause}" if action else slot_clause.capitalize()
    if action:
        lines.append(f"{action}.")

    included = []
    if mixed:
        included.append(_counted(mixed, "mixed face"))
    if uncertain:
        included.append(_counted(uncertain, "uncertain face"))
    if included:
        lines.append(f"This includes {' and '.join(included)}.")
    if suppressed:
        lines.append(
            f"Move {_counted(suppressed, 'below-significance face')} to alpha."
        )
    if retained:
        if retained == 1:
            lines.append(
                "1 reviewed face will remain on its source material by policy."
            )
        else:
            lines.append(
                f"{retained:,} reviewed faces will remain on their source "
                "materials by policy."
            )
    if unresolved:
        lines.append(
            f"{_counted(unresolved, 'unresolved material group')} "
            "will remain unchanged."
        )

    skipped = []
    if skipped_groups:
        skipped.append(_counted(skipped_groups, "material group"))
    if skipped_objects:
        skipped.append(_counted(skipped_objects, "object"))
    if skipped:
        lines.append(f"Skip {' and '.join(skipped)}.")

    lines.append(
        "Only material slots and face assignments change—no topology or "
        "source shader changes. Ctrl+Z to undo."
    )
    return tuple(lines)


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


def already_separated_tooltip(
    *, already_derived: bool, actionable: bool
) -> str:
    if not already_derived or actionable:
        return ""
    return (
        "All faces on the selected meshes are optimally assigned. "
        "No faces need to be moved."
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
    plan_payload: dict | None = None,
) -> str:
    payload = json.dumps(
        [
            analysis_id,
            mixed_policy,
            suppressed_policy,
            unsupported_policy,
            conflict_policy,
            plan_payload or {},
        ],
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.blake2b(payload.encode("utf8"), digest_size=16).hexdigest()


def assignment_plan_signature(plan_payload: dict) -> str:
    """Fingerprint a complete preflight independently of operator UI state."""

    payload = json.dumps(plan_payload, separators=(",", ":"), sort_keys=True)
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
        "can_preview": has_report and actionable and not running and not stale,
        "can_apply": has_report and actionable and not running and not stale,
    }
