from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

import lecture_auto.libreoffice_windows as libreoffice_windows
from lecture_auto.libreoffice_windows import (
    WindowsLibreOfficeInstallError,
    install_windows_libreoffice,
)
from lecture_auto.tasking import CancellationToken, TaskCancelledError


def _fake_download(monkeypatch: pytest.MonkeyPatch, payload: bytes = b"official msi") -> None:
    download = libreoffice_windows._Download(
        "https://example.invalid/office.msi", hashlib.sha256(payload).hexdigest()
    )
    monkeypatch.setattr(libreoffice_windows.platform, "machine", lambda: "AMD64")
    monkeypatch.setitem(libreoffice_windows._DOWNLOADS, "x86_64", download)

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(payload))}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        libreoffice_windows.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )


def test_install_extracts_validates_and_replaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_download(monkeypatch)
    commands: list[list[str]] = []

    def fake_run(command: list[str]):
        commands.append(command)
        if command[0] == "msiexec.exe":
            target = Path(
                next(value for value in command if value.startswith("TARGETDIR=")).split(
                    "=", 1
                )[1]
            )
            executable = target / "LibreOffice/program/soffice.com"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"new")
        return libreoffice_windows.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(libreoffice_windows, "_run", fake_run)
    old = tmp_path / "libreoffice/program/soffice.com"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    events: list[tuple[object, ...]] = []

    result = install_windows_libreoffice(
        tmp_path, progress=lambda *args: events.append(args)
    )

    assert Path(result).read_bytes() == b"new"
    assert commands[0][:2] == ["msiexec.exe", "/a"]
    assert "/i" not in commands[0]
    assert commands[1][1:] == ["--headless", "--version"]
    assert events[-1][:3] == ("complete", 4, 4)
    assert not tuple(tmp_path.glob(".libreoffice-*"))


def test_install_preserves_existing_copy_when_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_download(monkeypatch)
    old = tmp_path / "libreoffice/program/soffice.com"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")

    def fake_run(command: list[str]):
        if command[0] == "msiexec.exe":
            target = Path(
                next(value for value in command if value.startswith("TARGETDIR=")).split(
                    "=", 1
                )[1]
            )
            executable = target / "LibreOffice/program/soffice.com"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"new")
            return libreoffice_windows.subprocess.CompletedProcess(command, 0, "", "")
        raise WindowsLibreOfficeInstallError("validation failed")

    monkeypatch.setattr(libreoffice_windows, "_run", fake_run)

    with pytest.raises(WindowsLibreOfficeInstallError, match="validation failed"):
        install_windows_libreoffice(tmp_path)

    assert old.read_bytes() == b"old"
    assert not tuple(tmp_path.glob(".libreoffice-*"))


def test_install_honors_cancellation_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(libreoffice_windows.platform, "machine", lambda: "AMD64")
    token = CancellationToken()
    token.cancel()

    with pytest.raises(TaskCancelledError):
        install_windows_libreoffice(tmp_path, cancellation_token=token)


def test_install_rejects_unsupported_architecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(libreoffice_windows.platform, "machine", lambda: "riscv64")

    with pytest.raises(WindowsLibreOfficeInstallError, match="Unsupported Windows architecture"):
        install_windows_libreoffice(tmp_path)
