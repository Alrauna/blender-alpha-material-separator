# SPDX-License-Identifier: GPL-3.0-or-later
"""Transient extension state.

No face-level report is stored in Blender data. Later milestones may add an
in-memory report here, but file load, undo, redo, and unregister will clear it.
"""

from __future__ import annotations

from typing import Any

_STATE: dict[str, Any] = {}


def clear() -> None:
    """Drop every transient reference owned by the extension."""
    _STATE.clear()


def snapshot() -> dict[str, Any]:
    """Return a shallow copy for lifecycle tests."""
    return dict(_STATE)
