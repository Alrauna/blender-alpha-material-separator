# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import ci


WINDOWS_SHA256 = (
    "2d184b626c001692c362291911293b6a"
    "297179d618d95e9e9192c3a80318adc4"
)
LINUX_SHA256 = (
    "96f6c181a30f4950607839dc84d42a35"
    "4b250d8a0231b098b59b7bc69c351c48"
)


class CiTrustTests(unittest.TestCase):
    def test_fixed_blender_5_2_0_trust_anchors(self) -> None:
        self.assertEqual(ci.BLENDER_VERSION, "5.2.0")
        self.assertEqual(
            ci.CHECKSUM_URL,
            "https://download.blender.org/release/Blender5.2/"
            "blender-5.2.0.sha256",
        )
        self.assertEqual(
            ci.PLATFORMS["windows"]["filename"],
            "blender-5.2.0-windows-x64.zip",
        )
        self.assertEqual(ci.PLATFORMS["windows"]["sha256"], WINDOWS_SHA256)
        self.assertEqual(
            ci.PLATFORMS["linux"]["filename"],
            "blender-5.2.0-linux-x64.tar.xz",
        )
        self.assertEqual(ci.PLATFORMS["linux"]["sha256"], LINUX_SHA256)

    def test_parse_checksum_manifest_rejects_missing_duplicate_and_bad_rows(
        self,
    ) -> None:
        valid = (
            f"{WINDOWS_SHA256}  blender-5.2.0-windows-x64.zip\n"
            f"{LINUX_SHA256}  blender-5.2.0-linux-x64.tar.xz\n"
        ).encode()
        self.assertEqual(
            ci.parse_checksum_manifest(valid)["blender-5.2.0-windows-x64.zip"],
            WINDOWS_SHA256,
        )
        for payload in (
            b"",
            b"not-a-sha  archive.zip\n",
            (
                f"{WINDOWS_SHA256}  archive.zip\n"
                f"{WINDOWS_SHA256}  archive.zip\n"
            ).encode(),
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    ci.parse_checksum_manifest(payload)

    def test_resolver_payloads_and_committed_hash_must_all_agree(self) -> None:
        filename = "blender-5.2.0-windows-x64.zip"
        payload = f"{WINDOWS_SHA256}  {filename}\n".encode()
        ci.require_checksum_consensus(
            (payload, payload, payload), filename, WINDOWS_SHA256
        )
        with self.assertRaisesRegex(ValueError, "resolver"):
            ci.require_checksum_consensus(
                (payload, payload + b"\n", payload), filename, WINDOWS_SHA256
            )
        with self.assertRaisesRegex(ValueError, "committed"):
            ci.require_checksum_consensus(
                (payload, payload, payload), filename, "0" * 64
            )

    def test_sha256_file_hashes_bytes_without_loading_the_whole_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.bin"
            path.write_bytes(b"alpha-material-separator")
            self.assertEqual(
                ci.sha256_file(path),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )

    def test_curl_command_requires_https_tls_no_redirect_and_optional_doh(
        self,
    ) -> None:
        output = Path("checksum.txt")
        plain = ci.curl_command(ci.CHECKSUM_URL, output)
        cloudflare = ci.curl_command(
            ci.CHECKSUM_URL,
            output,
            "https://cloudflare-dns.com/dns-query",
        )
        self.assertIn("--proto", plain)
        self.assertIn("=https", plain)
        self.assertIn("--tlsv1.2", plain)
        self.assertIn("--fail", plain)
        self.assertIn("--write-out", plain)
        self.assertNotIn("--location", plain)
        self.assertNotIn("--doh-url", plain)
        for flag, value in (
            ("--connect-timeout", "30"),
            ("--max-time", "600"),
            ("--retry", "2"),
            ("--retry-delay", "2"),
            ("--retry-max-time", "600"),
        ):
            self.assertIn(flag, plain)
            self.assertEqual(plain[plain.index(flag) + 1], value)
        self.assertIn("--retry-all-errors", plain)
        self.assertEqual(
            cloudflare[cloudflare.index("--doh-url") + 1],
            "https://cloudflare-dns.com/dns-query",
        )
        with self.assertRaises(ValueError):
            ci.curl_command("http://download.blender.org/file", output)

    def test_download_timeout_removes_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "partial.bin"
            output.write_bytes(b"partial")
            timeout = subprocess.TimeoutExpired(
                cmd=["curl"],
                timeout=620,
            )
            with mock.patch.object(
                ci.subprocess,
                "run",
                side_effect=timeout,
            ):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    ci.download(ci.CHECKSUM_URL, output)
            self.assertFalse(output.exists())

    def test_archive_extraction_uses_safe_linux_tar_filter(self) -> None:
        archive = Path("blender.tar.xz")
        output = Path("blender")
        with mock.patch.object(ci.shutil, "unpack_archive") as unpack:
            ci.extract_archive("linux", archive, output)
            unpack.assert_called_once_with(archive, output, filter="data")

        with mock.patch.object(ci.shutil, "unpack_archive") as unpack:
            ci.extract_archive("windows", Path("blender.zip"), output)
            unpack.assert_called_once_with(Path("blender.zip"), output)

    def test_release_identity_is_strict_and_matches_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "blender_manifest.toml"
            manifest.write_text('version = "1.0.0"\n', encoding="utf-8")
            self.assertEqual(
                ci.release_identity("1.0.0", manifest),
                (
                    "1.0.0",
                    "v1.0.0",
                    "alpha_material_separator-1.0.0.zip",
                ),
            )
            for value in ("v1.0.0", "1.0", "1.0.0-beta", "1.0.0\nbad"):
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        ci.release_identity(value, manifest)
            with self.assertRaisesRegex(ValueError, "manifest"):
                ci.release_identity("1.0.1", manifest)

    def test_checksum_file_uses_lowercase_digest_and_archive_basename(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "alpha_material_separator-1.0.0.zip"
            checksum = root / "SHA256SUMS.txt"
            archive.write_bytes(b"release")
            digest = ci.write_sha256s(archive, checksum)
            self.assertEqual(digest, hashlib.sha256(b"release").hexdigest())
            self.assertEqual(
                checksum.read_text(encoding="utf-8"),
                f"{digest}  alpha_material_separator-1.0.0.zip\n",
            )
            ci.require_file_sha256(archive, digest)
            with self.assertRaises(ValueError):
                ci.require_file_sha256(archive, "0" * 64)


if __name__ == "__main__":
    unittest.main()
