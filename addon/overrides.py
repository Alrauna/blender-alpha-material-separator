# SPDX-License-Identifier: GPL-3.0-or-later
"""JSON-compatible per-material alpha-source override contracts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

CHANNEL_ITEMS = (
    ("ALPHA", "Alpha", "Use the image's stored alpha channel"),
    ("RED", "Red", "Use red as the alpha mask"),
    ("GREEN", "Green", "Use green as the alpha mask"),
    ("BLUE", "Blue", "Use blue as the alpha mask"),
    ("LUMINANCE", "Luminance", "Use linear RGB luminance as the alpha mask"),
)
ADDRESS_MODE_ITEMS = (
    ("AUTO", "Automatic", "Use the resolved Image Texture addressing"),
    ("REPEAT", "Repeat", "Repeat the image outside its base UV tile"),
    ("EXTEND", "Extend", "Extend edge pixels outside the base UV tile"),
    ("CLIP", "Clip", "Treat cells outside the image as transparent"),
    ("MIRROR", "Mirror", "Repeat with alternating mirrored tiles"),
)
CHANNELS = tuple(item[0] for item in CHANNEL_ITEMS)
ADDRESS_MODES = tuple(item[0] for item in ADDRESS_MODE_ITEMS)
_FIELDS = {
    "material_name",
    "image_name",
    "image_channel",
    "uv_map_name",
    "address_mode",
}


class OverrideConfigError(ValueError):
    """Raised when a public override payload is unsafe or ambiguous."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class MaterialOverride:
    material_name: str
    image_name: str = ""
    image_channel: str = "ALPHA"
    uv_map_name: str = ""
    address_mode: str = "AUTO"

    def payload(self) -> dict[str, str]:
        return asdict(self)


def parse_material_overrides_json(value: str) -> tuple[MaterialOverride, ...]:
    """Parse and validate the additive public operator argument."""
    if not value or not value.strip():
        return ()
    try:
        raw = json.loads(value)
    except (TypeError, json.JSONDecodeError) as error:
        raise OverrideConfigError(
            "INVALID_MATERIAL_OVERRIDES", "Material overrides must be valid JSON"
        ) from error
    if not isinstance(raw, list):
        raise OverrideConfigError(
            "INVALID_MATERIAL_OVERRIDES", "Material overrides must be a JSON list"
        )

    result: list[MaterialOverride] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or set(item) - _FIELDS:
            raise OverrideConfigError(
                "INVALID_MATERIAL_OVERRIDES",
                f"Material override {index + 1} has unknown or invalid fields",
            )
        values = {
            "material_name": item.get("material_name", ""),
            "image_name": item.get("image_name", ""),
            "image_channel": item.get("image_channel", "ALPHA"),
            "uv_map_name": item.get("uv_map_name", ""),
            "address_mode": item.get("address_mode", "AUTO"),
        }
        if not all(isinstance(value, str) for value in values.values()):
            raise OverrideConfigError(
                "INVALID_MATERIAL_OVERRIDES",
                f"Material override {index + 1} values must be strings",
            )
        values = {key: value.strip() for key, value in values.items()}
        name = values["material_name"]
        if not name:
            raise OverrideConfigError(
                "INVALID_MATERIAL_OVERRIDES", "Every override needs a target material"
            )
        if name in seen:
            raise OverrideConfigError(
                "DUPLICATE_MATERIAL_OVERRIDE",
                f"More than one override targets material {name!r}",
            )
        if values["image_channel"] not in CHANNELS:
            raise OverrideConfigError(
                "INVALID_MATERIAL_OVERRIDES",
                f"Unsupported image channel for material {name!r}",
            )
        if values["address_mode"] not in ADDRESS_MODES:
            raise OverrideConfigError(
                "INVALID_MATERIAL_OVERRIDES",
                f"Unsupported address mode for material {name!r}",
            )
        if not values["image_name"] and values["image_channel"] != "ALPHA":
            raise OverrideConfigError(
                "CHANNEL_REQUIRES_IMAGE_OVERRIDE",
                f"Material {name!r} needs an explicit image before selecting a channel",
            )
        seen.add(name)
        result.append(MaterialOverride(**values))
    return tuple(result)


def dumps_material_overrides(overrides) -> str:
    """Serialize override objects or payload dictionaries deterministically."""
    payload = [item.payload() if hasattr(item, "payload") else dict(item) for item in overrides]
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
