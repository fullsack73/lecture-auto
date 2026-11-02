from __future__ import annotations

import hashlib
import io
import tarfile
from pathlib import Path

import pytest

import lecture_auto.libreoffice_linux as linux_runtime
from lecture_auto.libreoffice_linux import LinuxLibreOfficeError, install_linux_libreoffice
from lecture_auto.tasking import CancellationToken, TaskCancelledError


def _tar_bytes(files: dict[str, bytes], *, mode: str = "w:xz") -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode=mode) as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o755 if name.endswith("/soffice") else 0o644
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def _ar_member(name: str, data: bytes) -> bytes:
    header = (
        f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{0o100644:<8o}{len(data):<10}`\n"
    ).encode("ascii")
    return header + data + (b"\n" if len(data) % 2 else b"")


def _deb_bytes() -> bytes:
    payload = _tar_bytes(
        {"./opt/libreoffice26.8/program/soffice": b"executable"}
    )
    return b"!<arch>\n" + _ar_member("debian-binary", b"2.0\n") + _ar_member("data.tar.xz", payload)


def _bundle_bytes() -> bytes:
    return _tar_bytes(
        {"LibreOffice_26.8.2_Linux_x86-64_deb/DEBS/libreoffice.deb": _deb_bytes()},
        mode="w:gz",
    )


def test_install_extracts_to_user_runtime_and_replaces_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _bundle_bytes()
    download = linux_runtime._Download("https://example.invalid/office.tar.gz", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(linux_runtime.platform, "machine", lambda: "x86_64")
    monkeypatch.setitem(linux_runtime._DOWNLOADS, "x86_64", download)
    monkeypatch.setattr(linux_runtime, "_download", lambda destination, *_args: destination.write_bytes(payload))
    monkeypatch.setattr(linux_runtime, "_validate", lambda executable: None)
    old = tmp_path / "libreoffice/program/soffice"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    events: list[tuple[object, ...]] = []

    installed = install_linux_libreoffice(tmp_path, progress=lambda *args: events.append(args))

    assert installed == str(tmp_path / "libreoffice/program/soffice")
    assert Path(installed).read_bytes() == b"executable"
    assert events[-1][:3] == ("complete", 5, 5)
    assert not tuple(tmp_path.glob(".libreoffice-*"))


def test_install_rejects_unsupported_architecture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux_runtime.platform, "machine", lambda: "riscv64")

    with pytest.raises(LinuxLibreOfficeError, match="architecture: riscv64"):
        install_linux_libreoffice(tmp_path)


def test_install_honors_cancellation_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(linux_runtime.platform, "machine", lambda: "x86_64")
    token = CancellationToken()
    token.cancel()

    with pytest.raises(TaskCancelledError):
        install_linux_libreoffice(tmp_path, cancellation_token=token)


def test_download_rejects_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response(io.BytesIO):
        headers = {"Content-Length": "3"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        linux_runtime.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(b"bad"),
    )

    with pytest.raises(LinuxLibreOfficeError, match="checksum"):
        linux_runtime._download(
            tmp_path / "office.tar.gz",
            linux_runtime._Download("https://example.invalid", "0" * 64),
            CancellationToken(),
            None,
        )


def test_extract_rejects_archive_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("../escape")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))

    with pytest.raises(LinuxLibreOfficeError, match="Unsafe path"):
        linux_runtime._extract_tar(archive_path, tmp_path / "output")


def test_extract_allows_relative_link_that_stays_in_destination(tmp_path: Path) -> None:
    archive_path = tmp_path / "safe-link.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        target = tarfile.TarInfo("target")
        target.size = 1
        archive.addfile(target, io.BytesIO(b"x"))
        link = tarfile.TarInfo("directory/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../target"
        archive.addfile(link)

    linux_runtime._extract_tar(archive_path, tmp_path / "output")

    assert (tmp_path / "output/directory/link").read_bytes() == b"x"


def test_extract_rejects_link_outside_destination(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe-link.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../outside"
        archive.addfile(link)

    with pytest.raises(LinuxLibreOfficeError, match="extraction failed"):
        linux_runtime._extract_tar(archive_path, tmp_path / "output")
