# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import plistlib
import re
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse


BLENDER_VERSION = "5.2.0"
BASE_URL = "https://download.blender.org/release/Blender5.2"
CHECKSUM_URL = f"{BASE_URL}/blender-5.2.0.sha256"
CURL_CONNECT_TIMEOUT_SECONDS = 30
CURL_TOTAL_TIMEOUT_SECONDS = 600
CURL_PROCESS_TIMEOUT_SECONDS = 620
CURL_RETRIES = 2
CLOUDFLARE_DOH_URL = "https://cloudflare-dns.com/dns-query"
QUAD9_DOT_HOST = "dns.quad9.net"
QUAD9_DOT_PORT = 853
MAX_RESOLVED_ADDRESSES = 16
PLATFORMS = {
    "windows": {
        "filename": "blender-5.2.0-windows-x64.zip",
        "sha256": (
            "2d184b626c001692c362291911293b6a"
            "297179d618d95e9e9192c3a80318adc4"
        ),
        "root": "blender-5.2.0-windows-x64",
        "executable": "blender.exe",
        "python_dir": "5.2/python/bin",
        "python_pattern": "python.exe",
    },
    "linux": {
        "filename": "blender-5.2.0-linux-x64.tar.xz",
        "sha256": (
            "96f6c181a30f4950607839dc84d42a35"
            "4b250d8a0231b098b59b7bc69c351c48"
        ),
        "root": "blender-5.2.0-linux-x64",
        "executable": "blender",
        "python_dir": "5.2/python/bin",
        "python_pattern": "python3.*",
    },
    "macos": {
        "filename": "blender-5.2.0-macos-arm64.dmg",
        "sha256": (
            "ed4d8390166dec5ea0a2813a03db6221"
            "f206ce016442be7f59f41d760972568a"
        ),
        "root": "Blender.app",
        "executable": "Contents/MacOS/Blender",
        "python_dir": "Contents/Resources/5.2/python/bin",
        "python_pattern": "python3.*",
    },
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+\Z")


def parse_checksum_manifest(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2 or not _SHA256.fullmatch(parts[0].lower()):
            raise ValueError("malformed checksum row")
        digest, filename = parts[0].lower(), parts[1].removeprefix("*")
        if filename in result:
            raise ValueError(f"duplicate checksum entry: {filename}")
        result[filename] = digest
    if not result:
        raise ValueError("empty checksum manifest")
    return result


def require_checksum_consensus(
    payloads: tuple[bytes, bytes, bytes],
    filename: str,
    expected_sha256: str,
) -> None:
    if len(set(payloads)) != 1:
        raise ValueError("resolver checksum payloads disagree")
    actual = parse_checksum_manifest(payloads[0]).get(filename)
    if actual is None:
        raise ValueError(f"checksum entry is missing: {filename}")
    if actual != expected_sha256:
        raise ValueError("official checksum disagrees with committed checksum")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_exact(stream: object, size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        chunk = stream.recv(size - len(result))  # type: ignore[attr-defined]
        if not chunk:
            raise ValueError("truncated DNS-over-TLS response")
        result.extend(chunk)
    return bytes(result)


def _decode_dns_name(
    message: bytes,
    offset: int,
    known_label_offsets: set[int],
) -> tuple[tuple[bytes, ...], int, set[int]]:
    labels: list[bytes] = []
    observed_offsets: set[int] = set()
    cursor = offset
    next_offset: int | None = None
    expanded_size = 1
    while True:
        if cursor >= len(message):
            raise ValueError("truncated DNS name")
        length = message[cursor]
        encoding = length & 0xC0
        if encoding == 0xC0:
            if cursor + 2 > len(message):
                raise ValueError("truncated DNS name pointer")
            pointer = ((length & 0x3F) << 8) | message[cursor + 1]
            if pointer not in known_label_offsets:
                raise ValueError("invalid DNS name pointer")
            if next_offset is None:
                next_offset = cursor + 2
            cursor = pointer
            continue
        if encoding:
            raise ValueError("invalid DNS label encoding")
        observed_offsets.add(cursor)
        cursor += 1
        if length == 0:
            if next_offset is None:
                next_offset = cursor
            return tuple(labels), next_offset, observed_offsets
        if length > 63 or cursor + length > len(message):
            raise ValueError("invalid DNS name")
        expanded_size += length + 1
        if expanded_size > 255:
            raise ValueError("DNS name exceeds 255 bytes")
        labels.append(message[cursor : cursor + length].lower())
        cursor += length


def _parse_dns_a_response(
    message: bytes,
    transaction_id: int,
    expected_question: bytes,
) -> tuple[str, ...]:
    if len(message) < 12:
        raise ValueError("truncated DNS response")
    response_id, flags, questions, answers, _, _ = (
        struct.unpack("!HHHHHH", message[:12])
    )
    # Reject non-standard opcodes, truncation, and error responses.
    if (
        response_id != transaction_id
        or not flags & 0x8000
        or flags & 0x7A0F
        or questions != 1
    ):
        raise ValueError("invalid DNS response")
    offset = 12 + len(expected_question)
    if message[12:offset] != expected_question:
        raise ValueError("DNS response question mismatch")
    question_name, question_end, known_label_offsets = _decode_dns_name(
        message,
        12,
        set(),
    )
    if (
        question_end + 4 != offset
        or message[question_end:offset] != struct.pack("!HH", 1, 1)
    ):
        raise ValueError("invalid DNS response question")
    addresses: list[str] = []
    for _ in range(answers):
        owner, offset, owner_offsets = _decode_dns_name(
            message,
            offset,
            known_label_offsets,
        )
        if offset + 10 > len(message):
            raise ValueError("truncated DNS record")
        record_type, record_class, _, length = struct.unpack(
            "!HHIH",
            message[offset : offset + 10],
        )
        offset += 10
        data = message[offset : offset + length]
        if len(data) != length:
            raise ValueError("truncated DNS record data")
        offset += length
        if record_type == 1 and record_class == 1 and length == 4:
            if owner != question_name:
                raise ValueError("DNS answer owner mismatch")
            address = str(ipaddress.IPv4Address(data))
            if address not in addresses:
                if len(addresses) >= MAX_RESOLVED_ADDRESSES:
                    raise ValueError("DNS address budget exceeded")
                addresses.append(address)
            known_label_offsets.update(owner_offsets)
    if not addresses:
        raise ValueError("Quad9 returned no IPv4 address")
    return tuple(addresses)


def quad9_addresses(hostname: str) -> tuple[str, ...]:
    labels = hostname.encode("idna").split(b".")
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError("invalid DNS hostname")
    transaction_id = secrets.randbits(16)
    question = (
        b"".join(bytes((len(label),)) + label for label in labels)
        + b"\0"
        + struct.pack("!HH", 1, 1)
    )
    message = (
        struct.pack("!HHHHHH", transaction_id, 0x0100, 1, 0, 0, 0)
        + question
    )
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection(
        (QUAD9_DOT_HOST, QUAD9_DOT_PORT),
        timeout=CURL_CONNECT_TIMEOUT_SECONDS,
    ) as raw:
        with context.wrap_socket(raw, server_hostname=QUAD9_DOT_HOST) as tls:
            tls.sendall(struct.pack("!H", len(message)) + message)
            response_size = struct.unpack("!H", _read_exact(tls, 2))[0]
            response = _read_exact(tls, response_size)
    return _parse_dns_a_response(response, transaction_id, question)


def curl_command(
    url: str,
    output: Path,
    doh_url: str | None = None,
    resolved_addresses: tuple[str, ...] | None = None,
) -> list[str]:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("HTTPS is required")
    if doh_url and resolved_addresses is not None:
        raise ValueError("choose DNS-over-HTTPS or a resolved address")
    command = [
        "curl",
        "--proto",
        "=https",
        "--tlsv1.2",
        "--fail",
        "--silent",
        "--show-error",
        "--connect-timeout",
        str(CURL_CONNECT_TIMEOUT_SECONDS),
        "--max-time",
        str(CURL_TOTAL_TIMEOUT_SECONDS),
        "--retry",
        str(CURL_RETRIES),
        "--retry-delay",
        "2",
        "--retry-max-time",
        str(CURL_TOTAL_TIMEOUT_SECONDS),
        "--retry-all-errors",
        "--output",
        str(output),
        "--write-out",
        "%{http_code}",
    ]
    if doh_url:
        if urlparse(doh_url).scheme != "https":
            raise ValueError("DNS-over-HTTPS requires HTTPS")
        command.extend(("--doh-url", doh_url))
    if resolved_addresses is not None:
        if (
            not resolved_addresses
            or len(resolved_addresses) > MAX_RESOLVED_ADDRESSES
            or parsed.hostname is None
        ):
            raise ValueError("resolved addresses require a hostname")
        addresses = ",".join(
            str(ipaddress.IPv4Address(address))
            for address in resolved_addresses
        )
        command.extend(("--resolve", f"{parsed.hostname}:443:{addresses}"))
    return [*command, url]


def download(
    url: str,
    output: Path,
    doh_url: str | None = None,
    resolved_addresses: tuple[str, ...] | None = None,
) -> None:
    try:
        result = subprocess.run(
            curl_command(url, output, doh_url, resolved_addresses),
            check=False,
            capture_output=True,
            text=True,
            timeout=CURL_PROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as ex:
        output.unlink(missing_ok=True)
        raise RuntimeError("download timed out") from ex
    if result.returncode or result.stdout != "200":
        output.unlink(missing_ok=True)
        raise RuntimeError(
            f"download failed with curl={result.returncode}, "
            f"http={result.stdout!r}: {result.stderr.strip()}"
        )


def download_via_quad9(url: str, output: Path) -> None:
    hostname = urlparse(url).hostname
    if hostname is None:
        raise ValueError("download URL requires a hostname")
    download(
        url,
        output,
        resolved_addresses=quad9_addresses(hostname),
    )


def _write_github_output(path: Path | None, **values: str | Path) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            text = str(value)
            if "\n" in text or "\r" in text:
                raise ValueError("GitHub outputs must be single-line")
            stream.write(f"{key}={text}\n")


def extract_dmg(archive: Path, output: Path, root: str) -> None:
    attached = subprocess.run(
        [
            "hdiutil",
            "attach",
            "-nobrowse",
            "-readonly",
            "-plist",
            str(archive),
        ],
        check=True,
        capture_output=True,
    )
    entities = plistlib.loads(attached.stdout)["system-entities"]
    mount_points = [
        entity["mount-point"]
        for entity in entities
        if entity.get("mount-point")
    ]
    if len(mount_points) != 1:
        raise ValueError(f"expected one mount point, got {mount_points}")
    mount = Path(mount_points[0])
    try:
        source = mount / root
        if not source.is_dir():
            raise ValueError(f"{root} not found in the disk image")
        shutil.copytree(source, output / root, symlinks=True)
    finally:
        subprocess.run(
            ["hdiutil", "detach", str(mount), "-quiet"],
            check=False,
        )


def extract_archive(platform: str, archive: Path, output: Path) -> None:
    if platform == "macos":
        extract_dmg(archive, output, PLATFORMS[platform]["root"])
    elif platform == "linux":
        shutil.unpack_archive(archive, output, filter="data")
    else:
        shutil.unpack_archive(archive, output)


def blender_executable_path(platform: str, extracted: Path) -> Path:
    metadata = PLATFORMS[platform]
    executable = extracted / metadata["root"] / metadata["executable"]
    if not executable.is_file():
        raise ValueError(f"expected Blender executable at {executable}")
    return executable.resolve()


def bundled_python_path(platform: str, root: Path) -> Path:
    metadata = PLATFORMS[platform]
    matches = [
        path.resolve()
        for path in (root / metadata["python_dir"]).glob(
            metadata["python_pattern"]
        )
        if path.is_file() and "config" not in path.name
    ]
    if not matches:
        raise ValueError("bundled Python executable was not found")
    return min(matches, key=lambda path: len(path.name))


def require_blender_version(version: str) -> None:
    if version != f"Blender {BLENDER_VERSION} LTS":
        raise ValueError(f"unexpected Blender version: {version!r}")


def prepare_blender(
    platform: str,
    output_dir: Path,
    github_output: Path | None = None,
) -> tuple[Path, Path]:
    metadata = PLATFORMS[platform]
    output_dir.mkdir(parents=True, exist_ok=False)
    checksum_paths = tuple(
        output_dir / f"checksums-{index}.txt" for index in range(3)
    )
    download(CHECKSUM_URL, checksum_paths[0])
    download(CHECKSUM_URL, checksum_paths[1], CLOUDFLARE_DOH_URL)
    download_via_quad9(CHECKSUM_URL, checksum_paths[2])
    payloads = tuple(path.read_bytes() for path in checksum_paths)
    require_checksum_consensus(
        payloads,
        metadata["filename"],
        metadata["sha256"],
    )

    archive = output_dir / metadata["filename"]
    download(f"{BASE_URL}/{metadata['filename']}", archive)
    if sha256_file(archive) != metadata["sha256"]:
        raise ValueError("downloaded archive hash mismatch")

    extract_dir = output_dir / "blender"
    extract_archive(platform, archive, extract_dir)
    blender = blender_executable_path(platform, extract_dir)
    python = bundled_python_path(
        platform,
        extract_dir / metadata["root"],
    )

    version = subprocess.run(
        [str(blender), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    require_blender_version(version)
    _write_github_output(github_output, blender=blender, python=python)
    return blender, python


def release_identity(version: str, manifest: Path) -> tuple[str, str, str]:
    if not _VERSION.fullmatch(version):
        raise ValueError("release version must use X.Y.Z")
    manifest_version = tomllib.loads(
        manifest.read_text(encoding="utf-8")
    )["version"]
    if manifest_version != version:
        raise ValueError(
            f"manifest version {manifest_version!r} does not match {version!r}"
        )
    return (
        version,
        f"v{version}",
        f"alpha_material_separator-{version}.zip",
    )


def write_sha256s(archive: Path, output: Path) -> str:
    digest = sha256_file(archive)
    output.write_text(
        f"{digest}  {archive.name}\n",
        encoding="utf-8",
        newline="\n",
    )
    return digest


def require_file_sha256(path: Path, expected_sha256: str) -> None:
    if not _SHA256.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 is malformed")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise ValueError(
            f"file SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-blender")
    prepare.add_argument("--platform", choices=tuple(PLATFORMS), required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--github-output", type=Path)

    check_release = subparsers.add_parser("check-release")
    check_release.add_argument("--version", required=True)
    check_release.add_argument("--manifest", type=Path, required=True)

    prepare_release = subparsers.add_parser("prepare-release")
    prepare_release.add_argument("--version", required=True)
    prepare_release.add_argument("--manifest", type=Path, required=True)
    prepare_release.add_argument("--archive", type=Path, required=True)
    prepare_release.add_argument("--checksum-output", type=Path, required=True)
    prepare_release.add_argument("--github-output", type=Path, required=True)

    verify_file = subparsers.add_parser("verify-file")
    verify_file.add_argument("--file", type=Path, required=True)
    verify_file.add_argument("--expected-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "prepare-blender":
        prepare_blender(
            arguments.platform,
            arguments.output_dir,
            arguments.github_output,
        )
    elif arguments.command == "check-release":
        release_identity(arguments.version, arguments.manifest)
    elif arguments.command == "prepare-release":
        version, tag, archive_name = release_identity(
            arguments.version,
            arguments.manifest,
        )
        if arguments.archive.name != archive_name:
            raise ValueError(
                f"release archive must be named {archive_name!r}"
            )
        digest = write_sha256s(
            arguments.archive,
            arguments.checksum_output,
        )
        _write_github_output(
            arguments.github_output,
            version=version,
            tag=tag,
            archive_name=archive_name,
            sha256=digest,
        )
    elif arguments.command == "verify-file":
        require_file_sha256(
            arguments.file,
            arguments.expected_sha256,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
