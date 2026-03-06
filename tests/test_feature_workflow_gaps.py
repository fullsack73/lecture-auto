from pathlib import Path

import pytest

from lecture_auto.cli_output import format_command_output
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


def _service(tmp_path: Path) -> SessionService:
    return SessionService(SessionMetadataStore(tmp_path / "config" / "sessions.json"))


def test_end_to_end_workflow_create_start_stop_history_detail(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.session_create("session-401", "2026-03-12")
    started = service.capture_start("session-401", "recordings/session-401.wav")
    stopped = service.capture_stop("session-401", success=True)
    history = service.session_history()
    detail = service.session_detail("session-401")

    assert created.payload["status"] == "idle"
    assert started.payload["status"] == "recording"
    assert stopped.payload["status"] == "completed"
    assert history.payload["sessions"][0]["session_id"] == "session-401"
    assert detail.payload["audio_file_path"] == "recordings/session-401.wav"


def test_interrupted_capture_persists_failed_status(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-402", "2026-03-12", title="Biology", course="BIO101")
    service.capture_start("session-402", "recordings/session-402.wav")

    failed = service.capture_stop("session-402", success=False)

    assert failed.payload["status"] == "failed"
    assert "recording_failed_at" in failed.payload["timestamps"]


def test_permission_denied_failure_mapping_is_actionable(tmp_path: Path) -> None:
    service = _service(tmp_path)

    mapped = service.map_capture_failure("permission")

    assert mapped.code == "CAPTURE_PERMISSION_DENIED"
    assert mapped.exit_code == 5
    assert "Grant microphone/system-audio permission" in mapped.guidance


def test_metadata_write_failures_are_mapped_to_user_friendly_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(tmp_path)

    def _raise_write_error(_: dict) -> dict:
        raise OSError("disk full")

    monkeypatch.setattr(service.store, "upsert", _raise_write_error)

    with pytest.raises(SessionCommandError) as exc:
        service.session_create("session-403", "2026-03-12")

    assert exc.value.code == "METADATA_WRITE_ERROR"
    assert exc.value.exit_code == 8
    assert "filesystem permissions" in exc.value.guidance


def test_json_history_and_detail_outputs_are_single_line_parseable(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-404", "2026-03-12")

    history_json = format_command_output(service.session_history(), as_json=True)
    detail_json = format_command_output(service.session_detail("session-404"), as_json=True)

    assert "\n" not in history_json
    assert "\n" not in detail_json
    assert '"ok":true' in history_json
    assert '"command":"session detail"' in detail_json
