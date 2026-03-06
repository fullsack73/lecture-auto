from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from lecture_auto.capture_runtime import (
    CaptureDependencyError,
    CaptureDeviceError,
    CaptureInterruptedError,
    CapturePermissionError,
    CaptureRuntimeAdapter,
    CaptureRuntimeError,
    NoopCaptureRuntimeAdapter,
)
from lecture_auto.session_metadata_store import SessionMetadataStore

VALID_STATES = {"idle", "recording", "stopping", "completed", "failed"}
ALLOWED_TRANSITIONS = {
    "idle": {"recording"},
    "recording": {"stopping", "failed"},
    "stopping": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
}


class SessionCommandError(RuntimeError):
    def __init__(self, code: str, message: str, guidance: str, exit_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.guidance = guidance
        self.exit_code = exit_code


@dataclass
class CommandResult:
    command: str
    payload: dict[str, Any]
    message: str

    def as_text(self) -> str:
        return self.message

    def as_json_line(self) -> str:
        return json.dumps(
            {"command": self.command, "payload": self.payload, "message": self.message},
            ensure_ascii=False,
            separators=(",", ":"),
        )


class SessionService:
    def __init__(
        self,
        store: SessionMetadataStore,
        runtime_adapter: CaptureRuntimeAdapter | None = None,
    ) -> None:
        self.store = store
        self.runtime_adapter = runtime_adapter or NoopCaptureRuntimeAdapter()

    def session_create(
        self,
        session_id: str,
        date: str,
        title: str | None = None,
        course: str | None = None,
    ) -> CommandResult:
        naming_pending = not (title and course)
        metadata = {
            "session_id": session_id,
            "date": date,
            "title": title,
            "course": course,
            "status": "idle",
            "audio_file_path": None,
            "timestamps": {"created_at": self._utc_now()},
            "naming_pending": naming_pending,
        }

        saved = self._persist_or_raise(metadata)
        return CommandResult(
            command="session create",
            payload=saved,
            message=f"Session '{saved['session_id']}' created and ready to record.",
        )

    def capture_start(self, session_id: str, audio_file_path: str | None = None) -> CommandResult:
        session = self._require_session(session_id)
        self._transition_or_raise(session, target_state="recording")
        resolved_audio_path = audio_file_path or self.store.build_recording_path(session_id)

        try:
            handle = self.runtime_adapter.start_capture(
                session_id=session_id,
                output_path=resolved_audio_path,
            )
        except CaptureDependencyError as exc:
            raise self.map_capture_failure("dependency") from exc
        except CapturePermissionError as exc:
            raise self.map_capture_failure("permission") from exc
        except CaptureDeviceError as exc:
            raise self.map_capture_failure("device") from exc
        except CaptureRuntimeError as exc:
            raise self.map_capture_failure("runtime") from exc

        session["audio_file_path"] = resolved_audio_path
        session["timestamps"]["recording_started_at"] = self._utc_now()
        session["timestamps"]["capture_process_id"] = handle.process_id
        session["timestamps"]["capture_backend"] = handle.backend

        saved = self._persist_or_raise(session)
        return CommandResult(
            command="capture start",
            payload=saved,
            message=(
                f"Capture started for session '{session_id}'. "
                f"Output file: {resolved_audio_path}"
            ),
        )

    def capture_stop(self, session_id: str, *, success: bool = True) -> CommandResult:
        session = self._require_session(session_id)
        self._transition_or_raise(session, target_state="stopping")
        session["timestamps"]["stopping_at"] = self._utc_now()

        try:
            self.runtime_adapter.stop_capture(session_id=session_id, interrupted=not success)
        except CaptureInterruptedError as exc:
            raise self.map_capture_failure("interrupted") from exc
        except CaptureDependencyError as exc:
            raise self.map_capture_failure("dependency") from exc
        except CapturePermissionError as exc:
            raise self.map_capture_failure("permission") from exc
        except CaptureDeviceError as exc:
            raise self.map_capture_failure("device") from exc
        except CaptureRuntimeError as exc:
            raise self.map_capture_failure("runtime") from exc

        final_state = "completed" if success else "failed"
        self._transition_or_raise(session, target_state=final_state)
        if success:
            session["timestamps"]["recording_completed_at"] = self._utc_now()
            message = f"Capture stopped successfully for session '{session_id}'."
        else:
            session["timestamps"]["recording_failed_at"] = self._utc_now()
            message = (
                f"Capture stopped with failure for session '{session_id}'. "
                "Run diagnostics and retry capture start."
            )

        saved = self._persist_or_raise(session)
        return CommandResult(command="capture stop", payload=saved, message=message)

    def session_history(self) -> CommandResult:
        rows = self.store.list_recent_first()
        payload = {
            "count": len(rows),
            "sessions": [
                {
                    "session_id": row["session_id"],
                    "date": row["date"],
                    "title": row["title"],
                    "course": row["course"],
                    "status": row["status"],
                }
                for row in rows
            ],
        }
        return CommandResult(
            command="session history",
            payload=payload,
            message=f"Loaded {payload['count']} session(s) from local history.",
        )

    def session_detail(self, session_id: str) -> CommandResult:
        session = self._require_session(session_id)
        return CommandResult(
            command="session detail",
            payload=session,
            message=f"Loaded details for session '{session_id}'.",
        )

    def map_capture_failure(self, failure_kind: str) -> SessionCommandError:
        mapping = {
            "dependency": SessionCommandError(
                code="CAPTURE_DEPENDENCY_ERROR",
                message="Audio capture dependencies are unavailable.",
                guidance="Install FFmpeg/PyAudio and retry.",
                exit_code=2,
            ),
            "device": SessionCommandError(
                code="CAPTURE_DEVICE_ERROR",
                message="No accessible audio input device was detected.",
                guidance="Check audio permissions and selected device.",
                exit_code=3,
            ),
            "runtime": SessionCommandError(
                code="CAPTURE_RUNTIME_ERROR",
                message="Capture failed during runtime.",
                guidance="Inspect logs and restart capture.",
                exit_code=4,
            ),
            "permission": SessionCommandError(
                code="CAPTURE_PERMISSION_DENIED",
                message="Capture permission was denied by the operating system.",
                guidance="Grant microphone/system-audio permission and retry.",
                exit_code=5,
            ),
            "interrupted": SessionCommandError(
                code="CAPTURE_INTERRUPTED",
                message="Capture was interrupted before completion.",
                guidance="Run 'capture stop' then restart capture when ready.",
                exit_code=6,
            ),
        }
        if failure_kind not in mapping:
            return SessionCommandError(
                code="CAPTURE_UNKNOWN_ERROR",
                message="Capture failed due to an unknown error.",
                guidance="Retry the command and verify the local environment.",
                exit_code=7,
            )
        return mapping[failure_kind]

    def _persist_or_raise(self, session: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.store.upsert(session)
        except OSError as exc:
            raise SessionCommandError(
                code="METADATA_WRITE_ERROR",
                message="Failed to persist session metadata to local storage.",
                guidance="Check filesystem permissions and available disk space.",
                exit_code=8,
            ) from exc

    def _require_session(self, session_id: str) -> dict[str, Any]:
        found = self.store.get_by_session_id(session_id)
        if not found:
            raise SessionCommandError(
                code="SESSION_NOT_FOUND",
                message=f"Session '{session_id}' was not found.",
                guidance="Run 'session history' to view available sessions.",
                exit_code=1,
            )
        return found

    def _transition_or_raise(self, session: dict[str, Any], target_state: str) -> None:
        current = session["status"]
        if current not in VALID_STATES:
            raise SessionCommandError(
                code="INVALID_SESSION_STATE",
                message=f"Session state '{current}' is invalid.",
                guidance="Recreate the session metadata before retrying.",
                exit_code=1,
            )

        allowed = ALLOWED_TRANSITIONS[current]
        if target_state not in allowed:
            raise SessionCommandError(
                code="INVALID_TRANSITION",
                message=(
                    f"Cannot move session '{session['session_id']}' "
                    f"from '{current}' to '{target_state}'."
                ),
                guidance="Use create -> start -> stop command order.",
                exit_code=1,
            )
        session["status"] = target_state

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
