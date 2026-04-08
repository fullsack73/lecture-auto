import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lecture_auto.cli import app
from lecture_auto.llm_adapter import GeminiLLMAdapter, LLMConfig
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


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
    
    transcript_dir = tmp_path / "transcripts" / "Physics"
    transcript_dir.mkdir(parents=True)
    (transcript_dir / "session-123-raw.md").write_text("Hello physics world.", encoding="utf-8")
    
    return tmp_path


def test_import_material_copies_file_and_updates_metadata(mock_workspace: Path) -> None:
    store = SessionMetadataStore(mock_workspace / ".lecture_auto" / "sessions.json")
    service = SessionService(store=store)

    source_pdf = mock_workspace / "source_document.pdf"
    source_pdf.write_bytes(b"PDF CONTENT")

    result = service.import_material(session_id="session-123", material_path=str(source_pdf))
    assert result.command == "material import"
    
    session = store.get_by_session_id("session-123")
    assert session is not None
    assert session.get("material_file_path") == "materials/physics/session-123.pdf"
    
    dest_pdf = mock_workspace / "materials" / "physics" / "session-123.pdf"
    assert dest_pdf.exists()
    assert dest_pdf.read_bytes() == b"PDF CONTENT"


def test_import_material_rejects_non_pdf(mock_workspace: Path) -> None:
    store = SessionMetadataStore(mock_workspace / ".lecture_auto" / "sessions.json")
    service = SessionService(store=store)

    source_txt = mock_workspace / "source_document.txt"
    source_txt.write_text("TEXT CONTENT")

    with pytest.raises(SessionCommandError, match="Unsupported file format"):
        service.import_material(session_id="session-123", material_path=str(source_txt))


@patch("lecture_auto.llm_adapter.GeminiLLMAdapter.generate_notes")
def test_summarize_session_passes_material_path(mock_generate, mock_workspace: Path) -> None:
    store = SessionMetadataStore(mock_workspace / ".lecture_auto" / "sessions.json")
    
    # Pre-populate material
    session = store.get_by_session_id("session-123")
    assert session is not None
    session["material_file_path"] = "materials/physics/session-123.pdf"
    store.upsert(session)
    
    mock_llm = MagicMock()
    mock_llm.generate_notes.return_value = "Mocked Notes"
    service = SessionService(store=store, llm_adapter=mock_llm)

    service.summarize_session(session_reference="session-123", template_name=None)
    
    mock_llm.generate_notes.assert_called_once()
    kwargs = mock_llm.generate_notes.call_args.kwargs
    assert kwargs.get("material_path") == str((mock_workspace / "materials" / "physics" / "session-123.pdf").resolve())


def test_gemini_adapter_uploads_and_deletes_file() -> None:
    config = LLMConfig(api_key="fake-key")
    with patch("google.genai.Client") as mock_client_cls:
        adapter = GeminiLLMAdapter(config)
        mock_client = mock_client_cls.return_value
        
        mock_upload = MagicMock()
        mock_upload.name = "uploaded_file_name_123"
        mock_client.files.upload.return_value = mock_upload
        
        mock_response = MagicMock()
        mock_response.text = "Generated Notes with PDF"
        mock_client.models.generate_content.return_value = mock_response
        
        with patch("os.path.exists", return_value=True):
            res = adapter.generate_notes(
                transcript="test transcript",
                template="test template",
                context_topic="Topic A",
                material_path="/fake/path/to.pdf"
            )
            
        assert res == "Generated Notes with PDF"
        mock_client.files.upload.assert_called_once_with(file="/fake/path/to.pdf")
        mock_client.files.delete.assert_called_once_with(name="uploaded_file_name_123")


def test_gemini_adapter_deletes_file_on_generation_failure() -> None:
    config = LLMConfig(api_key="fake-key")
    with patch("google.genai.Client") as mock_client_cls:
        adapter = GeminiLLMAdapter(config)
        mock_client = mock_client_cls.return_value
        
        mock_upload = MagicMock()
        mock_upload.name = "uploaded_file_name_123"
        mock_client.files.upload.return_value = mock_upload
        
        mock_client.models.generate_content.side_effect = Exception("API Error")
        
        with patch("os.path.exists", return_value=True):
            with pytest.raises(Exception, match="API Error"):
                adapter.generate_notes(
                    transcript="test transcript",
                    template="test template",
                    context_topic="Topic A",
                    material_path="/fake/path/to.pdf"
                )
            
        mock_client.files.upload.assert_called_once_with(file="/fake/path/to.pdf")
        mock_client.files.delete.assert_called_once_with(name="uploaded_file_name_123")
