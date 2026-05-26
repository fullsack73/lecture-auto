from pathlib import Path
from unittest.mock import patch

from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionService
from lecture_auto.tui import _menu_capture


def _service(tmp_path: Path) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(store=store)


def test_tui_capture_stop_uses_active_recording_session_without_prompt(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-901", "2026-05-26")
    service.capture_start("session-901")

    with patch("lecture_auto.tui._select", side_effect=["stop", "__back__"]):
        with patch("lecture_auto.tui._select_session") as select_session:
            _menu_capture(service)

    select_session.assert_not_called()
    assert service.session_detail("session-901").payload["status"] == "completed"


def test_tui_capture_stop_falls_back_to_session_prompt_when_nothing_is_recording(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-902", "2026-05-26")

    with patch("lecture_auto.tui._select", side_effect=["stop", "__back__"]):
        with patch("lecture_auto.tui._select_session", return_value=None) as select_session:
            _menu_capture(service)

    select_session.assert_called_once_with(service, "Select session to stop")
    assert service.session_detail("session-902").payload["status"] == "idle"
