# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest

from addon.unsupported import (
    UNSUPPORTED_SCOPE_FACE_LOCAL,
    UNSUPPORTED_SCOPE_MATERIAL_SOURCE,
    unsupported_scope,
)


class UnsupportedPolicyTests(unittest.TestCase):
    def test_resolved_face_local_failures_are_scoped_to_the_face(self) -> None:
        for reason in (
            "INVALID_UV",
            "NO_POSITIVE_AREA_UV_COVERAGE",
            "UV_TRIANGLES_UNAVAILABLE",
            "BUDGET_SCANLINES",
            "BUDGET_RUN_EMISSIONS",
        ):
            with self.subTest(reason=reason):
                self.assertEqual(
                    unsupported_scope(reason, material_supported=True),
                    UNSUPPORTED_SCOPE_FACE_LOCAL,
                )

    def test_resolver_and_image_failures_are_material_wide(self) -> None:
        for reason in (
            "NO_AUTHORITATIVE_ALPHA_IMAGE",
            "IMAGE_SNAPSHOT_MISSING",
            "IMAGE_READ_ERROR:cannot read pixels",
            "MATERIAL_UNRESOLVED",
        ):
            with self.subTest(reason=reason):
                self.assertEqual(
                    unsupported_scope(reason, material_supported=True),
                    UNSUPPORTED_SCOPE_MATERIAL_SOURCE,
                )

    def test_unresolved_material_cannot_claim_face_local_scope(self) -> None:
        self.assertEqual(
            unsupported_scope(
                "NO_POSITIVE_AREA_UV_COVERAGE", material_supported=False
            ),
            UNSUPPORTED_SCOPE_MATERIAL_SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
