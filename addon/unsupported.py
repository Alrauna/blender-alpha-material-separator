# SPDX-License-Identifier: GPL-3.0-or-later
"""Reason-scoped policy helpers for unsupported face analysis results."""

from __future__ import annotations


FACE_LOCAL_UNSUPPORTED_REASONS = frozenset(
    {
        "INVALID_UV",
        "NO_POSITIVE_AREA_UV_COVERAGE",
        "UV_TRIANGLES_UNAVAILABLE",
    }
)

UNSUPPORTED_SCOPE_FACE_LOCAL = "FACE_LOCAL"
UNSUPPORTED_SCOPE_MATERIAL_SOURCE = "MATERIAL_SOURCE"


def unsupported_scope(reason: str | None, *, material_supported: bool) -> str:
    """Classify an unsupported result without weakening its face classification.

    Face-local reasons occur only after a material alpha source was resolved. A
    resolver, image, or other material-wide failure stays out of the assignment
    plan so it cannot accidentally be routed to an alpha variant.
    """

    code = (reason or "").split(":", 1)[0]
    if material_supported and (
        code in FACE_LOCAL_UNSUPPORTED_REASONS or code.startswith("BUDGET_")
    ):
        return UNSUPPORTED_SCOPE_FACE_LOCAL
    return UNSUPPORTED_SCOPE_MATERIAL_SOURCE
