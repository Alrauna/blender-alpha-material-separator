# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the packaged extension manifest as the single source of identity.

The manifest is the only place a release version is edited. Everything else
derives from it, so a bump cannot leave a second copy behind.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "blender_manifest.toml"


def _readable(path: Path) -> Path:
    """Return a path Blender's Python can open on Windows.

    An installed extension can sit past the Windows MAX_PATH limit, where a
    plain absolute path fails to open. The extended-length prefix avoids that.
    It applies only to absolute Windows paths that are not already prefixed.
    """
    text = str(path)
    if len(text) < 250 or text[1:3] != ":\\" or text.startswith("\\\\?\\"):
        return path
    return Path(f"\\\\?\\{text}")


def read(path: Path | None = None) -> dict:
    """Return the parsed manifest, or an empty mapping if unreadable.

    A missing or malformed manifest must not raise. The version reaches both the
    public capability payload and the metadata written onto derived materials,
    so an honest empty value is preferable to a crash or a stale guess.
    """
    try:
        target = _readable(path or MANIFEST_PATH)
        return tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return {}


def _parse_version(raw: str) -> tuple[int, ...]:
    parts = str(raw).split(".")
    if not raw or not all(part.isdigit() for part in parts):
        return ()
    return tuple(int(part) for part in parts)


def version_tuple(path: Path | None = None) -> tuple[int, ...]:
    """Return the manifest version as integers, or an empty tuple."""
    return _parse_version(read(path).get("version", ""))


def maintainer_name(path: Path | None = None) -> str:
    """Return the maintainer without the contact address."""
    return str(read(path).get("maintainer", "")).split(" <")[0].strip()


def issues_url(path: Path | None = None) -> str:
    """Return the project issue tracker, or an empty string."""
    website = str(read(path).get("website", "")).rstrip("/")
    return f"{website}/issues" if website else ""
