from pathlib import Path

import pytest

from lecture_auto.session_metadata_store import (
    SessionMetadataStore,
    SessionMetadataValidationError,
)


def _base_session(session_id: str, date: str) -> dict:
    return {
        "session_id": session_id,
        "date": date,
        "title": "Databases",
        "course": "CS301",
        "status": "idle",
        "audio_file_path": None,
        "timestamps": {"created_at": date},
        "naming_pending": False,
    }


def test_build_recording_path_uses_session_id_only(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")

    path = store.build_recording_path("session-500")

    assert path == "recordings/session-500.wav"


def test_upsert_rejects_audio_path_not_matching_session_id(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    session = _base_session("session-501", "2026-03-06")
    session["audio_file_path"] = "recordings/other-session.wav"

    with pytest.raises(SessionMetadataValidationError, match=r"recordings/\{session_id\}\.\* convention"):
        store.upsert(session)


def test_capture_start_stop_style_updates_keep_consistent_audio_path(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    session = _base_session("session-502", "2026-03-06")

    started = dict(session)
    started["status"] = "recording"
    started["audio_file_path"] = store.build_recording_path("session-502")
    started["timestamps"] = {"created_at": "2026-03-06", "recording_started_at": "2026-03-06T10:00:00Z"}
    store.upsert(started)

    completed = dict(started)
    completed["status"] = "completed"
    completed["timestamps"] = {
        "created_at": "2026-03-06",
        "recording_started_at": "2026-03-06T10:00:00Z",
        "recording_completed_at": "2026-03-06T11:00:00Z",
    }
    saved = store.upsert(completed)

    assert saved["audio_file_path"] == "recordings/session-502.wav"
    assert saved["status"] == "completed"
    detail = store.get_by_session_id("session-502")
    assert detail is not None
    assert detail["audio_file_path"] == "recordings/session-502.wav"


def test_replace_failure_does_not_corrupt_existing_capture_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "config" / "sessions.json"
    store = SessionMetadataStore(target)

    existing = _base_session("session-503", "2026-03-06")
    existing["status"] = "recording"
    existing["audio_file_path"] = "recordings/session-503.wav"
    store.upsert(existing)

    updated = dict(existing)
    updated["status"] = "completed"

    def _raise_replace_error(_: str, __: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("lecture_auto.session_metadata_store.os.replace", _raise_replace_error)

    with pytest.raises(OSError, match="replace failed"):
        store.upsert(updated)

    preserved = store.get_by_session_id("session-503")
    assert preserved is not None
    assert preserved["status"] == "recording"
