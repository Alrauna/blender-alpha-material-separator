# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

from addon import api_contract, manifest
from addon.overrides import (
    ADDRESS_MODES as OVERRIDE_ADDRESS_MODES,
    MaterialOverride,
    parse_material_overrides_json,
)


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
        self.assertEqual(payload["api_version"], "1.3")
        self.assertEqual(
            payload["extension_version"],
            api_contract.dotted(manifest.version_tuple()),
        )
        manifest_data = tomllib.loads(MANIFEST.read_text(encoding="utf8"))
        self.assertEqual(manifest_data["version"], payload["extension_version"])
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
        self.assertEqual(payload["address_modes"], list(OVERRIDE_ADDRESS_MODES))
        self.assertIn("AUTO", payload["address_modes"])
        self.assertIn(
            "SIMPLE_REROUTE_IN_ALPHA_PATH",
            payload["supported_material_patterns"],
        )
        self.assertIn(
            "UNIQUE_BASE_COLOR_IMAGE_STORED_ALPHA",
            payload["supported_material_patterns"],
        )

    def test_every_published_address_mode_is_accepted_by_the_parser(self) -> None:
        published = api_contract.capability_payload()["address_modes"]
        for mode in published:
            with self.subTest(mode=mode):
                parsed = parse_material_overrides_json(
                    json.dumps(
                        [{"material_name": "Body", "address_mode": mode}]
                    )
                )
                self.assertEqual(parsed[0].address_mode, mode)

    def test_the_override_default_is_published_as_valid(self) -> None:
        default = MaterialOverride(material_name="Body").address_mode
        self.assertIn(default, api_contract.capability_payload()["address_modes"])

    def test_public_operator_ids_remain_api_1_compatible(self) -> None:
        self.assertEqual(api_contract.API_VERSION, (1, 3))
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
            '{"a_value":2,"api_version":"1.3","code":"OK","message":"done",'
            '"severity":"OK","z_value":1}',
        )

    def test_severity_is_published_and_closed_world(self) -> None:
        self.assertEqual(api_contract.severity_for("ANALYSIS_COMPLETE"), "OK")
        self.assertEqual(api_contract.severity_for("RESULT_STALE"), "INFO")
        self.assertEqual(
            api_contract.severity_for("ASSIGNMENT_COMPLETE_WITH_SKIPS"), "INFO"
        )
        # An unlisted code is an error, reproducing the panel's previous
        # closed-world `normal` set exactly.
        self.assertEqual(api_contract.severity_for("STALE_ANALYSIS"), "ERROR")
        self.assertEqual(api_contract.severity_for("ASSIGNMENT_BLOCKED"), "ERROR")
        self.assertEqual(api_contract.severity_for("A_CODE_ADDED_LATER"), "ERROR")

    def test_the_severity_table_reproduces_the_panels_previous_normal_set(self) -> None:
        """These nine codes rendered no alert box before severity existed."""
        previously_normal = {
            "NOT_QUERIED",
            "OK",
            "ANALYSIS_COMPLETE",
            "PREVIEW_COMPLETE",
            "ASSIGNMENT_COMPLETE",
            "ASSIGNMENT_COMPLETE_WITH_SKIPS",
            "ASSIGNMENT_NO_CHANGES",
            "CLEARED",
            "RESULT_STALE",
        }
        self.assertEqual(set(api_contract.STATUS_SEVERITIES), previously_normal)
        for code in previously_normal:
            with self.subTest(code=code):
                self.assertIn(api_contract.severity_for(code), {"OK", "INFO"})

    def test_every_status_payload_carries_its_severity(self) -> None:
        self.assertEqual(api_contract.status_payload("OK", "done")["severity"], "OK")
        self.assertEqual(
            api_contract.status_payload("ASSIGNMENT_BLOCKED", "no")["severity"],
            "ERROR",
        )

    def test_publish_status_updates_state_and_returns_payload(self) -> None:
        state = SimpleNamespace(last_status_code="", last_status_json="")
        payload = api_contract.publish_status(
            state, "EXAMPLE", "Example message", count=3
        )
        self.assertEqual(state.last_status_code, "EXAMPLE")
        self.assertEqual(json.loads(state.last_status_json), payload)
        self.assertEqual(payload["count"], 3)

    def test_workflow_payload_publishes_the_documented_field_set(self) -> None:
        view = {
            "state": "READY_TO_REVIEW",
            "can_analyze": True,
            "can_preview": True,
            "can_apply": True,
            "running": False,
            "stale": False,
            "reviewed": False,
            "actionable": True,
            "already_separated": False,
            "eligible_object_count": 2,
            "analysis_id": "abc123",
            "validation_state": "CLEAN",
            "expected_review_signature": "deadbeef",
            # Live objects the panel needs are never published.
            "plan": object(),
            "report": object(),
        }
        payload = api_contract.workflow_payload(view)
        self.assertEqual(
            set(payload),
            set(api_contract.WORKFLOW_FIELDS) | {"api_version"},
        )
        self.assertEqual(payload["api_version"], "1.3")
        self.assertEqual(payload["state"], "READY_TO_REVIEW")
        self.assertTrue(payload["can_apply"])
        self.assertEqual(payload["eligible_object_count"], 2)
        # Must survive the documented serializer.
        self.assertEqual(json.loads(api_contract.dumps(payload)), payload)

    def test_degraded_workflow_payload_offers_nothing(self) -> None:
        degraded = api_contract.degraded_workflow_payload()
        self.assertEqual(set(degraded), set(api_contract.WORKFLOW_FIELDS) | {"api_version"})
        self.assertTrue(degraded["stale"])
        self.assertFalse(degraded["can_analyze"])
        self.assertFalse(degraded["can_preview"])
        self.assertFalse(degraded["can_apply"])
        self.assertIn(degraded["state"], api_contract.WORKFLOW_STATES)

    def test_published_workflow_states_match_the_presentation_states(self) -> None:
        from addon.presentation import workflow_view

        produced = set()
        for arguments in (
            dict(eligible_objects=0),
            dict(eligible_objects=1),
            dict(eligible_objects=1, has_report=True, actionable=True),
            dict(eligible_objects=1, has_report=True, actionable=True, reviewed=True),
            dict(eligible_objects=1, has_report=True, actionable=False),
            dict(eligible_objects=1, has_report=True, stale=True),
            dict(eligible_objects=1, running=True),
            dict(eligible_objects=1, completed=True),
        ):
            defaults = dict(
                eligible_objects=0,
                running=False,
                has_report=False,
                stale=False,
                reviewed=False,
                actionable=False,
                completed=False,
            )
            produced.add(workflow_view(**(defaults | arguments))["state"])
        self.assertEqual(produced, set(api_contract.WORKFLOW_STATES))


if __name__ == "__main__":
    unittest.main()
