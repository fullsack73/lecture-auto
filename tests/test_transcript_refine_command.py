"""Focused tests for Refinement Service and Commands (Task Group 2)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService, CommandResult, SessionCommandError
from lecture_auto.llm_adapter import LLMProviderAdapter, LLMConfigError, LLMProviderAuthError, LLMTransientNetworkError
from lecture_auto.cli_output import format_command_output

@pytest.fixture
def store(tmp_path: Path) -> SessionMetadataStore:
    metadata_file = tmp_path / "metadata" / "sessions.jsonl"
    return SessionMetadataStore(metadata_file=metadata_file)

@pytest.fixture
def llm_adapter() -> MagicMock:
    adapter = MagicMock(spec=LLMProviderAdapter)
    adapter.refine_transcript.return_value = "Refined Mock Output"
    return adapter

@pytest.fixture
def service(store: SessionMetadataStore, llm_adapter: MagicMock) -> SessionService:
    store.metadata_file.parent.mkdir(parents=True)
    session = {
        "session_id": "test-session-1",
        "date": "2026-03-01",
        "title": "Introduction to AI",
        "course": "CS101",
        "status": "completed",
        "transcript_file_path": "transcripts/cs101/test-session-1-raw.md",
        "timestamps": {"created_at": "2026-03-01T12:00:00Z"},
        "naming_pending": False,
    }
    with store.metadata_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps([session]))
    
    (store.metadata_file.parent.parent / "transcripts" / "cs101").mkdir(parents=True)
    raw_path = store.metadata_file.parent.parent / "transcripts/cs101/test-session-1-raw.md"
    raw_path.write_text("Hello, this  is a raw transcript... It needs    refinement.")

    return SessionService(store=store, llm_adapter=llm_adapter)


def test_refine_falls_back_to_raw_when_edited_missing(service: SessionService) -> None:
    result = service.transcript_refine("test-session-1")
    
    assert result.command == "transcript refine"
    assert result.payload["target_used"] == "raw"
    service.llm_adapter.refine_transcript.assert_called_once_with(
        "Hello, this  is a raw transcript... It needs    refinement.",
        context_topic="Introduction to AI"
    )
    
    transcripts_dir = service.store.metadata_file.parent.parent / "transcripts" / "cs101"
    assert (transcripts_dir / "test-session-1-edited.md").exists()
    assert (transcripts_dir / "test-session-1-edited.md").read_text() == "Refined Mock Output"


def test_refine_uses_edited_when_present(service: SessionService) -> None:
    transcripts_dir = service.store.metadata_file.parent.parent / "transcripts" / "cs101"
    edited_path = transcripts_dir / "test-session-1-edited.md"
    edited_path.write_text("This is an existing edited transcript.")

    result = service.transcript_refine("test-session-1")
    
    assert result.payload["target_used"] == "edited"
    service.llm_adapter.refine_transcript.assert_called_once_with(
        "This is an existing edited transcript.",
        context_topic="Introduction to AI"
    )
    assert edited_path.read_text() == "Refined Mock Output"


def test_refine_forces_raw_with_flag_even_if_edited_present(service: SessionService) -> None:
    transcripts_dir = service.store.metadata_file.parent.parent / "transcripts" / "cs101"
    edited_path = transcripts_dir / "test-session-1-edited.md"
    edited_path.write_text("This is an existing edited transcript.")

    result = service.transcript_refine("test-session-1", raw=True)
    
    assert result.payload["target_used"] == "raw"
    service.llm_adapter.refine_transcript.assert_called_once_with(
        "Hello, this  is a raw transcript... It needs    refinement.",
        context_topic="Introduction to AI"
    )
    assert edited_path.read_text() == "Refined Mock Output"


def test_refine_handles_llm_network_error(service: SessionService) -> None:
    service.llm_adapter.refine_transcript.side_effect = LLMTransientNetworkError("Network down")
    
    with pytest.raises(SessionCommandError, match="Network down") as exc_info:
        service.transcript_refine("test-session-1")

    assert exc_info.value.code == "LLM_NETWORK_ERROR"


def test_refine_cli_formatting() -> None:
    result = CommandResult(
        command="transcript refine",
        payload={"session_id": "test-session-99", "target_used": "edited"},
        message="Transcript successfully refined from edited source."
    )
    output = format_command_output(result)
    assert "Transcript Refinement" in output
    assert "- Session ID: test-session-99" in output
    assert "- Source Target: edited" in output
    assert "- Result: Transcript successfully refined from edited source." in output

def test_refine_uses_raw_when_raw_is_newer(service: SessionService) -> None:
    transcripts_dir = service.store.metadata_file.parent.parent / "transcripts" / "cs101"
    edited_path = transcripts_dir / "test-session-1-edited.md"
    edited_path.write_text("This is an existing edited transcript.")
    
    # Overwrite raw to be newer than edited
    import time
    time.sleep(0.01)
    raw_path = transcripts_dir / "test-session-1-raw.md"
    raw_path.write_text("This is the new raw transcript that is newer.")

    result = service.transcript_refine("test-session-1")
    
    assert result.payload["target_used"] == "raw"
    service.llm_adapter.refine_transcript.assert_called_once_with(
        "This is the new raw transcript that is newer.",
        context_topic="Introduction to AI"
    )
    assert edited_path.read_text() == "Refined Mock Output"
