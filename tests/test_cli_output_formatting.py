from pathlib import Path

from lecture_auto.cli_output import format_command_error, format_command_output
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService


def _service(tmp_path: Path) -> SessionService:
    return SessionService(SessionMetadataStore(tmp_path / "config" / "sessions.json"))


def test_success_text_template_for_session_create_is_readable(tmp_path: Path) -> None:
    service = _service(tmp_path)
    result = service.session_create("session-301", "2026-03-10")

    rendered = format_command_output(result)

    assert "Session Created" in rendered
    assert "Session ID: session-301" in rendered
    assert "Next: Run 'capture start session-301'" in rendered


def test_failure_text_template_is_actionable(tmp_path: Path) -> None:
    service = _service(tmp_path)

    error = service.map_capture_failure("device")
    rendered = format_command_error("capture start", error)

    assert "Command Failed" in rendered
    assert "capture start" in rendered
    assert "Next Action:" in rendered
    assert "Exit Code: 3" in rendered


def test_json_output_shape_is_standardized_and_one_line(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = service.session_create("session-302", "2026-03-10")

    json_line = format_command_output(created, as_json=True)

    assert "\n" not in json_line
    assert '"ok":true' in json_line
    assert '"command":"session create"' in json_line
    assert '"payload"' in json_line
    assert '"message"' in json_line


def test_history_output_provides_concise_scannable_rows(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-303", "2026-03-08", title="Calculus", course="MATH201")
    service.session_create("session-304", "2026-03-09", title="Physics", course="PHY201")

    history = service.session_history()
    rendered = format_command_output(history)

    assert "Session History (2 total)" in rendered
    assert "session-304" in rendered
    assert "session-303" in rendered
    assert "Next: Run 'session detail <session_id>'" in rendered


def test_detail_output_includes_complete_session_facts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-305", "2026-03-11", title="Chemistry", course="CHEM101")
    service.capture_start("session-305", "recordings/session-305.wav")

    detail = service.session_detail("session-305")
    rendered = format_command_output(detail)

    assert "Session Detail" in rendered
    assert "Session ID: session-305" in rendered
    assert "Status: recording" in rendered
    assert "Audio Path: recordings/session-305.wav" in rendered
    assert "Timestamps:" in rendered


def test_audio_import_output_includes_progress_summary_fields(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-306", "2026-03-11")
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")

    imported = service.import_audio("session-306", str(source))
    rendered = format_command_output(imported)

    assert "Audio Import Completed" in rendered
    assert "Current Stage: succeeded" in rendered
    assert "Final Status: succeeded" in rendered
    assert "Started At:" in rendered
    assert "Ended At:" in rendered
    assert "Attempt: 1/3" in rendered


def test_audio_import_retry_output_uses_retry_header(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-307", "2026-03-11")
    missing = tmp_path / "missing.wav"
    service.import_audio("session-307", str(missing))
    missing.write_bytes(b"wav")

    retried = service.retry_import_audio("session-307")
    rendered = format_command_output(retried)

    assert "Audio Import Retry Completed" in rendered
    assert "Attempt: 2/3" in rendered


def test_audio_import_json_output_remains_single_line_with_progress_payload(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-308", "2026-03-11")
    source = tmp_path / "sample.mp3"
    source.write_bytes(b"mp3")

    imported = service.import_audio("session-308", str(source))
    json_line = format_command_output(imported, as_json=True)

    assert "\n" not in json_line
    assert '"command":"audio import"' in json_line
    assert '"progress"' in json_line
