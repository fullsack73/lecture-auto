import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.genai import types
from typer.testing import CliRunner

from lecture_auto.cli import app
from lecture_auto.llm_adapter import GeminiLLMAdapter, LLMConfig
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


@pytest.fixture(autouse=True)
def isolate_usage_logging(monkeypatch):
    monkeypatch.setattr("lecture_auto.llm_adapter._log_llm_usage", lambda *args, **kwargs: None)


def _note_payload(
    *,
    detailed_title: str = "Topic A details",
    questions: list[str] | None = None,
) -> dict:
    return {
        "note_title": "Topic A의 핵심 원리",
        "topic_overview": ["Topic A overview"],
        "core_concepts": ["Core concept"],
        "detailed_explanations": [
            {"title": detailed_title, "bullets": ["Detailed bullet"]}
        ],
        "examples_mentioned": ["Example"],
        "questions_to_review": questions
        or [
            "What is Topic A?",
            "Why does Topic A matter?",
            "How does Topic A connect to the core concept?",
            "What assumptions shape Topic A?",
        ],
        "exam_related_mentions": ["Not mentioned."],
    }


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
        mock_response.text = json.dumps(_note_payload(), ensure_ascii=False)
        mock_client.models.generate_content.side_effect = [
            MagicMock(text="Supporting reference"), mock_response, MagicMock(text='{"issues": []}'),
        ]
        
        with patch("os.path.exists", return_value=True):
            res = adapter.generate_notes(
                transcript="test transcript",
                template="test template",
                context_topic="Topic A",
                material_path="/fake/path/to.pdf"
            )
            
        assert res.startswith("# Topic A의 핵심 원리")
        assert "### Topic A details" in res
        assert "- Core concept" in res
        mock_client.files.upload.assert_called_once()
        upload_kwargs = mock_client.files.upload.call_args.kwargs
        assert upload_kwargs["file"] == "/fake/path/to.pdf"
        assert isinstance(upload_kwargs["config"], types.UploadFileConfig)
        assert upload_kwargs["config"].mime_type == "application/pdf"

        calls = mock_client.models.generate_content.call_args_list
        generate_kwargs = calls[1].kwargs
        assert calls[0].kwargs["contents"][-1] is mock_upload
        assert all(mock_upload not in c.kwargs["contents"] for c in calls[1:])
        assert "Material reference" in generate_kwargs["config"]["system_instruction"]
        assert generate_kwargs["config"]["response_mime_type"] == "application/json"
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
            
        mock_client.files.upload.assert_called_once()
        upload_kwargs = mock_client.files.upload.call_args.kwargs
        assert upload_kwargs["file"] == "/fake/path/to.pdf"
        assert isinstance(upload_kwargs["config"], types.UploadFileConfig)
        assert upload_kwargs["config"].mime_type == "application/pdf"
        mock_client.files.delete.assert_called_once_with(name="uploaded_file_name_123")


def test_gemini_adapter_repairs_json_and_renders_structured_markdown() -> None:
    config = LLMConfig(api_key="fake-key")
    with patch("google.genai.Client") as mock_client_cls:
        adapter = GeminiLLMAdapter(config)
        mock_client = mock_client_cls.return_value

        first_response = MagicMock()
        first_response.text = json.dumps(
            _note_payload(
                detailed_title="Sub Topic 1",
                questions=["What is Topic A?"],
            ),
            ensure_ascii=False,
        )
        repair_response = MagicMock()
        repair_response.text = json.dumps(
            _note_payload(detailed_title="Evidence-based Topic A"),
            ensure_ascii=False,
        )
        mock_client.models.generate_content.side_effect = [
            first_response,
            MagicMock(text='{"issues": []}'),
            repair_response,
            MagicMock(text='{"issues": []}'),
        ]

        notes = adapter.generate_notes(
            transcript="test transcript",
            template="# ignored template",
            context_topic="Topic A",
        )

    assert "### Evidence-based Topic A" in notes
    assert "## Questions to Review" in notes
    assert mock_client.models.generate_content.call_count == 4
    repair_prompt = mock_client.models.generate_content.call_args_list[2].kwargs["contents"][0]
    assert "Repair this JSON" in repair_prompt
    assert "# ignored template" not in repair_prompt


def test_pdf_is_read_once_for_chunk_merge_and_repair():
    with patch("google.genai.Client") as client_cls, patch("os.path.exists", return_value=True):
        adapter = GeminiLLMAdapter(LLMConfig(api_key="fake", chunk_size=500))
        client = client_cls.return_value
        uploaded = client.files.upload.return_value
        uploaded.name = "files/reference"
        reference = "Exact formula: E = mc^2; terminology: Eigenvalue.\n" + "context " * 1500
        def generate(**kwargs):
            prompt = kwargs["contents"][0]
            if prompt.startswith("Extract a compact"):
                return MagicMock(text=reference)
            if prompt.startswith("Chunk: "):
                return MagicMock(text='{"evidence": [{"topic": "Topic A", "detail": "Lecture content."}]}')
            if prompt.startswith("Build the final study note"):
                return MagicMock(text=json.dumps(_note_payload(detailed_title="Sub Topic 1")))
            if "Study note:\n" in prompt:
                return MagicMock(text='{"issues": []}')
            return MagicMock(text=json.dumps(_note_payload()))
        client.models.generate_content.side_effect = generate
        notes = adapter.generate_notes("lecture content. " * 200, "template", material_path="input.pdf")
        calls = client.models.generate_content.call_args_list
        assert len(calls) > 4
        assert sum(any(item is uploaded for item in c.kwargs["contents"]) for c in calls) == 1
        for call in calls[1:]:
            system = call.kwargs["config"]["system_instruction"]
            if "Study note:\n" in call.kwargs["contents"][0]:
                assert "Material reference" not in system
                continue
            actual_reference = system.split("not proof of spoken facts):\n", 1)[1]
            assert len(actual_reference) == 8000
            assert "E = mc^2" in actual_reference
            assert "Eigenvalue" in actual_reference
        assert "Repair this JSON" in calls[-2].kwargs["contents"][0]
        assert notes.startswith("# Topic A")
        client.files.delete.assert_called_once_with(name=uploaded.name)


def test_empty_pdf_reference_fails_without_repeating_pdf():
    with patch("google.genai.Client") as client_cls, patch("os.path.exists", return_value=True):
        adapter = GeminiLLMAdapter(LLMConfig(api_key="fake"))
        client = client_cls.return_value
        client.models.generate_content.return_value = MagicMock(text="")
        client.files.upload.return_value.name = "files/reference"
        with pytest.raises(Exception, match="reference extraction returned empty"):
            adapter.generate_notes("lecture", "template", material_path="input.pdf")
        assert client.models.generate_content.call_count == 1
        client.files.delete.assert_called_once_with(name="files/reference")
