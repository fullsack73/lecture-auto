from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

import lecture_auto.libreoffice_runtime as libreoffice_runtime
from lecture_auto.libreoffice_runtime import (
    LibreOfficeRuntimeError,
    find_libreoffice,
    install_libreoffice,
)
from lecture_auto.tasking import CancellationToken, TaskCancelledError


def test_find_libreoffice_prefers_managed_install(tmp_path: Path) -> None:
    executable = tmp_path / "libreoffice/LibreOffice.app/Contents/MacOS/soffice"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")

    assert find_libreoffice(tmp_path) == str(executable)


def test_find_libreoffice_uses_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable = tmp_path / "soffice"
    executable.write_bytes(b"")
    monkeypatch.setattr(libreoffice_runtime.shutil, "which", lambda name: str(executable) if name == "soffice" else None)
    monkeypatch.setattr(libreoffice_runtime.sys, "platform", "linux")

    assert find_libreoffice(tmp_path / "runtime") == str(executable)


def test_install_rejects_unsupported_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(libreoffice_runtime.sys, "platform", "freebsd")

    with pytest.raises(LibreOfficeRuntimeError, match="Unsupported platform"):
        install_libreoffice(tmp_path)


def test_install_macos_downloads_validates_and_replaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"official dmg"
    download = libreoffice_runtime._Download("https://example.invalid/office.dmg", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(libreoffice_runtime.sys, "platform", "darwin")
    monkeypatch.setattr(libreoffice_runtime.platform, "machine", lambda: "arm64")
    monkeypatch.setitem(libreoffice_runtime._MAC_DOWNLOADS, "arm64", download)

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(payload))}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(libreoffice_runtime.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(payload))

    def fake_run(command: list[str], *, check: bool = True):
        if command[:2] == ["hdiutil", "attach"]:
            mount = Path(command[command.index("-mountpoint") + 1])
            executable = mount / "LibreOffice.app/Contents/MacOS/soffice"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"new")
        return libreoffice_runtime.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(libreoffice_runtime, "_run", fake_run)
    old = tmp_path / "libreoffice/LibreOffice.app/Contents/MacOS/soffice"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    events = []

    result = install_libreoffice(tmp_path, progress=lambda *args: events.append(args))

    assert Path(result).read_bytes() == b"new"
    assert events[-1][:3] == ("complete", 4, 4)
    assert not tuple(tmp_path.glob(".libreoffice-*"))


def test_install_honors_cancellation_before_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(libreoffice_runtime.sys, "platform", "darwin")
    monkeypatch.setattr(libreoffice_runtime.platform, "machine", lambda: "arm64")
    token = CancellationToken()
    token.cancel()

    with pytest.raises(TaskCancelledError):
        install_libreoffice(tmp_path, cancellation_token=token)


@pytest.mark.parametrize(
    ("system", "module_name", "function_name"),
    [("win32", "libreoffice_windows", "install_windows_libreoffice"),
     ("linux", "libreoffice_linux", "install_linux_libreoffice")],
)
def test_install_dispatches_to_platform(tmp_path, monkeypatch, system, module_name, function_name):
    import importlib

    module = importlib.import_module(f"lecture_auto.{module_name}")
    monkeypatch.setattr(module, function_name, lambda root, **kwargs: str(root / "installed"))
    monkeypatch.setattr(libreoffice_runtime.sys, "platform", system)
    assert install_libreoffice(tmp_path) == str(tmp_path / "installed")


def test_find_linux_managed_executable(tmp_path):
    executable = tmp_path / "libreoffice/program/soffice"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    assert find_libreoffice(tmp_path) == str(executable)
