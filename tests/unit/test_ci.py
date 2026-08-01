# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import struct
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
DNS_QUESTION = (
    b"\x08download\x07blender\x03org\x00"
    + struct.pack("!HH", 1, 1)
)
DNS_A_1 = (
    b"\xc0\x0c"
    + struct.pack("!HHIH", 1, 1, 60, 4)
    + b"\xcb\x00\x71\x07"
)
DNS_A_2 = (
    b"\xc0\x0c"
    + struct.pack("!HHIH", 1, 1, 60, 4)
    + b"\xcb\x00\x71\x08"
)


def dns_response(
    *,
    transaction_id: int = 0x1234,
    flags: int = 0x8180,
    question: bytes = DNS_QUESTION,
    questions: int = 1,
    answers: tuple[bytes, ...] = (),
    authorities: tuple[bytes, ...] = (),
    additional: tuple[bytes, ...] = (),
) -> bytes:
    return (
        struct.pack(
            "!HHHHHH",
            transaction_id,
            flags,
            questions,
            len(answers),
            len(authorities),
            len(additional),
        )
        + question * questions
        + b"".join((*answers, *authorities, *additional))
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

    def test_quad9_dot_uses_validated_tls_and_returns_a_records(self) -> None:
        message = dns_response(answers=(DNS_A_1,))

        class FakeTls:
            def __init__(self, payload: bytes) -> None:
                self.payload = bytearray(payload)
                self.sent = b""

            def __enter__(self) -> FakeTls:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def sendall(self, payload: bytes) -> None:
                self.sent = payload

            def recv(self, size: int) -> bytes:
                chunk = bytes(self.payload[:size])
                del self.payload[:size]
                return chunk

        tls = FakeTls(struct.pack("!H", len(message)) + message)
        raw = mock.MagicMock()
        raw.__enter__.return_value = raw
        context = mock.MagicMock()
        context.wrap_socket.return_value = tls
        with (
            mock.patch.object(
                ci.socket,
                "create_connection",
                return_value=raw,
            ) as connect,
            mock.patch.object(
                ci.ssl,
                "create_default_context",
                return_value=context,
            ),
            mock.patch.object(ci.secrets, "randbits", return_value=0x1234),
        ):
            self.assertEqual(
                ci.quad9_addresses("download.blender.org"),
                ("203.0.113.7",),
            )
        connect.assert_called_once_with(
            ("dns.quad9.net", 853),
            timeout=30,
        )
        context.wrap_socket.assert_called_once_with(
            raw,
            server_hostname="dns.quad9.net",
        )
        self.assertEqual(
            struct.unpack("!H", tls.sent[:2])[0],
            len(tls.sent) - 2,
        )
        query = tls.sent[2:]
        self.assertEqual(
            query,
            struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
            + DNS_QUESTION,
        )

    def test_dns_parser_rejects_truncated_and_non_answer_addresses(self) -> None:
        for message in (
            dns_response(flags=0x8380, answers=(DNS_A_1,)),
            dns_response(authorities=(DNS_A_1,)),
            dns_response(additional=(DNS_A_1,)),
        ):
            with self.subTest(message=message):
                with self.assertRaises(ValueError):
                    ci._parse_dns_a_response(
                        message,
                        0x1234,
                        DNS_QUESTION,
                    )

    def test_dns_parser_requires_exact_standard_question(self) -> None:
        valid = dns_response(answers=(DNS_A_1, DNS_A_2, DNS_A_1))
        self.assertEqual(
            ci._parse_dns_a_response(valid, 0x1234, DNS_QUESTION),
            ("203.0.113.7", "203.0.113.8"),
        )
        wrong_name = (
            b"\x07example\x03com\x00"
            + struct.pack("!HH", 1, 1)
        )
        wrong_type = (
            b"\x08download\x07blender\x03org\x00"
            + struct.pack("!HH", 28, 1)
        )
        for message in (
            dns_response(questions=0),
            dns_response(questions=2),
            dns_response(question=wrong_name, answers=(DNS_A_1,)),
            dns_response(question=wrong_type, answers=(DNS_A_1,)),
        ):
            with self.subTest(message=message):
                with self.assertRaises(ValueError):
                    ci._parse_dns_a_response(
                        message,
                        0x1234,
                        DNS_QUESTION,
                    )

    def test_dns_parser_rejects_invalid_headers_and_records(self) -> None:
        invalid_pointer = (
            b"\xc0\xff"
            + struct.pack("!HHIH", 1, 1, 60, 4)
            + b"\xcb\x00\x71\x07"
        )
        invalid_label = (
            b"\x40"
            + b"a" * 64
            + b"\0"
            + struct.pack("!HHIH", 1, 1, 60, 4)
            + b"\xcb\x00\x71\x07"
        )
        for message in (
            dns_response(transaction_id=0x5678, answers=(DNS_A_1,)),
            dns_response(flags=0x0180, answers=(DNS_A_1,)),
            dns_response(flags=0x8980, answers=(DNS_A_1,)),
            dns_response(flags=0x8181, answers=(DNS_A_1,)),
            dns_response(answers=(DNS_A_1[:-1],)),
            dns_response(answers=(invalid_pointer,)),
            dns_response(answers=(invalid_label,)),
            b"\x12\x34",
        ):
            with self.subTest(message=message):
                with self.assertRaises(ValueError):
                    ci._parse_dns_a_response(
                        message,
                        0x1234,
                        DNS_QUESTION,
                    )

    def test_read_exact_reassembles_chunks_and_rejects_early_eof(self) -> None:
        stream = mock.MagicMock()
        stream.recv.side_effect = (b"a", b"bc")
        self.assertEqual(ci._read_exact(stream, 3), b"abc")
        stream.recv.side_effect = (b"a", b"")
        with self.assertRaisesRegex(ValueError, "truncated"):
            ci._read_exact(stream, 3)

    def test_curl_command_can_pin_validated_hostname_to_addresses(self) -> None:
        command = ci.curl_command(
            ci.CHECKSUM_URL,
            Path("checksum.txt"),
            resolved_addresses=("203.0.113.7", "203.0.113.8"),
        )
        self.assertEqual(
            command[command.index("--resolve") + 1],
            "download.blender.org:443:203.0.113.7,203.0.113.8",
        )
        self.assertNotIn("--doh-url", command)
        with self.assertRaises(ValueError):
            ci.curl_command(
                ci.CHECKSUM_URL,
                Path("checksum.txt"),
                resolved_addresses=(),
            )

    def test_quad9_download_uses_all_resolved_addresses(self) -> None:
        output = Path("checksum.txt")
        with (
            mock.patch.object(
                ci,
                "quad9_addresses",
                return_value=("203.0.113.7", "203.0.113.8"),
            ),
            mock.patch.object(ci, "download") as download,
        ):
            ci.download_via_quad9(ci.CHECKSUM_URL, output)
        download.assert_called_once_with(
            ci.CHECKSUM_URL,
            output,
            resolved_addresses=("203.0.113.7", "203.0.113.8"),
        )

    def test_archive_extraction_uses_safe_linux_tar_filter(self) -> None:
        archive = Path("blender.tar.xz")
        output = Path("blender")
        with mock.patch.object(ci.shutil, "unpack_archive") as unpack:
            ci.extract_archive("linux", archive, output)
            unpack.assert_called_once_with(archive, output, filter="data")

        with mock.patch.object(ci.shutil, "unpack_archive") as unpack:
            ci.extract_archive("windows", Path("blender.zip"), output)
            unpack.assert_called_once_with(Path("blender.zip"), output)

    def test_blender_executable_uses_exact_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            extracted = Path(directory)
            expected = (
                extracted
                / "blender-5.2.0-linux-x64"
                / "blender"
            )
            expected.parent.mkdir()
            expected.touch()
            decoy = extracted / "nested" / "blender"
            decoy.parent.mkdir()
            decoy.touch()
            self.assertEqual(
                ci.blender_executable_path("linux", extracted),
                expected.resolve(),
            )
            expected.unlink()
            with self.assertRaisesRegex(ValueError, "expected Blender"):
                ci.blender_executable_path("linux", extracted)

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
