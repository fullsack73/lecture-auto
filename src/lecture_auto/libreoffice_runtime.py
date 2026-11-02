from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from lecture_auto.tasking import CancellationToken


LibreOfficeProgress = Callable[[str, int | float | None, int | float | None, str], None]


class LibreOfficeRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Download:
    url: str
    sha256: str


_VERSION = "26.8.2"
_MAC_DOWNLOADS = {
    "arm64": _Download(
        f"https://download.documentfoundation.org/libreoffice/stable/{_VERSION}/mac/aarch64/LibreOffice_{_VERSION}_MacOS_aarch64.dmg",
        "9f24fe83ab1ed5c95eb3df580119f32932f713e577feeac02bf619fb00749b55",
    ),
    "x86_64": _Download(
        f"https://download.documentfoundation.org/libreoffice/stable/{_VERSION}/mac/x86_64/LibreOffice_{_VERSION}_MacOS_x86-64.dmg",
        "0af062779cc17f6f852918b2424c745f7dd2d20d51d7fb8a0925eb92ec0417a7",
    ),
}


def _runtime_dir(value: Path | str | None) -> Path:
    if value is not None:
        return Path(value).expanduser().resolve()
    from lecture_auto.local_runtime import default_runtime_dir

    return default_runtime_dir()


def find_libreoffice(runtime_dir: Path | str | None = None) -> str | None:
    root = _runtime_dir(runtime_dir)
    candidates = [
        root / "libreoffice" / "LibreOffice.app" / "Contents" / "MacOS" / "soffice",
        root / "libreoffice" / "program" / "soffice",
        root / "libreoffice" / "program" / "soffice.com",
        root / "libreoffice" / "program" / "soffice.exe",
    ]
    for name in ("libreoffice", "soffice"):
        resolved = shutil.which(name)
        if resolved:
            candidates.append(Path(resolved))
    if sys.platform == "darwin":
        candidates.extend(
            (
                Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
                Path.home() / "Applications/LibreOffice.app/Contents/MacOS/soffice",
            )
        )
    elif sys.platform == "win32":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                candidates.extend(
                    (
                        Path(base) / "LibreOffice/program/soffice.com",
                        Path(base) / "LibreOffice/program/soffice.exe",
                    )
                )
    else:
        candidates.append(Path("/opt/libreoffice/program/soffice"))
        candidates.extend(sorted(Path("/opt").glob("libreoffice*/program/soffice")))
    return next((str(path) for path in candidates if path.is_file()), None)


def install_libreoffice(
    runtime_dir: Path | str | None = None,
    *,
    progress: LibreOfficeProgress | None = None,
    cancellation_token: CancellationToken | None = None,
) -> str:
    if sys.platform == "win32":
        from lecture_auto.libreoffice_windows import install_windows_libreoffice

        return install_windows_libreoffice(_runtime_dir(runtime_dir), progress=progress, cancellation_token=cancellation_token)
    if sys.platform.startswith("linux"):
        from lecture_auto.libreoffice_linux import install_linux_libreoffice

        return install_linux_libreoffice(_runtime_dir(runtime_dir), progress=progress, cancellation_token=cancellation_token)
    if sys.platform != "darwin":
        raise LibreOfficeRuntimeError(f"Unsupported platform: {sys.platform}")
    arch = {"aarch64": "arm64", "amd64": "x86_64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    download = _MAC_DOWNLOADS.get(arch)
    if download is None:
        raise LibreOfficeRuntimeError(f"Unsupported macOS architecture: {platform.machine()}")

    token = cancellation_token or CancellationToken()
    root = _runtime_dir(runtime_dir)
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
            dmg = temporary_dir / "LibreOffice.dmg"
            mount = temporary_dir / "mount"
            mount.mkdir()
            step("download", 0, 4, f"Downloading LibreOffice {_VERSION}")
            token.raise_if_cancelled()
            _download(dmg, download, token, progress)
            token.raise_if_cancelled()
            step("mount", 1, 4, "Opening LibreOffice installer")
            _run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(dmg)])
            try:
                source = mount / "LibreOffice.app"
                if not source.is_dir():
                    raise LibreOfficeRuntimeError("LibreOffice.app was not found in the downloaded image.")
                token.raise_if_cancelled()
                step("copy", 2, 4, "Installing LibreOffice")
                shutil.copytree(source, staging / "LibreOffice.app", symlinks=True)
            finally:
                _run(["hdiutil", "detach", str(mount)], check=False)

        token.raise_if_cancelled()
        executable = staging / "LibreOffice.app/Contents/MacOS/soffice"
        if not executable.is_file():
            raise LibreOfficeRuntimeError("Installed LibreOffice executable is missing.")
        step("validate", 3, 4, "Validating LibreOffice")
        _run([str(executable), "--headless", "--version"])
        if destination.exists():
            destination.replace(backup)
        staging.replace(destination)
        shutil.rmtree(backup, ignore_errors=True)
        installed = destination / "LibreOffice.app/Contents/MacOS/soffice"
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
        raise LibreOfficeRuntimeError(f"LibreOffice download failed: {exc}") from exc
    if digest.hexdigest() != download.sha256:
        raise LibreOfficeRuntimeError("LibreOffice download checksum verification failed.")


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if check:
            raise LibreOfficeRuntimeError(f"LibreOffice installer command failed: {exc}") from exc
        return subprocess.CompletedProcess(command, 1, "", str(exc))
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise LibreOfficeRuntimeError(detail or "LibreOffice installer command failed.")
    return result
