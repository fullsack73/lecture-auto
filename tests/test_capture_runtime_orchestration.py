from pathlib import Path

import pytest

from lecture_auto.capture_runtime import (
    CaptureDependencyError,
    CaptureInterruptedError,
    CapturePermissionError,
    CaptureRuntimeAdapter,
    CaptureHandle,
)
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


class FakeRuntimeAdapter(CaptureRuntimeAdapter):
    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.stopped: list[tuple[str, bool]] = []
        self.raise_on_start: Exception | None = None
        self.raise_on_stop: Exception | None = None

    def start_capture(self, session_id: str, output_path: str) -> CaptureHandle:
        if self.raise_on_start is not None:
            raise self.raise_on_start

        self.started.append((session_id, output_path))
        return CaptureHandle(
            session_id=session_id,
            output_path=output_path,
            process_id=7777,
            backend="fake",
        )

    def stop_capture(
        self,
        session_id: str,
        *,
        interrupted: bool = False,
        process_id: int | None = None,
    ) -> None:
        if self.raise_on_stop is not None:
            raise self.raise_on_stop

        self.stopped.append((session_id, interrupted))


def _service(tmp_path: Path, adapter: FakeRuntimeAdapter) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(store=store, runtime_adapter=adapter)


def test_capture_start_uses_runtime_adapter_and_default_session_path(tmp_path: Path) -> None:
    adapter = FakeRuntimeAdapter()
    service = _service(tmp_path, adapter)
    service.session_create("session-601", "2026-03-06")

    result = service.capture_start("session-601")

    expected_runtime_path = str((tmp_path / "recordings/session-601.wav").resolve())
    assert adapter.started == [("session-601", expected_runtime_path)]
    assert result.payload["audio_file_path"] == "recordings/session-601.wav"
    assert result.payload["timestamps"]["capture_process_id"] == 7777


def test_capture_stop_hands_off_process_lifecycle_and_persists_completed(tmp_path: Path) -> None:
    adapter = FakeRuntimeAdapter()
    service = _service(tmp_path, adapter)
    service.session_create("session-602", "2026-03-06")
    service.capture_start("session-602", "recordings/session-602.wav")

    result = service.capture_stop("session-602", success=True)

    assert adapter.stopped == [("session-602", False)]
    assert result.payload["status"] == "completed"


def test_start_failure_maps_dependency_errors_to_existing_contract(tmp_path: Path) -> None:
    adapter = FakeRuntimeAdapter()
    adapter.raise_on_start = CaptureDependencyError("missing ffmpeg")
    service = _service(tmp_path, adapter)
    service.session_create("session-603", "2026-03-06")

    with pytest.raises(SessionCommandError) as exc:
        service.capture_start("session-603")

    assert exc.value.code == "CAPTURE_DEPENDENCY_ERROR"
    assert exc.value.exit_code == 2


def test_stop_failure_maps_interruption_to_existing_contract(tmp_path: Path) -> None:
    adapter = FakeRuntimeAdapter()
    adapter.raise_on_stop = CaptureInterruptedError("interrupted")
    service = _service(tmp_path, adapter)
    service.session_create("session-604", "2026-03-06")
    service.capture_start("session-604")

    with pytest.raises(SessionCommandError) as exc:
        service.capture_stop("session-604", success=True)

    assert exc.value.code == "CAPTURE_INTERRUPTED"
    assert exc.value.exit_code == 6


def test_start_failure_maps_permission_to_existing_contract(tmp_path: Path) -> None:
    adapter = FakeRuntimeAdapter()
    adapter.raise_on_start = CapturePermissionError("permission denied")
    service = _service(tmp_path, adapter)
    service.session_create("session-605", "2026-03-06")

    with pytest.raises(SessionCommandError) as exc:
        service.capture_start("session-605")

    assert exc.value.code == "CAPTURE_PERMISSION_DENIED"
    assert exc.value.exit_code == 5
