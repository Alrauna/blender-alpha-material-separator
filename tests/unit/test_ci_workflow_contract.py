# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
ATTEST_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"


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
            "runner: macos-15",
            "label: Windows",
            "label: Linux",
            "label: macOS",
            "platform: macos",
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
            [f"actions/checkout@{CHECKOUT_SHA}"] * 2
            + [f"actions/attest@{ATTEST_SHA}"],
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

    def test_release_attestation_is_isolated_from_content_writes(self) -> None:
        for marker in (
            "\n  release_draft:\n",
            "\n  release_attestation:\n",
            "\n  release_publish:\n",
        ):
            self.assertIn(marker, self.text)

        draft = self.text.split("\n  release_draft:\n", 1)[1].split(
            "\n  release_attestation:\n", 1
        )[0]
        attestation = self.text.split(
            "\n  release_attestation:\n", 1
        )[1].split("\n  release_publish:\n", 1)[0]
        publish = self.text.split("\n  release_publish:\n", 1)[1]

        self.assertIn("environment: release", draft)
        self.assertIn("permissions:\n      contents: write", draft)
        self.assertNotIn("uses:", draft)
        self.assertEqual(
            re.findall(
                r"^\s{4}permissions:\n(?:^\s{6}.+\n?)+",
                attestation,
                re.MULTILINE,
            ),
            [
                "    permissions:\n"
                "      contents: read\n"
                "      id-token: write\n"
                "      attestations: write\n"
            ],
        )
        self.assertNotIn("contents: write", attestation)
        self.assertIn(f"actions/attest@{ATTEST_SHA}", attestation)
        self.assertIn("environment: release", publish)
        self.assertIn("permissions:\n      contents: write", publish)
        self.assertNotIn("uses:", publish)

    def test_stored_zip_is_verified_attested_then_published(self) -> None:
        expected_subject = (
            "subject-path: '${{ runner.temp }}/downloaded-release/"
            "${{ needs.release_draft.outputs.archive_name }}'"
        )
        for text in (
            "Get-FileHash -LiteralPath $Archive -Algorithm SHA256",
            "$Actual -ne $env:EXPECTED_SHA256",
            expected_subject,
        ):
            self.assertIn(text, self.text)

        positions = [
            self.text.index("gh release create"),
            self.text.index("gh release upload"),
            self.text.index("gh release download"),
            self.text.index("scripts/ci.py verify-file"),
            self.text.index(
                "Get-FileHash -LiteralPath $Archive -Algorithm SHA256"
            ),
            self.text.index(f"actions/attest@{ATTEST_SHA}"),
            self.text.index("gh release edit"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.text.count("subject-path:"), 1)

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

    def test_macos_uses_the_complete_shared_validation_job(self) -> None:
        validate = self.text.split("\n  release_gate:\n", 1)[0]
        self.assertIn("runner: macos-15", validate)
        self.assertIn("label: macOS", validate)
        self.assertIn("platform: macos", validate)
        self.assertEqual(validate.count("steps:"), 1)
        self.assertNotIn("continue-on-error", validate)
        self.assertNotIn("matrix.platform != 'macos'", validate)

    def test_release_is_manual_main_public_and_environment_gated(self) -> None:
        draft = self.text.split("\n  release_draft:\n", 1)[1].split(
            "\n  release_attestation:\n", 1
        )[0]
        attestation = self.text.split(
            "\n  release_attestation:\n", 1
        )[1].split("\n  release_publish:\n", 1)[0]
        publish = self.text.split("\n  release_publish:\n", 1)[1]
        guards = (
            "github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/main'",
            "github.event.repository.visibility == 'public'",
        )
        for section in (draft, attestation, publish):
            for text in guards:
                self.assertIn(text, section)
        self.assertIn("needs: [validate, release_gate]", draft)
        self.assertIn("needs: [release_draft]", attestation)
        self.assertIn(
            "needs: [release_draft, release_attestation]", publish
        )
        for section in (draft, publish):
            self.assertIn("environment: release", section)
            self.assertIn("contents: write", section)

    def test_release_draft_fetches_exact_public_sha_without_credentials(
        self,
    ) -> None:
        draft = self.text.split("\n  release_draft:\n", 1)[1].split(
            "\n  release_attestation:\n", 1
        )[0]
        source_step = draft.split(
            "\n      - name: Refuse an existing tag or release",
            1,
        )[0]
        self.assertNotIn("uses:", draft)
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
        )[1].split("\n  release_draft:\n", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", release_gate)
        self.assertIn(
            "github.event.repository.visibility == 'public'",
            release_gate,
        )
        for text in (
            "RELEASE_TAG: ${{ needs.release_draft.outputs.tag }}",
            "ARCHIVE_NAME: ${{ needs.release_draft.outputs.archive_name }}",
            "EXPECTED_SHA256: ${{ needs.release_draft.outputs.sha256 }}",
            "gh release download $env:RELEASE_TAG",
            "gh release edit $env:RELEASE_TAG --draft=false",
        ):
            self.assertIn(text, self.text)

    def test_draft_outputs_enter_shell_through_step_environment(self) -> None:
        draft = self.text.split("\n  release_draft:\n", 1)[1].split(
            "\n  release_attestation:\n", 1
        )[0]
        for step in draft.split("\n      - name: ")[1:]:
            if "\n        run:" in step:
                run_source = step.split("\n        run:", 1)[1]
                self.assertNotIn("${{ steps.release.outputs.", run_source)
        for text in (
            "RELEASE_TAG: ${{ steps.release.outputs.tag }}",
            "ARCHIVE_NAME: ${{ steps.release.outputs.archive_name }}",
            "EXPECTED_SHA256: ${{ steps.release.outputs.sha256 }}",
            "gh release create $env:RELEASE_TAG",
            "gh release upload $env:RELEASE_TAG",
            "gh release download $env:RELEASE_TAG",
            "--expected-sha256 $env:EXPECTED_SHA256",
        ):
            self.assertIn(text, draft)

    def test_validation_discovers_exactly_one_versioned_zip(self) -> None:
        validate = self.text.split("\n  release_gate:\n", 1)[0]
        self.assertNotIn("alpha_material_separator-1.0.0.zip", validate)
        self.assertIn("Get-ChildItem", validate)
        self.assertIn("-Filter 'alpha_material_separator-*.zip'", validate)
        self.assertIn("$Archives.Count -ne 1", validate)
        self.assertIn("$Archives[0].FullName", validate)

    def test_build_steps_create_their_output_directory_first(self) -> None:
        for name in ("Build extension ZIP", "Build fresh extension ZIP"):
            with self.subTest(name=name):
                step = self.text.split(
                    f"\n      - name: {name}\n",
                    1,
                )[1].split("\n      - name:", 1)[0]
                self.assertIn("New-Item -ItemType Directory", step)
                self.assertLess(
                    step.index("New-Item -ItemType Directory"),
                    step.index("--command extension build"),
                )

    def test_release_is_draft_first_rehashes_attests_and_publishes(self) -> None:
        positions = [
            self.text.index("gh release create"),
            self.text.index("gh release upload"),
            self.text.index("gh release download"),
            self.text.index("scripts/ci.py verify-file"),
            self.text.index(
                "Get-FileHash -LiteralPath $Archive -Algorithm SHA256"
            ),
            self.text.index(f"actions/attest@{ATTEST_SHA}"),
            self.text.index("gh release edit"),
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("--draft", self.text)
        self.assertIn("--draft=false", self.text)
        self.assertIn("SHA256SUMS.txt", self.text)
        self.assertIn("gh api graphql", self.text)
        self.assertNotIn("gh release view", self.text)

    def test_tokens_and_permissions_are_scoped_to_release_steps(self) -> None:
        before_draft, after_draft = self.text.split(
            "\n  release_draft:\n", 1
        )
        draft, after_attestation = after_draft.split(
            "\n  release_attestation:\n", 1
        )
        attestation, publish = after_attestation.split(
            "\n  release_publish:\n", 1
        )
        self.assertEqual(self.text.count("contents: write"), 2)
        for section in (draft, publish):
            self.assertIn("permissions:\n      contents: write", section)
        self.assertNotIn("contents: write", attestation)
        self.assertIn("permissions:\n      contents: read", attestation)
        self.assertIn("id-token: write", attestation)
        self.assertIn("attestations: write", attestation)
        self.assertNotIn("GH_TOKEN:", before_draft)
        self.assertEqual(draft.count("GH_TOKEN:"), 4)
        self.assertEqual(attestation.count("GH_TOKEN:"), 1)
        self.assertEqual(publish.count("GH_TOKEN:"), 1)
        for line in self.text.splitlines():
            if "GH_TOKEN:" in line:
                self.assertIn("${{ github.token }}", line)
        token_steps = [
            step
            for step in self.text.split("\n      - name: ")[1:]
            if "GH_TOKEN:" in step
        ]
        self.assertEqual(len(token_steps), 6)
        for step in token_steps:
            self.assertEqual(step.count("GH_TOKEN:"), 1)
            self.assertIn("\n        run:", step)
            self.assertIn("gh ", step.split("\n        run:", 1)[1])
            self.assertNotIn("\n        uses:", step)

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
            "CI / macOS — Blender 5.2",
            "Blender 5.2.0",
            "macos-15",
            "blender-5.2.0-macos-arm64.dmg",
            "hdiutil",
            "Cloudflare",
            "Quad9",
            "SHA256SUMS.txt",
            "performance threshold",
        ):
            self.assertIn(text, testing)
        for text in (
            "actions/attest",
            "1e69f48acb82d1966a394da916b4c1698aa569d6",
            "gh attestation verify",
            "release_draft",
            "release_attestation",
            "release_publish",
            "contents: read",
            "id-token: write",
            "attestations: write",
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
            "validated label boundaries",
            "at most 16",
        ):
            self.assertIn(text, testing + agents + plan)


if __name__ == "__main__":
    unittest.main()
