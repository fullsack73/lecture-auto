import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService, SessionCommandError


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Path:
    config_dir = tmp_path / ".lecture_auto"
    config_dir.mkdir()
    sessions_file = config_dir / "sessions.json"
    sessions_file.write_text(
        json.dumps(
            [
                {
                    "session_id": "session-123",
                    "date": "2026-03-26",
                    "title": "Topic A",
                    "course": "Physics",
                    "status": "completed",
                    "transcript_file_path": "transcripts/Physics/session-123-raw.md",
                    "timestamps": {"created_at": "2026-03-26T10:00:00Z"},
                    "naming_pending": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path

def test_import_material_appends_to_existing_pdf(mock_workspace: Path, monkeypatch) -> None:
    store = SessionMetadataStore(mock_workspace / ".lecture_auto" / "sessions.json")
    service = SessionService(store=store)

    # First import
    source_pdf1 = mock_workspace / "source1.pdf"
    source_pdf1.write_bytes(b"PDF 1 CONTENT")
    service.import_material(session_id="session-123", material_path=str(source_pdf1))
    
    # Mock _merge_pdfs before second import
    merge_called = False
    def fake_merge(existing_path: str, new_path: str, output_path: str) -> None:
        nonlocal merge_called
        merge_called = True
        with open(existing_path, "rb") as f1, open(new_path, "rb") as f2:
            content1 = f1.read()
            content2 = f2.read()
            
        import tempfile
        import os
        from pathlib import Path
        temp_out = output_path + ".tmp"
        with open(temp_out, "wb") as fout:
            fout.write(content1 + b" MERGED " + content2)
        import shutil
        shutil.move(temp_out, output_path)

    monkeypatch.setattr(service, "_merge_pdfs", fake_merge)
    
    # Second import
    source_pdf2 = mock_workspace / "source2.pdf"
    source_pdf2.write_bytes(b"PDF 2 CONTENT")
    service.import_material(session_id="session-123", material_path=str(source_pdf2))
    
    assert merge_called is True
    dest_pdf = mock_workspace / "materials" / "physics" / "session-123.pdf"
    assert dest_pdf.read_bytes() == b"PDF 1 CONTENT MERGED PDF 2 CONTENT"
