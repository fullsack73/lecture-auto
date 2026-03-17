import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from lecture_auto.cli import app

runner = CliRunner()


@patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": ""})
def test_library_list_command_exits_0():
    """Test that 'library list' command exits with code 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "notes").mkdir()
        (workspace / "transcripts").mkdir()
        (workspace / "recordings").mkdir()
        (workspace / "metadata").mkdir()
        
        sessions = [
            {
                "session_id": "lecture-001",
                "date": "2026-03-01",
                "title": "Intro",
                "course": "CS101",
                "status": "completed",
                "audio_file_path": None,
                "timestamps": {"created_at": "2026-03-01T10:00:00Z"},
                "naming_pending": False,
            },
        ]
        
        metadata_file = workspace / "metadata" / "sessions.json"
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False)
        
        with patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": str(workspace)}):
            result = runner.invoke(app, ["library", "list"])
            assert result.exit_code == 0
            assert "lecture-001" in result.stdout


@patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": ""})
def test_library_search_command_returns_matches():
    """Test that 'library search <query>' command returns matching sessions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "notes").mkdir()
        (workspace / "transcripts").mkdir()
        (workspace / "recordings").mkdir()
        (workspace / "metadata").mkdir()
        
        sessions = [
            {
                "session_id": "python-basics",
                "date": "2026-03-01",
                "title": "Python Intro",
                "course": "CS101",
                "status": "completed",
                "audio_file_path": None,
                "timestamps": {"created_at": "2026-03-01T10:00:00Z"},
                "naming_pending": False,
            },
        ]
        
        metadata_file = workspace / "metadata" / "sessions.json"
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False)
        
        with patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": str(workspace)}):
            result = runner.invoke(app, ["library", "search", "python"])
            assert result.exit_code == 0
            assert "python-basics" in result.stdout


@patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": ""})
def test_library_open_command_exits_0_for_known_session():
    """Test that 'library open <session-id>' exits with code 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "notes").mkdir()
        (workspace / "transcripts").mkdir()
        (workspace / "recordings").mkdir()
        (workspace / "metadata").mkdir()
        
        sessions = [
            {
                "session_id": "lecture-001",
                "date": "2026-03-01",
                "title": "Intro",
                "course": "CS101",
                "status": "completed",
                "audio_file_path": None,
                "timestamps": {"created_at": "2026-03-01T10:00:00Z"},
                "naming_pending": False,
            },
        ]
        
        metadata_file = workspace / "metadata" / "sessions.json"
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False)
        
        with patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": str(workspace)}):
            with patch("subprocess.run"):
                result = runner.invoke(app, ["library", "open", "lecture-001"])
                assert result.exit_code == 0


@patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": ""})
def test_library_list_with_status_filter():
    """Test that 'library list --status' filters correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "notes").mkdir()
        (workspace / "transcripts").mkdir()
        (workspace / "recordings").mkdir()
        (workspace / "metadata").mkdir()
        
        sessions = [
            {
                "session_id": "lecture-001",
                "date": "2026-03-01",
                "title": "Intro",
                "course": "CS101",
                "status": "completed",
                "audio_file_path": None,
                "timestamps": {"created_at": "2026-03-01T10:00:00Z"},
                "naming_pending": False,
            },
            {
                "session_id": "lecture-002",
                "date": "2026-03-05",
                "title": "Advanced",
                "course": "CS101",
                "status": "idle",
                "audio_file_path": None,
                "timestamps": {"created_at": "2026-03-05T10:00:00Z"},
                "naming_pending": True,
            },
        ]
        
        metadata_file = workspace / "metadata" / "sessions.json"
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False)
        
        with patch.dict("os.environ", {"LECTURE_AUTO_WORKSPACE": str(workspace)}):
            result = runner.invoke(app, ["library", "list", "--status", "completed"])
            assert result.exit_code == 0
            assert "lecture-001" in result.stdout
