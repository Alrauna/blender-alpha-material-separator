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
        self.assertEqual(self.text.count("actions/checkout@"), 3)

    def test_no_unapproved_actions_or_execution_surfaces(self) -> None:
        action_uses = re.findall(r"^\s*uses:\s*(\S+)", self.text, re.MULTILINE)
        self.assertEqual(
            action_uses,
            [f"actions/checkout@{CHECKOUT_SHA}"] * 3,
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

    def test_release_is_manual_main_public_and_environment_gated(self) -> None:
        for text in (
            "if: github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/main'",
            "github.event.repository.visibility == 'public'",
            "needs: [validate, release_gate]",
            "environment: release",
            "contents: write",
        ):
            self.assertIn(text, self.text)

    def test_release_is_draft_first_and_rehashes_downloaded_asset(self) -> None:
        positions = [
            self.text.index("gh release create"),
            self.text.index("gh release upload"),
            self.text.index("gh release download"),
            self.text.index("scripts/ci.py verify-file"),
            self.text.index("gh release edit"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("--draft", self.text)
        self.assertIn("--draft=false", self.text)
        self.assertIn("SHA256SUMS.txt", self.text)
        self.assertIn("gh api graphql", self.text)
        self.assertNotIn("gh release view", self.text)

    def test_write_token_is_scoped_to_release_and_gh_steps(self) -> None:
        release_section = self.text.split("\n  release:\n", 1)[1]
        self.assertEqual(self.text.count("contents: write"), 1)
        self.assertIn("permissions:\n      contents: write", release_section)
        self.assertNotIn("GH_TOKEN:", self.text.split("\n  release:\n", 1)[0])
        self.assertEqual(release_section.count("GH_TOKEN:"), 5)
        for line in release_section.splitlines():
            if "GH_TOKEN:" in line:
                self.assertIn("${{ github.token }}", line)


if __name__ == "__main__":
    unittest.main()
