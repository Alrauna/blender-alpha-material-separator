# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

from addon import api_contract
from addon.overrides import ADDRESS_MODES as OVERRIDE_ADDRESS_MODES


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "addon" / "blender_manifest.toml"


class ApiContractTests(unittest.TestCase):
    def test_core_import_does_not_require_bpy(self) -> None:
        self.assertNotIn("bpy", sys.modules)

    def test_capability_payload_is_deterministic_and_conservative(self) -> None:
        first = api_contract.dumps(api_contract.capability_payload())
        second = api_contract.dumps(api_contract.capability_payload())
        self.assertEqual(first, second)

        payload = json.loads(first)
        self.assertEqual(payload["api_version"], "1.2")
        self.assertEqual(payload["extension_version"], "1.0.0")
        manifest = tomllib.loads(MANIFEST.read_text(encoding="utf8"))
        self.assertEqual(manifest["version"], payload["extension_version"])
        self.assertTrue(payload["capabilities"]["query_capabilities"])
        self.assertTrue(payload["capabilities"]["material_support_matrix_ready"])
        self.assertTrue(payload["capabilities"]["analysis"])
        self.assertTrue(payload["capabilities"]["component_revalidation"])
        self.assertTrue(payload["capabilities"]["face_selection_preview"])
        self.assertTrue(payload["capabilities"]["material_assignment"])
        self.assertTrue(payload["capabilities"]["per_material_overrides"])
        self.assertTrue(payload["capabilities"]["partial_material_assignment"])
        self.assertTrue(payload["capabilities"]["plan_derived_preview"])
        self.assertTrue(payload["capabilities"]["reason_scoped_unsupported"])
        self.assertEqual(
            payload["unsupported_scopes"],
            ["FACE_LOCAL", "MATERIAL_SOURCE", "DATA_SAFETY"],
        )
        self.assertIn("TO_ALPHA", payload["unsupported_policies"])
        self.assertEqual(
            payload["validation_states"], ["CLEAN", "RECHECK_PENDING", "STALE"]
        )
        self.assertIn("SUPPRESSED", payload["classifications"])
        self.assertEqual(
            payload["address_modes"],
            [mode for mode in OVERRIDE_ADDRESS_MODES if mode != "AUTO"],
        )
        self.assertIn(
            "SIMPLE_REROUTE_IN_ALPHA_PATH",
            payload["supported_material_patterns"],
        )
        self.assertIn(
            "UNIQUE_BASE_COLOR_IMAGE_STORED_ALPHA",
            payload["supported_material_patterns"],
        )

    def test_public_operator_ids_remain_api_1_2_compatible(self) -> None:
        self.assertEqual(api_contract.API_VERSION, (1, 2))
        self.assertEqual(
            api_contract.PUBLIC_OPERATOR_IDS,
            (
                "alpha_material_separator.query_capabilities",
                "alpha_material_separator.analyze",
                "alpha_material_separator.select_faces",
                "alpha_material_separator.assign_materials",
                "alpha_material_separator.clear_results",
            ),
        )
        payload = api_contract.capability_payload()
        self.assertEqual(payload["operator_ids"], list(api_contract.PUBLIC_OPERATOR_IDS))
        self.assertTrue(payload["capabilities"]["per_material_overrides"])

    def test_status_json_uses_stable_sorting(self) -> None:
        encoded = api_contract.dumps(
            api_contract.status_payload("OK", "done", z_value=1, a_value=2)
        )
        self.assertEqual(
            encoded,
            '{"a_value":2,"api_version":"1.2","code":"OK","message":"done","z_value":1}',
        )

    def test_publish_status_updates_state_and_returns_payload(self) -> None:
        state = SimpleNamespace(last_status_code="", last_status_json="")
        payload = api_contract.publish_status(
            state, "EXAMPLE", "Example message", count=3
        )
        self.assertEqual(state.last_status_code, "EXAMPLE")
        self.assertEqual(json.loads(state.last_status_json), payload)
        self.assertEqual(payload["count"], 3)


if __name__ == "__main__":
    unittest.main()
