import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lecture_auto.capture_runtime import CaptureRuntimeAdapter
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService


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
                    "status": "idle",
                    "timestamps": {"created_at": "2026-03-26T10:00:00Z"},
                    "naming_pending": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    return tmp_path


@patch("lecture_auto.session_service.SessionService._concat_audio")
def test_capture_append_flow_resolves_temp_path(
    mock_concat: MagicMock,
    mock_workspace: Path,
) -> None:
    store = SessionMetadataStore(mock_workspace / ".lecture_auto" / "sessions.json")
    mock_runtime = MagicMock(spec=CaptureRuntimeAdapter)

    class FakeHandle:
        process_id = 999
        backend = "mock"

    mock_runtime.start_capture.return_value = FakeHandle()

    service = SessionService(store=store, runtime_adapter=mock_runtime)

    # First capture start (creates the file on disk conceptually, mock it)
    recordings_dir = mock_workspace / "recordings" / "physics"
    recordings_dir.mkdir(parents=True)
    base_file = recordings_dir / "session-123.wav"
    
    # We must start capture so that the file path is resolved
    service.capture_start(session_id="session-123")
    
    # Simulate first capture created the file
    base_file.write_text("dummy-audio-1")
    
    # Complete first capture
    session = store.get_by_session_id("session-123")
    assert session is not None
    
    service.capture_stop(session_id="session-123", success=True)
    
    # Now start capture again in the SAME session
    # We must reset status to idle first to allow recording again
    session = store.get_by_session_id("session-123")
    assert session is not None
    session["status"] = "idle"
    store.upsert(session)

    res = service.capture_start(session_id="session-123")
    
    # Verify it used a -part.wav path since original existed
    session = store.get_by_session_id("session-123")
    assert session is not None
    assert "active_part_path" in session.get("timestamps", {})
    
    active_part = session["timestamps"]["active_part_path"]
    assert "-part.wav" in active_part
    
    # Verify capture started with the part file
    started_path = mock_runtime.start_capture.call_args.kwargs["output_path"]
    assert str(started_path).endswith("-part.wav")
    
    # Stop capture and verify concatenation
    service.capture_stop(session_id="session-123", success=True)
    
    mock_concat.assert_called_once()
    args, kwargs = mock_concat.call_args
    assert "session-123.wav" in kwargs["base_path"] or "session-123.wav" in args[0]
    assert "-part.wav" in kwargs["part_path"] or "-part.wav" in args[1]
    
    session = store.get_by_session_id("session-123")
    assert session is not None
    assert "active_part_path" not in session.get("timestamps", {})


@patch("lecture_auto.session_service.SessionService._concat_audio")
def test_capture_append_flow_discard_on_failure(
    mock_concat: MagicMock,
    mock_workspace: Path,
) -> None:
    store = SessionMetadataStore(mock_workspace / ".lecture_auto" / "sessions.json")
    mock_runtime = MagicMock(spec=CaptureRuntimeAdapter)

    class FakeHandle:
        process_id = 999
        backend = "mock"

    mock_runtime.start_capture.return_value = FakeHandle()

    service = SessionService(store=store, runtime_adapter=mock_runtime)

    recordings_dir = mock_workspace / "recordings" / "physics"
    recordings_dir.mkdir(parents=True)
    base_file = recordings_dir / "session-123.wav"
    
    service.capture_start(session_id="session-123")
    base_file.write_text("dummy-audio-1")
    service.capture_stop(session_id="session-123", success=True)
    
    session = store.get_by_session_id("session-123")
    assert session is not None
    session["status"] = "idle"
    store.upsert(session)

    service.capture_start(session_id="session-123")
    session = store.get_by_session_id("session-123")
    assert session is not None
    active_part = session["timestamps"].get("active_part_path")
    assert active_part is not None
    
    # Simulate writing to the part file
    Path(active_part).write_text("dummy-audio-part")
    
    # Stop capture WITH FAILURE
    service.capture_stop(session_id="session-123", success=False)
    
    mock_concat.assert_not_called()
    
    session = store.get_by_session_id("session-123")
    assert session is not None
    assert "active_part_path" not in session.get("timestamps", {})
    
    # The part file should have been cleaned up
    assert not Path(active_part).exists()