# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
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
DOH_URLS = (
    "https://cloudflare-dns.com/dns-query",
    "https://dns.quad9.net/dns-query",
)
PLATFORMS = {
    "windows": {
        "filename": "blender-5.2.0-windows-x64.zip",
        "sha256": (
            "2d184b626c001692c362291911293b6a"
            "297179d618d95e9e9192c3a80318adc4"
        ),
        "executable": "blender.exe",
        "python_pattern": "python.exe",
    },
    "linux": {
        "filename": "blender-5.2.0-linux-x64.tar.xz",
        "sha256": (
            "96f6c181a30f4950607839dc84d42a35"
            "4b250d8a0231b098b59b7bc69c351c48"
        ),
        "executable": "blender",
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


def curl_command(
    url: str,
    output: Path,
    doh_url: str | None = None,
) -> list[str]:
    if urlparse(url).scheme != "https":
        raise ValueError("HTTPS is required")
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
    return [*command, url]


def download(url: str, output: Path, doh_url: str | None = None) -> None:
    try:
        result = subprocess.run(
            curl_command(url, output, doh_url),
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


def _write_github_output(path: Path | None, **values: str | Path) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for key, value in values.items():
            text = str(value)
            if "\n" in text or "\r" in text:
                raise ValueError("GitHub outputs must be single-line")
            stream.write(f"{key}={text}\n")


def extract_archive(platform: str, archive: Path, output: Path) -> None:
    if platform == "linux":
        shutil.unpack_archive(archive, output, filter="data")
    else:
        shutil.unpack_archive(archive, output)


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
    for path, doh_url in zip(checksum_paths[1:], DOH_URLS, strict=True):
        download(CHECKSUM_URL, path, doh_url)
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
    executable_matches = list(extract_dir.rglob(metadata["executable"]))
    if len(executable_matches) != 1:
        raise ValueError("expected exactly one Blender executable")
    blender = executable_matches[0].resolve()

    python_matches = [
        path.resolve()
        for path in blender.parent.joinpath("5.2", "python", "bin").glob(
            metadata["python_pattern"]
        )
        if path.is_file() and "config" not in path.name
    ]
    if not python_matches:
        raise ValueError("bundled Python executable was not found")
    python = min(python_matches, key=lambda path: len(path.name))

    version = subprocess.run(
        [str(blender), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    if version != f"Blender {BLENDER_VERSION}":
        raise ValueError(f"unexpected Blender version: {version!r}")
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
