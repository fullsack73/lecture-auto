import os
from unittest.mock import patch, MagicMock
from lecture_auto.session_service import SessionService, CommandResult
from lecture_auto.session_metadata_store import SessionMetadataStore

def test_transcript_search_finds_session(tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    
    # Pre-populate store
    service.session_create("sess-1", "2026-03-07", title="Math 101", course="Math")
    service.session_create("sess-2", "2026-03-08", title="History 101", course="History")
    
    result = service.transcript_search("Math")
    assert result.command == "transcript search"
    assert len(result.payload["matches"]) == 1
    assert result.payload["matches"][0]["title"] == "Math 101"

@patch("lecture_auto.session_service.typer.launch")
def test_transcript_open_creates_edited_if_modified(mock_launch, tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    
    # Create session with transcript
    service.session_create("sess-1", "2026-03-07", title="Math 101", course="Math")
    
    # Mock files
    transcript_path = tmp_path / "transcripts" / "sess-1-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("Hello Math!", encoding="utf-8")
    
    # Update store to have the transcript
    sess = store.get_by_session_id("sess-1")
    sess["transcript_file_path"] = f"transcripts/{transcript_path.name}"
    store.upsert(sess)

    # Set up mock payload for `typer.launch` that simulates an edit
    def mock_launch_side_effect(filepath, wait):
        assert wait is True
        # Simulate user changing the file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("Hello Math Edited!")

    mock_launch.side_effect = mock_launch_side_effect

    # Set CWD to tmp_path so it resolves properly
    with patch("lecture_auto.session_service.Path.cwd", return_value=tmp_path):
        result = service.transcript_open("Math 101")
        
        # Verify result and files
        assert result.command == "transcript open"
        assert result.payload["session_id"] == "sess-1"
        assert result.payload["state"] == "edited"
        
        # Verify edited.md exists and raw.md is untouched
        edited_path = tmp_path / "transcripts" / "sess-1-edited.md"
        assert edited_path.exists()
        assert edited_path.read_text(encoding="utf-8") == "Hello Math Edited!"
        assert transcript_path.read_text(encoding="utf-8") == "Hello Math!"

@patch("lecture_auto.session_service.typer.launch")
def test_transcript_open_no_save_if_unmodified(mock_launch, tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    
    # Create session with transcript
    service.session_create("sess-1", "2026-03-07", title="Math 101", course="Math")
    
    transcript_path = tmp_path / "transcripts" / "sess-1-raw.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("Hello Math!", encoding="utf-8")
    
    sess = store.get_by_session_id("sess-1")
    sess["transcript_file_path"] = f"transcripts/{transcript_path.name}"
    store.upsert(sess)

    def mock_launch_side_effect(filepath, wait):
        # Do not modify the file
        pass

    mock_launch.side_effect = mock_launch_side_effect

    with patch("lecture_auto.session_service.Path.cwd", return_value=tmp_path):
        result = service.transcript_open("sess-1")
        
        assert result.command == "transcript open"
        assert result.payload["state"] == "unmodified"
        
        edited_path = tmp_path / "transcripts" / "sess-1-edited.md"
        assert not edited_path.exists()

def test_transcript_search_no_matches(tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    
    service.session_create("sess-1", "2026-03-07", title="Math 101", course="Math")
    
    result = service.transcript_search("Science")
    assert result.command == "transcript search"
    assert len(result.payload["matches"]) == 0

from lecture_auto.session_service import SessionCommandError
import pytest

def test_transcript_open_session_not_found(tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    
    with pytest.raises(SessionCommandError, match="not found"):
        service.transcript_open("sess-ghost")

def test_transcript_open_no_transcript_attached(tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    service.session_create("no-trans-sess", "2026-03-07", title="Math", course="Math")
    
    with pytest.raises(SessionCommandError, match="No transcript found"):
        service.transcript_open("no-trans-sess")

def test_transcript_open_file_missing_on_disk(tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    service.session_create("sess-1", "2026-03-07", title="Math", course="Math")
    
    sess = store.get_by_session_id("sess-1")
    sess["transcript_file_path"] = "transcripts/ghost-raw.md"
    store.upsert(sess)
    
    with pytest.raises(SessionCommandError, match="Transcript file missing"):
        service.transcript_open("sess-1")

@patch("lecture_auto.session_service.typer.launch")
def test_transcript_open_updates_existing_edited_md(mock_launch, tmp_path):
    store_file = tmp_path / "metadata.json"
    store = SessionMetadataStore(store_file)
    service = SessionService(store)
    service.session_create("sess-1", "2026-03-07", title="Math 101", course="Math")
    
    transcript_path = tmp_path / "transcripts" / "sess-1-raw.md"
    edited_path = tmp_path / "transcripts" / "sess-1-edited.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("Hello Math Raw!", encoding="utf-8")
    edited_path.write_text("Hello Math Edited V1!", encoding="utf-8")
    
    sess = store.get_by_session_id("sess-1")
    sess["transcript_file_path"] = f"transcripts/{transcript_path.name}"
    store.upsert(sess)

    def mock_launch_side_effect(filepath, wait):
        assert wait is True
        # Assert it opens the edited.md, not raw.md
        assert "edited" in str(filepath)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("Hello Math Edited V2!")

    mock_launch.side_effect = mock_launch_side_effect

    with patch("lecture_auto.session_service.Path.cwd", return_value=tmp_path):
        result = service.transcript_open("sess-1")
        assert result.command == "transcript open"
        assert result.payload["state"] == "edited"
        assert result.message == "Edited transcript for 'sess-1' updated."
        
        assert edited_path.read_text(encoding="utf-8") == "Hello Math Edited V2!"
        assert transcript_path.read_text(encoding="utf-8") == "Hello Math Raw!"
