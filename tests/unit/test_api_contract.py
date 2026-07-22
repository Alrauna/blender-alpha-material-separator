# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import sys
import unittest

from addon import api_contract


class ApiContractTests(unittest.TestCase):
    def test_core_import_does_not_require_bpy(self) -> None:
        self.assertNotIn("bpy", sys.modules)

    def test_capability_payload_is_deterministic_and_conservative(self) -> None:
        first = api_contract.dumps(api_contract.capability_payload())
        second = api_contract.dumps(api_contract.capability_payload())
        self.assertEqual(first, second)

        payload = json.loads(first)
        self.assertEqual(payload["api_version"], "1.0")
        self.assertEqual(payload["extension_version"], "0.1.0")
        self.assertTrue(payload["capabilities"]["query_capabilities"])
        self.assertTrue(payload["capabilities"]["material_support_matrix_ready"])
        self.assertTrue(payload["capabilities"]["analysis"])
        self.assertTrue(payload["capabilities"]["face_selection_preview"])
        self.assertTrue(payload["capabilities"]["material_assignment"])
        self.assertIn("SUPPRESSED", payload["classifications"])
        self.assertIn(
            "SIMPLE_REROUTE_IN_ALPHA_PATH",
            payload["supported_material_patterns"],
        )
        self.assertIn(
            "UNIQUE_BASE_COLOR_IMAGE_STORED_ALPHA",
            payload["supported_material_patterns"],
        )

    def test_status_json_uses_stable_sorting(self) -> None:
        encoded = api_contract.dumps(
            api_contract.status_payload("OK", "done", z_value=1, a_value=2)
        )
        self.assertEqual(
            encoded,
            '{"a_value":2,"api_version":"1.0","code":"OK","message":"done","z_value":1}',
        )


if __name__ == "__main__":
    unittest.main()
