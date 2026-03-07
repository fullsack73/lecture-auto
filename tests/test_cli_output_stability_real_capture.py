from pathlib import Path

from lecture_auto.capture_runtime import CaptureHandle
from lecture_auto.cli_output import format_command_error, format_command_output
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService


class StableRuntimeAdapter:
    def start_capture(self, session_id: str, output_path: str) -> CaptureHandle:
        return CaptureHandle(
            session_id=session_id,
            output_path=output_path,
            process_id=4321,
            backend="stable-runtime",
        )

    def stop_capture(
        self,
        session_id: str,
        *,
        interrupted: bool = False,
        process_id: int | None = None,
    ) -> None:
        return None


def _service(tmp_path: Path) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(store=store, runtime_adapter=StableRuntimeAdapter())


def test_capture_start_text_template_remains_readable_and_actionable(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-701", "2026-03-06")

    result = service.capture_start("session-701")
    rendered = format_command_output(result)

    assert "Capture Started" in rendered
    assert "Session ID: session-701" in rendered
    assert "Audio Path: recordings/session-701.wav" in rendered
    assert "Next: Run 'capture stop <session_id>'" in rendered


def test_capture_stop_text_template_remains_readable_and_actionable(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-702", "2026-03-06")
    service.capture_start("session-702")

    result = service.capture_stop("session-702", success=True)
    rendered = format_command_output(result)

    assert "Capture Stopped" in rendered
    assert "Session ID: session-702" in rendered
    assert "Final Status: completed" in rendered
    assert "Next: Run 'session detail <session_id>'" in rendered


def test_json_output_for_real_capture_flow_stays_one_line_and_parseable(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.session_create("session-703", "2026-03-06")
    started = service.capture_start("session-703")

    json_line = format_command_output(started, as_json=True)

    assert "\n" not in json_line
    assert '"ok":true' in json_line
    assert '"command":"capture start"' in json_line
    assert '"payload"' in json_line
    assert '"message"' in json_line


def test_error_output_template_remains_actionable(tmp_path: Path) -> None:
    _ = _service(tmp_path)
    error = SessionCommandError(
        code="CAPTURE_DEVICE_ERROR",
        message="No accessible audio input device was detected.",
        guidance="Check audio permissions and selected device.",
        exit_code=3,
    )

    rendered = format_command_error("capture start", error)

    assert "Command Failed" in rendered
    assert "capture start" in rendered
    assert "Next Action: Check audio permissions and selected device." in rendered
    assert "Exit Code: 3" in rendered
