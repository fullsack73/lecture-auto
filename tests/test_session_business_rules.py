from pathlib import Path

import pytest

from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


def _service(tmp_path: Path) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(store)


def test_valid_lifecycle_transitions_persist_completed_status(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service.session_create("session-200", "2026-03-06", title="Linear Algebra", course="MATH101")
    service.capture_start("session-200", "recordings/session-200.wav")
    stop_result = service.capture_stop("session-200", success=True)

    assert stop_result.payload["status"] == "completed"
    assert "recording_completed_at" in stop_result.payload["timestamps"]


def test_invalid_transition_is_rejected_with_actionable_message(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-201", "2026-03-06")

    with pytest.raises(SessionCommandError) as exc:
        service.capture_stop("session-201", success=True)

    assert exc.value.code == "INVALID_TRANSITION"
    assert "create -> start -> stop" in exc.value.guidance
    assert exc.value.exit_code == 1


@pytest.mark.parametrize(
    ("failure_kind", "expected_code", "expected_exit"),
    [
        ("dependency", "CAPTURE_DEPENDENCY_ERROR", 2),
        ("device", "CAPTURE_DEVICE_ERROR", 3),
        ("runtime", "CAPTURE_RUNTIME_ERROR", 4),
    ],
)
def test_failure_mapping_returns_expected_error_contract(
    tmp_path: Path,
    failure_kind: str,
    expected_code: str,
    expected_exit: int,
) -> None:
    service = _service(tmp_path)

    mapped = service.map_capture_failure(failure_kind)

    assert mapped.code == expected_code
    assert mapped.exit_code == expected_exit
    assert mapped.guidance


def test_status_persistence_and_detail_lookup_after_start(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-202", "2026-03-07", title="Physics", course="PHY101")

    start_result = service.capture_start("session-202", "recordings/session-202.wav")
    detail_result = service.session_detail("session-202")

    assert start_result.payload["status"] == "recording"
    assert detail_result.payload["status"] == "recording"
    assert detail_result.payload["audio_file_path"] == "recordings/session-202.wav"


def test_create_without_title_or_course_marks_naming_pending(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.session_create("session-203", "2026-03-08", title=None, course=None)

    assert created.payload["naming_pending"] is True
    assert created.payload["title"] is None
    assert created.payload["course"] is None


def test_output_contract_supports_plain_text_and_one_line_json(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = service.session_create("session-204", "2026-03-09")
    json_line = created.as_json_line()

    assert "\n" not in json_line
    assert created.as_text() == "Session 'session-204' created and ready to record."
    assert '"command":"session create"' in json_line


def test_import_audio_requires_supported_extension_and_updates_job_lifecycle(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-205", "2026-03-09")
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")

    result = service.import_audio("session-205", str(source))

    assert result.payload["job_status"] == "succeeded"
    assert result.payload["job_attempts"] == 1
    assert result.payload["progress"]["current_stage"] == "succeeded"
    assert result.payload["audio_file_path"] == "recordings/session-205-imported.wav"


def test_import_audio_rejects_unsupported_extension_with_actionable_error(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-206", "2026-03-09")
    source = tmp_path / "sample.m4a"
    source.write_bytes(b"m4a")

    with pytest.raises(SessionCommandError) as exc:
        service.import_audio("session-206", str(source))

    assert exc.value.code == "UNSUPPORTED_AUDIO_FORMAT"
    assert "Use a .wav or .mp3 file" in exc.value.guidance


def test_import_audio_rejects_duplicate_source_for_same_session(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-207", "2026-03-09")
    source = tmp_path / "sample.mp3"
    source.write_bytes(b"mp3")
    service.import_audio("session-207", str(source))

    with pytest.raises(SessionCommandError) as exc:
        service.import_audio("session-207", str(source))

    assert exc.value.code == "DUPLICATE_AUDIO_IMPORT"


def test_retry_import_audio_allows_failed_jobs_only_and_caps_attempts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-208", "2026-03-09")
    source = tmp_path / "missing.wav"

    failed = service.import_audio("session-208", str(source))
    assert failed.payload["job_status"] == "failed"

    source.write_bytes(b"wav")
    retried = service.retry_import_audio("session-208")
    assert retried.command == "audio import retry"
    assert retried.payload["job_attempts"] == 2
    assert retried.payload["job_status"] == "succeeded"

    with pytest.raises(SessionCommandError) as exc:
        service.retry_import_audio("session-208")
    assert exc.value.code == "IMPORT_RETRY_NOT_ALLOWED"


def test_retry_import_audio_rejects_when_attempts_reach_limit(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.session_create("session-209", "2026-03-09")
    session = created.payload
    session["job_status"] = "failed"
    session["job_attempts"] = 3
    session["import_source_audio_path"] = str((tmp_path / "sample.wav").as_posix())
    service.store.upsert(session)

    with pytest.raises(SessionCommandError) as exc:
        service.retry_import_audio("session-209")

    assert exc.value.code == "IMPORT_RETRY_LIMIT_EXCEEDED"
