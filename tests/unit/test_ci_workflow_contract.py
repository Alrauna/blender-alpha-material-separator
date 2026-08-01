# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


class CiWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_validation_triggers_and_stable_names(self) -> None:
        for text in (
            "pull_request:",
            "push:",
            "branches: [main]",
            "workflow_dispatch:",
            "CI / ${{ matrix.label }} — Blender 5.2",
            "runner: windows-2025",
            "runner: ubuntu-24.04",
            "label: Windows",
            "label: Linux",
        ):
            self.assertIn(text, self.text)
        self.assertNotIn("pull_request_target", self.text)
        self.assertNotIn("schedule:", self.text)

    def test_checkout_and_default_permissions_are_locked_down(self) -> None:
        self.assertIn("permissions:\n  contents: read", self.text)
        self.assertIn(f"actions/checkout@{CHECKOUT_SHA}", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertEqual(self.text.count("actions/checkout@"), 1)

    def test_no_unapproved_actions_or_execution_surfaces(self) -> None:
        action_uses = re.findall(r"^\s*uses:\s*(\S+)", self.text, re.MULTILINE)
        self.assertEqual(
            action_uses,
            [f"actions/checkout@{CHECKOUT_SHA}"],
        )
        for forbidden in (
            "actions/cache",
            "actions/upload-artifact",
            "actions/download-artifact",
            "setup-python",
            "container:",
            "self-hosted",
            "secrets.",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_validation_runs_the_complete_project_gate(self) -> None:
        for text in (
            "scripts/ci.py prepare-blender",
            "-m unittest discover -s tests/unit -t . -v",
            "--disable-autoexec",
            "--python tests/blender/run_all.py",
            "--command extension validate addon",
            "--command extension build",
            "--source-dir addon",
            "--command extension validate",
        ):
            self.assertIn(text, self.text)


if __name__ == "__main__":
    unittest.main()
