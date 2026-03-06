from pathlib import Path

import pytest

from lecture_auto.session_metadata_store import (
    SessionMetadataStore,
    SessionMetadataValidationError,
)


def _build_session(session_id: str, date: str) -> dict:
    return {
        "session_id": session_id,
        "date": date,
        "title": "Intro to AI",
        "course": "CS101",
        "status": "idle",
        "audio_file_path": None,
        "timestamps": {"created_at": date},
        "naming_pending": False,
    }


def test_schema_validation_rejects_missing_required_fields(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")

    with pytest.raises(SessionMetadataValidationError, match="Missing required fields"):
        store.upsert({"session_id": "s-001"})


def test_upsert_persists_deterministic_payload_and_roundtrips(tmp_path: Path) -> None:
    target = tmp_path / "config" / "sessions.json"
    store = SessionMetadataStore(target)
    session = _build_session("session-001", "2026-03-06")

    saved = store.upsert(session)
    loaded = store.load_all()

    assert saved["session_id"] == "session-001"
    assert saved["date"] == "2026-03-06"
    assert loaded == [saved]

    # Key order is deterministic to keep snapshot-style assertions stable.
    assert target.read_text(encoding="utf-8") == (
        '[{"session_id":"session-001","date":"2026-03-06","title":"Intro to AI",'
        '"course":"CS101","status":"idle","audio_file_path":null,'
        '"timestamps":{"created_at":"2026-03-06"},"naming_pending":false}]'
    )


def test_safe_write_preserves_existing_file_when_replace_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "config" / "sessions.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        '[{"session_id":"session-old","date":"2026-03-01","title":null,'
        '"course":null,"status":"completed","audio_file_path":null,'
        '"timestamps":{"created_at":"2026-03-01"},"naming_pending":true}]',
        encoding="utf-8",
    )

    store = SessionMetadataStore(target)

    def _raise_replace_error(_: str, __: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("lecture_auto.session_metadata_store.os.replace", _raise_replace_error)

    with pytest.raises(OSError, match="replace failed"):
        store.upsert(_build_session("session-002", "2026-03-07"))

    # Existing file content remains unchanged when atomic swap fails.
    assert store.load_all()[0]["session_id"] == "session-old"


def test_list_recent_first_returns_descending_date_order(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    store.upsert(_build_session("session-001", "2026-03-05"))
    store.upsert(_build_session("session-002", "2026-03-07"))
    store.upsert(_build_session("session-003", "2026-03-06"))

    session_ids = [row["session_id"] for row in store.list_recent_first()]
    assert session_ids == ["session-002", "session-003", "session-001"]


def test_get_by_session_id_returns_matching_session(tmp_path: Path) -> None:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    store.upsert(_build_session("session-111", "2026-03-08"))

    found = store.get_by_session_id("session-111")
    missing = store.get_by_session_id("not-found")

    assert found is not None
    assert found["session_id"] == "session-111"
    assert missing is None
