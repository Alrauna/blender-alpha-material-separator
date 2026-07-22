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
            "Alpha Material",
            "Analyze Selected Meshes",
            "Preview Faces to Move",
            "Apply Material Separation",
            "Simple",
            "Expert",
        ):
            self.assertIn(text, self.text)

    def test_defaults_and_safety_caveats_are_documented(self) -> None:
        for text in (
            "Blender 5.2",
            "one object",
            "does not cut geometry",
            "Ctrl+Z",
            "Unity",
            "draw call",
            "per-material",
        ):
            self.assertIn(text, self.text)

    def test_required_end_user_sections_exist_in_order(self) -> None:
        headings = (
            "What it does",
            "Requirements and installation",
            "60-second Simple workflow",
            "What the results mean",
            "Simple and Expert interfaces",
            "Manual alpha sources",
            "What each step changes",
            "Undo, rerun, and stale results",
            "Unity and VRChat handoff",
            "Troubleshooting",
            "Supported and unsupported material setups",
            "Glossary",
            "Developer documentation",
            "License",
        )
        positions = [self.text.index(f"## {heading}") for heading in headings]
        self.assertEqual(positions, sorted(positions))

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
