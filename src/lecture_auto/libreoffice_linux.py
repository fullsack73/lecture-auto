from __future__ import annotations

import hashlib
import io
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from lecture_auto.tasking import CancellationToken

LibreOfficeProgress = Callable[[str, int | float | None, int | float | None, str], None]


class LinuxLibreOfficeError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Download:
    url: str
    sha256: str


_VERSION = "26.8.2"
_DOWNLOADS = {
    "x86_64": _Download(
        f"https://download.documentfoundation.org/libreoffice/stable/{_VERSION}/deb/x86_64/LibreOffice_{_VERSION}_Linux_x86-64_deb.tar.gz",
        "8290c8f46cb33d6df8f681cb796e0697461ea070f86ec55b63c94d7eb9d9a476",
    ),
    "aarch64": _Download(
        f"https://download.documentfoundation.org/libreoffice/stable/{_VERSION}/deb/aarch64/LibreOffice_{_VERSION}_Linux_aarch64_deb.tar.gz",
        "54a780b666fcda7510c2eebe85265b71dd209db280fc16882fca5589015ca505",
    ),
}


def install_linux_libreoffice(
    runtime_dir: Path | str,
    *,
    progress: LibreOfficeProgress | None = None,
    cancellation_token: CancellationToken | None = None,
) -> str:
    """Install official LibreOffice binaries without root or package-manager tools."""
    arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    download = _DOWNLOADS.get(arch)
    if download is None:
        raise LinuxLibreOfficeError(
            f"Managed LibreOffice installation does not support Linux architecture: {platform.machine()}"
        )

    token = cancellation_token or CancellationToken()
    root = Path(runtime_dir).expanduser().resolve()
    destination = root / "libreoffice"
    staging = root / f".libreoffice-staging-{uuid.uuid4().hex}"
    backup = root / f".libreoffice-backup-{uuid.uuid4().hex}"
    root.mkdir(parents=True, exist_ok=True)

    def step(stage: str, completed: int, total: int, message: str) -> None:
        if progress:
            progress(stage, completed, total, message)

    try:
        with tempfile.TemporaryDirectory(prefix="lecture-auto-libreoffice-linux-") as temporary:
            temporary_dir = Path(temporary)
            archive = temporary_dir / "LibreOffice.tar.gz"
            packages = temporary_dir / "packages"
            extracted = temporary_dir / "extracted"
            step("download", 0, 5, f"Downloading LibreOffice {_VERSION}")
            token.raise_if_cancelled()
            _download(archive, download, token, progress)
            token.raise_if_cancelled()
            step("unpack", 1, 5, "Opening LibreOffice packages")
            _extract_tar(archive, packages)
            debs = sorted(packages.rglob("*.deb"))
            if not debs:
                raise LinuxLibreOfficeError("No LibreOffice packages were found in the download.")
            step("extract", 2, 5, "Installing LibreOffice packages")
            for package in debs:
                token.raise_if_cancelled()
                _extract_deb(package, extracted)
            office_roots = sorted(
                path.parent.parent
                for path in (extracted / "opt").glob("libreoffice*/program/soffice")
                if path.is_file()
            )
            if len(office_roots) != 1:
                raise LinuxLibreOfficeError("The LibreOffice executable was not found after extraction.")
            shutil.copytree(office_roots[0], staging, symlinks=True)

        token.raise_if_cancelled()
        executable = staging / "program" / "soffice"
        if not executable.is_file():
            raise LinuxLibreOfficeError("Installed LibreOffice executable is missing.")
        step("validate", 3, 5, "Validating LibreOffice")
        _validate(executable)
        step("activate", 4, 5, "Activating LibreOffice")
        if destination.exists():
            destination.replace(backup)
        staging.replace(destination)
        shutil.rmtree(backup, ignore_errors=True)
        installed = destination / "program" / "soffice"
        step("complete", 5, 5, "LibreOffice installed")
        return str(installed)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and not destination.exists():
            backup.replace(destination)
        raise


def _download(
    destination: Path,
    download: _Download,
    token: CancellationToken,
    progress: LibreOfficeProgress | None,
) -> None:
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(download.url, timeout=60) as response, destination.open("wb") as output:
            total = int(response.headers.get("Content-Length") or 0) or None
            received = 0
            while chunk := response.read(1024 * 1024):
                token.raise_if_cancelled()
                output.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress:
                    progress("download", received, total, "Downloading LibreOffice")
    except OSError as exc:
        raise LinuxLibreOfficeError(f"LibreOffice download failed: {exc}") from exc
    if digest.hexdigest() != download.sha256:
        raise LinuxLibreOfficeError("LibreOffice download checksum verification failed.")


def _extract_tar(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:*") as bundle:
            _safe_extract(bundle, destination)
    except (OSError, tarfile.TarError) as exc:
        raise LinuxLibreOfficeError(f"LibreOffice package extraction failed: {exc}") from exc


def _extract_deb(package: Path, destination: Path) -> None:
    try:
        payload = _read_ar_member(package, "data.tar")
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as data:
            _safe_extract(data, destination)
    except (OSError, tarfile.TarError, ValueError) as exc:
        raise LinuxLibreOfficeError(f"Failed to extract {package.name}: {exc}") from exc


def _read_ar_member(archive: Path, prefix: str) -> bytes:
    with archive.open("rb") as source:
        if source.read(8) != b"!<arch>\n":
            raise ValueError("invalid Debian package header")
        while header := source.read(60):
            if len(header) != 60 or header[58:] != b"`\n":
                raise ValueError("invalid Debian package member")
            name = header[:16].decode("ascii", "strict").strip().rstrip("/")
            try:
                size = int(header[48:58].decode("ascii").strip())
            except ValueError as exc:
                raise ValueError("invalid Debian package member size") from exc
            data = source.read(size)
            if len(data) != size:
                raise ValueError("truncated Debian package member")
            if size % 2:
                source.read(1)
            if name.startswith(prefix):
                return data
    raise ValueError("Debian package has no data archive")


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise LinuxLibreOfficeError(f"Unsafe path in LibreOffice archive: {member.name}")
    if not hasattr(tarfile, "data_filter"):
        raise LinuxLibreOfficeError(
            "Secure archive extraction requires Python 3.11.4 or newer."
        )
    archive.extractall(destination, filter=tarfile.data_filter)


def _validate(executable: Path) -> None:
    try:
        result = subprocess.run(
            [str(executable), "--headless", "--version"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LinuxLibreOfficeError(f"LibreOffice validation failed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise LinuxLibreOfficeError(detail or "LibreOffice validation failed.")
