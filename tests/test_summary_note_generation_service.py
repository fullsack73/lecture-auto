from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lecture_auto.llm_adapter import LLMProviderAdapter
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService


def _build_service(tmp_path: Path) -> tuple[SessionService, MagicMock]:
    metadata_file = tmp_path / "metadata" / "sessions.json"
    store = SessionMetadataStore(metadata_file=metadata_file)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)

    session_new = {
        "session_id": "session-new",
        "date": "2026-03-08",
        "title": "New Session",
        "course": "COURSE-2",
        "status": "completed",
        "transcript_file_path": "transcripts/session-new-raw.md",
        "timestamps": {"created_at": "2026-03-08T00:00:00+00:00"},
        "naming_pending": False,
    }
    session_old = {
        "session_id": "session-old",
        "date": "2026-03-07",
        "title": "Old Session",
        "course": "COURSE-1",
        "status": "completed",
        "transcript_file_path": "transcripts/session-old-raw.md",
        "timestamps": {"created_at": "2026-03-07T00:00:00+00:00"},
        "naming_pending": False,
    }

    store.upsert(session_old)
    store.upsert(session_new)

    transcript_dir = metadata_file.parent.parent / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / "session-new-raw.md").write_text("new raw transcript", encoding="utf-8")
    (transcript_dir / "session-old-raw.md").write_text("old raw transcript", encoding="utf-8")

    llm_adapter = MagicMock(spec=LLMProviderAdapter)
    llm_adapter.generate_notes.return_value = "generated notes"

    return SessionService(store=store, llm_adapter=llm_adapter), llm_adapter


def test_summarize_defaults_to_most_recent_session(tmp_path: Path) -> None:
    service, llm_adapter = _build_service(tmp_path)

    result = service.summarize_session(session_reference="", preview=True)

    assert result.command == "summarize"
    assert result.payload["session_id"] == "session-new"
    assert result.payload["template"] == "structured-notes"
    llm_adapter.generate_notes.assert_called_once()
    assert llm_adapter.generate_notes.call_args.kwargs["transcript"] == "new raw transcript"
    assert "## Topic Overview" in llm_adapter.generate_notes.call_args.kwargs["template"]


def test_summarize_id_targets_specific_session(tmp_path: Path) -> None:
    service, llm_adapter = _build_service(tmp_path)

    result = service.summarize_session(session_reference="session-old", preview=True)

    assert result.payload["session_id"] == "session-old"
    assert llm_adapter.generate_notes.call_args.kwargs["transcript"] == "old raw transcript"


@pytest.mark.parametrize("reference", ["session-new", "New Session"])
def test_summarize_preview_returns_notes_without_writing_file(
    tmp_path: Path,
    reference: str,
) -> None:
    service, _ = _build_service(tmp_path)

    result = service.summarize_session(session_reference=reference, preview=True)

    assert result.message == "generated notes"
    assert result.payload["preview"] is True
    note_path = tmp_path / "notes" / "course-2" / "session-new.md"
    assert not note_path.exists()


def test_summarize_save_writes_and_overwrites_note_file(tmp_path: Path) -> None:
    service, llm_adapter = _build_service(tmp_path)
    llm_adapter.generate_notes.side_effect = ["first notes", "second notes"]

    first = service.summarize_session(session_reference="session-old", preview=False)
    second = service.summarize_session(session_reference="session-old", preview=False)

    assert first.payload["note_file_path"] == "notes/course-1/session-old.md"
    assert second.payload["note_file_path"] == "notes/course-1/session-old.md"

    note_path = tmp_path / "notes" / "course-1" / "session-old.md"
    assert note_path.exists()
    assert note_path.read_text(encoding="utf-8") == "second notes"


def test_save_reuses_preview_once_and_writes_identical_notes(tmp_path):
    service, adapter = _build_service(tmp_path)
    preview = service.summarize_session("session-new", preview=True)
    saved = service.summarize_session("session-new")
    assert adapter.generate_notes.call_count == 1
    assert (tmp_path / saved.payload["note_file_path"]).read_text() == preview.payload["notes"]
    service.summarize_session("session-new")
    assert adapter.generate_notes.call_count == 2


@pytest.mark.parametrize("changed", ["transcript", "title", "course", "material", "model", "language", "template"])
def test_preview_invalidated_when_inputs_change(tmp_path, monkeypatch, changed):
    from lecture_auto.llm_config import LLMConfig
    service, adapter = _build_service(tmp_path)
    adapter.config = LLMConfig(provider="ollama")
    session = service.store.get_by_session_id("session-new")
    material = tmp_path / "materials/session-new.pdf"
    material.parent.mkdir(exist_ok=True)
    material.write_bytes(b"first PDF")
    session["material_file_path"] = "materials/session-new.pdf"
    service.store.upsert(session)
    service.summarize_session("session-new", preview=True)
    if changed == "transcript":
        (tmp_path / service.store.get_by_session_id("session-new")["transcript_file_path"]).write_text("changed")
    elif changed in ("title", "course"):
        session[changed] = "changed"
        service.store.upsert(session)
    elif changed == "material":
        material.write_bytes(b"other PDF")
    elif changed in ("model", "language"):
        setattr(adapter.config, "model_name" if changed == "model" else "language", "changed")
    else:
        monkeypatch.setattr(service, "_resolve_note_template", lambda _: ("structured-notes", "changed template"))
    service.summarize_session("session-new")
    assert adapter.generate_notes.call_count == 2


def test_failed_or_canceled_preview_cannot_be_saved_from_cache(tmp_path):
    from lecture_auto.session_service import SessionCommandError
    from lecture_auto.tasking import CancellationToken, TaskCancelledError
    service, adapter = _build_service(tmp_path)
    service.summarize_session("session-new", preview=True)
    adapter.generate_notes.side_effect = RuntimeError("failed")
    with pytest.raises(SessionCommandError):
        service.summarize_session("session-new", preview=True)
    assert not service._note_previews
    token = CancellationToken()
    def cancel(**kwargs):
        token.cancel()
        return "canceled notes"
    adapter.generate_notes.side_effect = cancel
    with pytest.raises(TaskCancelledError):
        service.summarize_session("session-new", preview=True, cancellation_token=token)
    assert not service._note_previews
    adapter.generate_notes.side_effect = None
    service.summarize_session("session-new")
    assert adapter.generate_notes.call_count == 4


def test_preview_cache_keeps_only_eight_sessions(tmp_path):
    service, adapter = _build_service(tmp_path)
    original = service.store.get_by_session_id("session-new")
    for i in range(9):
        relative = f"transcripts/s-{i}-raw.md"
        (tmp_path / relative).write_text("synthetic lecture")
        service.store.upsert({**original, "session_id": f"s-{i}", "transcript_file_path": relative})
        service.summarize_session(f"s-{i}", preview=True)
    assert len(service._note_previews) == 8
    assert "s-0" not in service._note_previews
