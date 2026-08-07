# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from addon import manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "addon" / "blender_manifest.toml"


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_reads_the_packaged_manifest(self) -> None:
        self.assertEqual(manifest.read()["version"], self.raw["version"])

    def test_version_tuple_matches_the_manifest(self) -> None:
        expected = tuple(int(part) for part in self.raw["version"].split("."))
        self.assertEqual(manifest.version_tuple(), expected)

    def test_maintainer_name_drops_the_contact_address(self) -> None:
        name = manifest.maintainer_name()
        self.assertTrue(name)
        self.assertNotIn("@", name)
        self.assertNotIn("<", name)
        self.assertTrue(self.raw["maintainer"].startswith(name))

    def test_issues_url_is_derived_from_the_website(self) -> None:
        self.assertEqual(
            manifest.issues_url(), f"{self.raw['website'].rstrip('/')}/issues"
        )

    def test_unreadable_manifest_degrades_instead_of_raising(self) -> None:
        missing = Path("does-not-exist") / "blender_manifest.toml"
        self.assertEqual(manifest.read(missing), {})
        self.assertEqual(manifest.version_tuple(missing), ())
        self.assertEqual(manifest.maintainer_name(missing), "")
        self.assertEqual(manifest.issues_url(missing), "")

    def test_malformed_version_yields_an_empty_tuple(self) -> None:
        self.assertEqual(manifest._parse_version("not.a.version"), ())
        self.assertEqual(manifest._parse_version(""), ())


if __name__ == "__main__":
    unittest.main()
