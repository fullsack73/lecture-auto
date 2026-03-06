from pathlib import Path

import pytest

from lecture_auto.session_metadata_store import SessionMetadataStore, SessionMetadataValidationError


def _base_session(session_id: str, date: str) -> dict:
    return {
        "session_id": session_id,
        "date": date,
        "title": "OS",
        "course": "CS201",
        "status": "idle",
        "audio_file_path": f"recordings/{session_id}.wav",
        "timestamps": {"created_at": date},
        "naming_pending": False,
    }


def test_build_raw_transcript_path_is_deterministic_and_session_scoped(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")

    path = store.build_raw_transcript_path("session-901")

    assert path == "transcripts/session-901-raw.md"


def test_transcript_path_validation_rejects_paths_not_scoped_to_session(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    row = _base_session("session-902", "2026-03-06")
    row["transcript_file_path"] = "transcripts/other-session-raw.md"

    with pytest.raises(
        SessionMetadataValidationError,
        match=r"transcripts/\{session_id\}-raw\.\* convention",
    ):
        store.upsert(row)


def test_upsert_accepts_transcription_tracking_fields_with_expected_types(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    row = _base_session("session-903", "2026-03-06")
    row["transcript_file_path"] = "transcripts/session-903-raw.md"
    row["transcription_status"] = "succeeded"
    row["transcription_error_category"] = None
    row["transcription_retry_count"] = 1

    saved = store.upsert(row)

    assert saved["transcript_file_path"] == "transcripts/session-903-raw.md"
    assert saved["transcription_status"] == "succeeded"
    assert saved["transcription_retry_count"] == 1


def test_upsert_rejects_negative_transcription_retry_count(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    row = _base_session("session-904", "2026-03-06")
    row["transcription_retry_count"] = -1

    with pytest.raises(SessionMetadataValidationError, match="transcription_retry_count"):
        store.upsert(row)
