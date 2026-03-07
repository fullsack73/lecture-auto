"""Gap analysis and end-to-end simulation tests for Transcript Refinement (Task Group 3)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService, SessionCommandError
from lecture_auto.llm_config import LLMConfig

import sys
mock_google = MagicMock()
mock_genai = MagicMock()
mock_google.genai = mock_genai
sys.modules['google'] = mock_google
sys.modules['google.genai'] = mock_genai

from lecture_auto.llm_adapter import GeminiLLMAdapter


@pytest.fixture
def store(tmp_path: Path) -> SessionMetadataStore:
    metadata_file = tmp_path / "metadata" / "sessions.jsonl"
    store = SessionMetadataStore(metadata_file=metadata_file)
    store.metadata_file.parent.mkdir(parents=True)
    return store


def test_end_to_end_refinement_chunking(store: SessionMetadataStore) -> None:
    mock_genai.reset_mock()
    # Set up session without edited transcript initially
    session = {
        "session_id": "long-session-1",
        "date": "2026-03-01",
        "title": "Long Lecture",
        "course": "CS102",
        "status": "completed",
        "transcript_file_path": "transcripts/long-session-1-raw.md",
        "timestamps": {"created_at": "2026-03-01T12:00:00Z"},
        "naming_pending": False,
    }
    with store.metadata_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps([session]))
    
    transcripts_dir = store.metadata_file.parent.parent / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    raw_path = transcripts_dir / "long-session-1-raw.md"
    
    # Create a string longer than chunk size (4000)
    long_word = "Word " * 1000  # 5000 characters
    raw_path.write_text(long_word)
    
    # Configure the mock adapter
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Refined Mock Output Chunk"
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client_instance
    
    config = LLMConfig(api_key="valid", chunk_size=4000)
    adapter = GeminiLLMAdapter(config)
    service = SessionService(store=store, llm_adapter=adapter)
    
    result = service.transcript_refine("long-session-1")
    
    # Since text is ~5000 chars, it should be chunked into 2 calls
    assert mock_client_instance.models.generate_content.call_count == 2
    
    edited_path = transcripts_dir / "long-session-1-edited.md"
    assert edited_path.exists()
    assert "Refined Mock Output Chunk\nRefined Mock Output Chunk" in edited_path.read_text()
    assert result.payload["target_used"] == "raw"


def test_refine_missing_transcript_raises_error(store: SessionMetadataStore) -> None:
    session = {
        "session_id": "missing-session",
        "date": "2026-03-01",
        "title": "Missing Lecture",
        "course": "CS102",
        "status": "completed",
        "transcript_file_path": "transcripts/missing-session-raw.md",
        "timestamps": {"created_at": "2026-03-01T12:00:00Z"},
        "naming_pending": False,
    }
    with store.metadata_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps([session]))

    adapter = MagicMock()
    service = SessionService(store=store, llm_adapter=adapter)

    with pytest.raises(SessionCommandError, match="missing") as excinfo:
        service.transcript_refine("missing-session")
    
    assert excinfo.value.code == "TRANSCRIPT_FILE_MISSING"


def test_refine_empty_transcript_raises_error(store: SessionMetadataStore) -> None:
    session = {
        "session_id": "empty-session",
        "date": "2026-03-01",
        "title": "Empty Lecture",
        "course": "CS102",
        "status": "completed",
        "transcript_file_path": "transcripts/empty-session-raw.md",
        "timestamps": {"created_at": "2026-03-01T12:00:00Z"},
        "naming_pending": False,
    }
    with store.metadata_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps([session]))

    transcripts_dir = store.metadata_file.parent.parent / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    raw_path = transcripts_dir / "empty-session-raw.md"
    raw_path.write_text("   ")

    adapter = MagicMock()
    service = SessionService(store=store, llm_adapter=adapter)

    with pytest.raises(SessionCommandError, match="empty") as excinfo:
        service.transcript_refine("empty-session")
    
    assert excinfo.value.code == "TRANSCRIPT_EMPTY"
