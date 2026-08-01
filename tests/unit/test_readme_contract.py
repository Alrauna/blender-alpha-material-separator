# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"


class ReadmeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = README.read_text(encoding="utf8")

    def test_guided_workflow_labels_and_location_are_exact(self) -> None:
        for text in (
            "3D View",
            "open the **AMS** tab",
            "Analyze Selected Meshes",
            "Preview Faces to Move",
            "Apply Material Separation",
            "Material Details",
            "Simple",
            "Expert",
        ):
            self.assertIn(text, self.text)

    def test_current_release_identity_is_documented(self) -> None:
        self.assertIn("Version 1.0.0 targets Blender 5.2 LTS.", self.text)
        self.assertIn("alpha_material_separator-1.0.0.zip", self.text)
        self.assertNotIn("still undergoing release validation", self.text)

    def test_defaults_and_safety_caveats_are_documented(self) -> None:
        for text in (
            "Blender 5.2",
            "one object",
            "does not cut geometry",
            "Ctrl+Z",
            "draw call",
            "per-material",
            "UV coordinates may be below 0 or above 1",
        ):
            self.assertIn(text, self.text)

    def test_partial_apply_and_mode_revalidation_are_documented(self) -> None:
        for text in (
            "face-local uncertainty to alpha",
            "stays completely unchanged",
            "does not require another analysis",
            "final synchronous check",
            "aggregate assignment outcomes",
            "Review → Material Details",
            "Preview is recommended but optional",
            "Apply without Preview always asks for confirmation",
            (
                "Assignment-only plan changes require confirmation, "
                "not another analysis"
            ),
        ):
            self.assertIn(text, self.text)
        self.assertNotIn(
            "One uncertain face can conservatively skip its entire source-material group",
            self.text,
        )

    def test_friendly_status_copy_is_documented(self) -> None:
        for text in (
            "Inputs Changed — Analyze Again",
            "Left unchanged — no alpha source selected",
            "Already separated — no additional changes",
        ):
            self.assertIn(text, self.text)
        for text in (
            "materials may need an alpha source",
            "Open Material Details",
            "collapsed after every successful analysis",
        ):
            self.assertIn(text, self.text)

    def test_end_user_sections_exist_in_order(self) -> None:
        headings = (
            "What it does",
            "Install",
            "Quick start",
            "Understanding the results",
            "When a material needs help",
            "Safety, undo, and reruns",
            "After export",
            "Troubleshooting",
            "More documentation",
            "License",
        )
        positions = [self.text.index(f"## {heading}") for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_readme_excludes_renderer_and_repository_specific_copy(self) -> None:
        for text in (
            "Unity",
            "VRChat",
            ".packaged-releases/",
            ".local-references/",
            "## Developer documentation",
        ):
            self.assertNotIn(text, self.text)

    def test_readme_uses_one_screenshot_and_links_deeper_docs(self) -> None:
        images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", self.text)
        self.assertEqual(images, ["docs/images/01-panel-simple.png"])
        for target in (
            "docs/material-support.md",
            "docs/testing.md",
            "docs/integration-api.md",
            "docs/performance.md",
        ):
            self.assertIn(f"]({target})", self.text)

    def test_relative_links_resolve_inside_repository(self) -> None:
        links = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", self.text)
        for target in links:
            if "://" in target or target.startswith("#"):
                continue
            clean = target.split("#", 1)[0].replace("%20", " ")
            resolved = (ROOT / clean).resolve()
            self.assertTrue(resolved.is_relative_to(ROOT.resolve()), target)
            self.assertTrue(resolved.exists(), target)


if __name__ == "__main__":
    unittest.main()
