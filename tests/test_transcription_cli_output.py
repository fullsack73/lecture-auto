from pathlib import Path

from lecture_auto.cli_output import format_command_error, format_command_output
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService
from lecture_auto.stt_config import STTConfig


def _service(tmp_path: Path) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(
        store=store,
        stt_config=STTConfig(mode="api", api_provider="fake", api_key="k"),
    )


def test_transcription_text_output_shows_stages_attempt_and_path(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-1101", "2026-03-06")
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")
    service.import_audio("session-1101", str(source))

    result = service.transcribe_session("session-1101")
    rendered = format_command_output(result)

    assert "Transcription Completed" in rendered
    assert "Stages: preflight_checks -> mode_provider_initialization -> transcription_in_progress -> file_write_complete" in rendered
    assert "Attempt:" in rendered
    assert "Transcript Path: transcripts/session-1101-raw.md" in rendered


def test_transcription_json_output_is_single_line_and_contains_progress_payload(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-1102", "2026-03-06")
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")
    service.import_audio("session-1102", str(source))

    result = service.transcribe_session("session-1102")
    json_line = format_command_output(result, as_json=True)

    assert "\n" not in json_line
    assert '"command":"transcription run"' in json_line
    assert '"transcription_progress"' in json_line


def test_transcription_error_output_remains_actionable_for_category_errors() -> None:
    error = SessionCommandError(
        code="TRANSCRIPTION_NETWORK_TRANSIENT_ERROR",
        message="Transient network/provider failure during transcription.",
        guidance="Retry later or verify provider/network availability.",
        exit_code=4,
    )

    rendered = format_command_error("transcription run", error)

    assert "Command Failed" in rendered
    assert "transcription run" in rendered
    assert "Retry later or verify provider/network availability." in rendered
    assert "Exit Code: 4" in rendered
