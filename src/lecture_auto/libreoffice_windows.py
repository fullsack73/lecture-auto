from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import tempfile
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lecture_auto.tasking import CancellationToken


LibreOfficeProgress = Callable[[str, int | float | None, int | float | None, str], None]


class WindowsLibreOfficeInstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Download:
    url: str
    sha256: str


_VERSION = "26.8.2"
_DOWNLOADS = {
    "x86_64": _Download(
        f"https://download.documentfoundation.org/libreoffice/stable/{_VERSION}/win/x86_64/LibreOffice_{_VERSION}_Win_x86-64.msi",
        "ff4b911403b67ee9e6249f820f9782c44bb32c94fdaa45b0da53a8e419e5307a",
    ),
    "arm64": _Download(
        f"https://download.documentfoundation.org/libreoffice/stable/{_VERSION}/win/aarch64/LibreOffice_{_VERSION}_Win_aarch64.msi",
        "73e6a15f5b2b9e6a87ffad7fdaacd6e992a597b08c911ee7e3baddd15e29bcc7",
    ),
}


def install_windows_libreoffice(
    runtime_dir: Path | str,
    *,
    progress: LibreOfficeProgress | None = None,
    cancellation_token: CancellationToken | None = None,
) -> str:
    """Install an isolated LibreOffice copy using MSI administrative extraction."""
    arch = {"amd64": "x86_64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    download = _DOWNLOADS.get(arch)
    if download is None:
        raise WindowsLibreOfficeInstallError(
            f"Unsupported Windows architecture: {platform.machine()}"
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
        with tempfile.TemporaryDirectory(prefix="lecture-auto-libreoffice-") as temporary:
            temporary_dir = Path(temporary)
            package = temporary_dir / "LibreOffice.msi"
            extracted = temporary_dir / "extracted"
            step("download", 0, 4, f"Downloading LibreOffice {_VERSION}")
            token.raise_if_cancelled()
            _download(package, download, token, progress)
            token.raise_if_cancelled()
            step("extract", 1, 4, "Extracting LibreOffice")
            _run(
                [
                    "msiexec.exe",
                    "/a",
                    str(package),
                    "/qn",
                    f"TARGETDIR={extracted}",
                ]
            )
            token.raise_if_cancelled()
            executable = next(extracted.rglob("program/soffice.com"), None)
            if executable is None:
                raise WindowsLibreOfficeInstallError(
                    "LibreOffice executable was not found in the extracted MSI."
                )
            step("copy", 2, 4, "Installing LibreOffice")
            shutil.copytree(executable.parent.parent, staging)

        token.raise_if_cancelled()
        executable = staging / "program/soffice.com"
        step("validate", 3, 4, "Validating LibreOffice")
        _run([str(executable), "--headless", "--version"])
        if destination.exists():
            destination.replace(backup)
        staging.replace(destination)
        shutil.rmtree(backup, ignore_errors=True)
        installed = destination / "program/soffice.com"
        step("complete", 4, 4, "LibreOffice installed")
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
        with urllib.request.urlopen(download.url, timeout=60) as response, destination.open(
            "wb"
        ) as output:
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
        raise WindowsLibreOfficeInstallError(
            f"LibreOffice download failed: {exc}"
        ) from exc
    if digest.hexdigest() != download.sha256:
        raise WindowsLibreOfficeInstallError(
            "LibreOffice download checksum verification failed."
        )


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WindowsLibreOfficeInstallError(
            f"LibreOffice installer command failed: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise WindowsLibreOfficeInstallError(
            detail or "LibreOffice installer command failed."
        )
    return result
