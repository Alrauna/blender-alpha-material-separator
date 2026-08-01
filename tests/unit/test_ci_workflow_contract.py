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
        self.assertEqual(self.text.count("actions/checkout@"), 2)

    def test_no_unapproved_actions_or_execution_surfaces(self) -> None:
        action_uses = re.findall(r"^\s*uses:\s*(\S+)", self.text, re.MULTILINE)
        self.assertEqual(
            action_uses,
            [f"actions/checkout@{CHECKOUT_SHA}"] * 2,
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
            "github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/main'",
            "github.event.repository.visibility == 'public'",
            "needs: [validate, release_gate]",
            "environment: release",
            "contents: write",
        ):
            self.assertIn(text, self.text)

    def test_release_job_fetches_exact_public_sha_without_credentials(self) -> None:
        release = self.text.split("\n  release:\n", 1)[1]
        source_step = release.split(
            "\n      - name: Refuse an existing tag or release",
            1,
        )[0]
        self.assertNotIn("uses:", release)
        self.assertIn(
            "SOURCE_REPOSITORY: https://github.com/${{ github.repository }}.git",
            source_step,
        )
        self.assertIn("SOURCE_SHA: ${{ github.sha }}", source_step)
        self.assertIn("GIT_TERMINAL_PROMPT: 0", source_step)
        self.assertIn("git init .", source_step)
        self.assertIn(
            "git fetch --no-tags --depth=1 origin $env:SOURCE_SHA",
            source_step,
        )
        self.assertIn("git checkout --detach FETCH_HEAD", source_step)
        self.assertIn("git rev-parse HEAD", source_step)
        self.assertIn("$Actual.Trim() -ne $env:SOURCE_SHA", source_step)
        self.assertNotIn("GH_TOKEN:", source_step)
        self.assertNotIn("github.token", source_step)

    def test_dispatch_contexts_never_enter_shell_source(self) -> None:
        self.assertNotIn("if ('${{ github.ref }}'", self.text)
        self.assertNotIn(
            "if ('${{ github.event.repository.visibility }}'",
            self.text,
        )
        release_gate = self.text.split(
            "\n  release_gate:\n",
            1,
        )[1].split("\n  release:\n", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", release_gate)
        self.assertIn(
            "github.event.repository.visibility == 'public'",
            release_gate,
        )

    def test_validation_discovers_exactly_one_versioned_zip(self) -> None:
        validate = self.text.split("\n  release_gate:\n", 1)[0]
        self.assertNotIn("alpha_material_separator-1.0.0.zip", validate)
        self.assertIn("Get-ChildItem", validate)
        self.assertIn("-Filter 'alpha_material_separator-*.zip'", validate)
        self.assertIn("$Archives.Count -ne 1", validate)
        self.assertIn("$Archives[0].FullName", validate)

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

    def test_release_input_is_never_interpolated_into_shell_source(self) -> None:
        expression = "${{ inputs.version }}"
        expression_lines = [
            line.strip()
            for line in self.text.splitlines()
            if expression in line
        ]
        self.assertEqual(
            expression_lines,
            [f"RELEASE_VERSION: {expression}"] * 2,
        )
        self.assertIn("$env:RELEASE_VERSION", self.text)

    def test_ci_security_and_rollout_are_documented(self) -> None:
        testing = (ROOT / "docs" / "testing.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        plan = (ROOT / "PLAN.md").read_text(encoding="utf-8")
        for text in (
            "CI / Windows — Blender 5.2",
            "CI / Linux — Blender 5.2",
            "Blender 5.2.0",
            "Cloudflare",
            "Quad9",
            "SHA256SUMS.txt",
            "performance threshold",
        ):
            self.assertIn(text, testing)
        for text in (
            "actions/checkout",
            "persist-credentials: false",
            "contents: read",
            "contents: write",
            "Do not push",
        ):
            self.assertIn(text, agents)
        self.assertIn("GitHub Actions CI/CD", plan)
        for text in (
            "unauthenticated native Git",
            "exact `GITHUB_SHA`",
            "30-second connection timeout",
            "two retries",
            "version-independent",
            "separate milestone",
            "Quad9 DoT",
            "exact archive root",
        ):
            self.assertIn(text, testing + agents + plan)


if __name__ == "__main__":
    unittest.main()
