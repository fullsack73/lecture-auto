from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lecture_auto.llm_adapter import (
    LLMProviderAdapter,
    LLMProviderAuthError,
    LLMTransientNetworkError,
)
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


def _base_session(session_id: str = "session-401") -> dict[str, object]:
    return {
        "session_id": session_id,
        "date": "2026-03-08",
        "title": "Algorithms",
        "course": "CS301",
        "status": "completed",
        "transcript_file_path": f"transcripts/{session_id}-raw.md",
        "timestamps": {"created_at": "2026-03-08T00:00:00+00:00"},
        "naming_pending": False,
    }


def _service_with_session(tmp_path: Path, session: dict[str, object]) -> tuple[SessionService, MagicMock]:
    metadata_file = tmp_path / "metadata" / "sessions.json"
    store = SessionMetadataStore(metadata_file=metadata_file)
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    store.upsert(session)

    llm_adapter = MagicMock(spec=LLMProviderAdapter)
    llm_adapter.generate_notes.return_value = "gap-analysis-notes"
    return SessionService(store=store, llm_adapter=llm_adapter), llm_adapter


def test_summarize_template_not_found_returns_command_error(tmp_path: Path) -> None:
    session = _base_session()
    service, _ = _service_with_session(tmp_path, session)
    transcript_path = tmp_path / "transcripts" / "session-401-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("transcript", encoding="utf-8")

    with pytest.raises(SessionCommandError) as exc:
        service.summarize_session(session_reference="session-401", template_name="missing-template")

    assert exc.value.code == "TEMPLATE_NOT_FOUND"


def test_summarize_llm_auth_error_is_propagated_with_mapped_code(tmp_path: Path) -> None:
    session = _base_session()
    service, llm_adapter = _service_with_session(tmp_path, session)
    llm_adapter.generate_notes.side_effect = LLMProviderAuthError("bad key")

    transcript_path = tmp_path / "transcripts" / "session-401-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("transcript", encoding="utf-8")

    with pytest.raises(SessionCommandError) as exc:
        service.summarize_session(session_reference="session-401", preview=True)

    assert exc.value.code == "LLM_AUTH_FAILED"
    assert "bad key" in exc.value.message


def test_summarize_llm_network_error_is_propagated_with_mapped_code(tmp_path: Path) -> None:
    session = _base_session()
    service, llm_adapter = _service_with_session(tmp_path, session)
    llm_adapter.generate_notes.side_effect = LLMTransientNetworkError("net down")

    transcript_path = tmp_path / "transcripts" / "session-401-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("transcript", encoding="utf-8")

    with pytest.raises(SessionCommandError) as exc:
        service.summarize_session(session_reference="session-401", preview=True)

    assert exc.value.code == "LLM_NETWORK_ERROR"


def test_summarize_id_for_session_with_no_transcript_fails(tmp_path: Path) -> None:
    session = _base_session("session-402")
    service, _ = _service_with_session(tmp_path, session)

    with pytest.raises(SessionCommandError) as exc:
        service.summarize_session(session_reference="session-402", preview=True)

    assert exc.value.code == "TRANSCRIPT_NOT_FOUND"


def test_summarize_overwrites_existing_note_file(tmp_path: Path) -> None:
    session = _base_session("session-403")
    service, llm_adapter = _service_with_session(tmp_path, session)
    llm_adapter.generate_notes.return_value = "updated content"

    transcript_path = tmp_path / "transcripts" / "session-403-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("transcript", encoding="utf-8")

    note_path = tmp_path / "notes" / "session-403.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text("old content", encoding="utf-8")

    service.summarize_session(session_reference="session-403", preview=False)

    assert note_path.read_text(encoding="utf-8") == "updated content"


def test_summarize_uses_custom_template_from_user_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _base_session("session-404")
    service, llm_adapter = _service_with_session(tmp_path, session)

    transcript_path = tmp_path / "transcripts" / "session-404-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("transcript", encoding="utf-8")

    fake_home = tmp_path / "home"
    user_template = fake_home / ".lecture_auto" / "templates" / "custom-format.md"
    user_template.parent.mkdir(parents=True, exist_ok=True)
    user_template.write_text("# custom-template", encoding="utf-8")
    monkeypatch.setattr("lecture_auto.session_service.Path.home", lambda: fake_home)

    service.summarize_session(session_reference="session-404", template_name="custom-format", preview=True)

    assert llm_adapter.generate_notes.call_args.kwargs["template"] == "# custom-template"


def test_summarize_prefers_edited_transcript_over_raw(tmp_path: Path) -> None:
    session = _base_session("session-405")
    service, llm_adapter = _service_with_session(tmp_path, session)

    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / "session-405-raw.md").write_text("raw version", encoding="utf-8")
    (transcript_dir / "session-405-edited.md").write_text("edited version", encoding="utf-8")

    result = service.summarize_session(session_reference="session-405", preview=True)

    assert result.payload["source_transcript"] == "edited"
    assert llm_adapter.generate_notes.call_args.kwargs["transcript"] == "edited version"
