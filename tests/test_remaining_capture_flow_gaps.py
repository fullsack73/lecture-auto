from pathlib import Path

import pytest

from lecture_auto.capture_runtime import CaptureDeviceError, CaptureHandle
from lecture_auto.cli_output import format_command_output
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


class IntegrationRuntimeAdapter:
    def __init__(self) -> None:
        self.active: dict[str, str] = {}
        self.raise_on_start: Exception | None = None

    def start_capture(self, session_id: str, output_path: str) -> CaptureHandle:
        if self.raise_on_start is not None:
            raise self.raise_on_start
        self.active[session_id] = output_path
        return CaptureHandle(session_id=session_id, output_path=output_path, process_id=9021, backend="integration")

    def stop_capture(self, session_id: str, *, interrupted: bool = False) -> None:
        self.active.pop(session_id, None)


def _service(tmp_path: Path, adapter: IntegrationRuntimeAdapter) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(store=store, runtime_adapter=adapter)


def test_end_to_end_create_start_stop_history_detail_with_runtime(tmp_path: Path) -> None:
    adapter = IntegrationRuntimeAdapter()
    service = _service(tmp_path, adapter)

    service.session_create("session-801", "2026-03-06")
    service.capture_start("session-801")
    stop_result = service.capture_stop("session-801", success=True)
    history = service.session_history()
    detail = service.session_detail("session-801")

    assert stop_result.payload["status"] == "completed"
    assert history.payload["sessions"][0]["session_id"] == "session-801"
    assert detail.payload["audio_file_path"] == "recordings/session-801.wav"


def test_capture_stop_failure_persists_failed_status_without_runtime_error(tmp_path: Path) -> None:
    adapter = IntegrationRuntimeAdapter()
    service = _service(tmp_path, adapter)

    service.session_create("session-802", "2026-03-06")
    service.capture_start("session-802")
    result = service.capture_stop("session-802", success=False)

    assert result.payload["status"] == "failed"
    assert "recording_failed_at" in result.payload["timestamps"]


def test_runtime_device_error_is_mapped_to_actionable_contract(tmp_path: Path) -> None:
    adapter = IntegrationRuntimeAdapter()
    adapter.raise_on_start = CaptureDeviceError("no audio device")
    service = _service(tmp_path, adapter)
    service.session_create("session-803", "2026-03-06")

    with pytest.raises(SessionCommandError) as exc:
        service.capture_start("session-803")

    assert exc.value.code == "CAPTURE_DEVICE_ERROR"
    assert exc.value.exit_code == 3


def test_history_and_detail_json_output_stays_one_line_after_runtime_flow(tmp_path: Path) -> None:
    adapter = IntegrationRuntimeAdapter()
    service = _service(tmp_path, adapter)
    service.session_create("session-804", "2026-03-06")
    service.capture_start("session-804")

    history_json = format_command_output(service.session_history(), as_json=True)
    detail_json = format_command_output(service.session_detail("session-804"), as_json=True)

    assert "\n" not in history_json
    assert "\n" not in detail_json
    assert '"command":"session history"' in history_json
    assert '"command":"session detail"' in detail_json
