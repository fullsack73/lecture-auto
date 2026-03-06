from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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

SUPPORTED_IMPORT_EXTENSIONS = {"wav", "mp3"}
JOB_VALID_STATES = {"queued", "running", "succeeded", "failed", "canceled"}
JOB_ALLOWED_TRANSITIONS = {
    None: {"queued"},
    "queued": {"running", "failed", "canceled"},
    "running": {"succeeded", "failed", "canceled"},
    "succeeded": set(),
    "failed": {"queued"},
    "canceled": {"queued"},
}
MAX_IMPORT_RETRIES = 3


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

    def import_audio(
        self,
        session_id: str,
        source_audio_path: str,
        *,
        allow_failed_retry: bool = False,
    ) -> CommandResult:
        session = self._require_session(session_id)
        normalized_source_path = self._normalize_source_path(source_audio_path)
        extension = self._require_supported_import_extension(normalized_source_path)
        self._reject_duplicate_import(
            session,
            normalized_source_path,
            allow_failed_retry=allow_failed_retry,
        )

        session["import_source_audio_path"] = normalized_source_path
        session["job_attempts"] = int(session.get("job_attempts", 0)) + 1
        session["job_error_code"] = None

        self._transition_job_or_raise(session, "queued")
        session["job_timestamps"]["queued_at"] = self._utc_now()
        self._transition_job_or_raise(session, "running")
        session["job_timestamps"]["started_at"] = self._utc_now()

        persisted_path = session.get("audio_file_path")
        if not persisted_path:
            persisted_path = self.store.next_imported_audio_path(session_id, extension)

        try:
            self._copy_import_audio(
                source_path=normalized_source_path,
                destination_relative_path=persisted_path,
            )
        except OSError as exc:
            self._transition_job_or_raise(session, "failed")
            session["job_error_code"] = "IMPORT_COPY_ERROR"
            session["job_timestamps"]["ended_at"] = self._utc_now()
            saved = self._persist_or_raise(session)
            return CommandResult(
                command="audio import",
                payload=self._build_progress_payload(saved),
                message=(
                    f"Audio import failed for session '{session_id}'. "
                    "Fix file access issues and run retry."
                ),
            )

        session["audio_file_path"] = persisted_path
        self._transition_job_or_raise(session, "succeeded")
        session["job_timestamps"]["ended_at"] = self._utc_now()
        saved = self._persist_or_raise(session)
        return CommandResult(
            command="audio import",
            payload=self._build_progress_payload(saved),
            message=f"Audio import completed for session '{session_id}'.",
        )

    def retry_import_audio(self, session_id: str) -> CommandResult:
        session = self._require_session(session_id)
        current_status = session.get("job_status")
        attempts = int(session.get("job_attempts", 0))

        if current_status != "failed":
            raise SessionCommandError(
                code="IMPORT_RETRY_NOT_ALLOWED",
                message="Retry is only allowed for failed import jobs.",
                guidance="Run import first or inspect the last failed job.",
                exit_code=1,
            )

        if attempts >= MAX_IMPORT_RETRIES:
            raise SessionCommandError(
                code="IMPORT_RETRY_LIMIT_EXCEEDED",
                message="Import retry limit has been reached.",
                guidance="Retry limit is 3 attempts. Re-import with a new command if needed.",
                exit_code=1,
            )

        source_audio_path = session.get("import_source_audio_path")
        if not isinstance(source_audio_path, str) or not source_audio_path.strip():
            raise SessionCommandError(
                code="IMPORT_SOURCE_NOT_FOUND",
                message="Cannot retry import because source audio path is missing.",
                guidance="Run the audio import command again with a valid source path.",
                exit_code=1,
            )

        # Retry must preserve the same target path to avoid duplicate artifacts.
        retried = self.import_audio(
            session_id=session_id,
            source_audio_path=source_audio_path,
            allow_failed_retry=True,
        )
        return CommandResult(
            command="audio import retry",
            payload=retried.payload,
            message=retried.message,
        )

    def cancel_import_audio(self, session_id: str) -> CommandResult:
        session = self._require_session(session_id)
        if session.get("job_status") not in {"queued", "running"}:
            raise SessionCommandError(
                code="IMPORT_CANCEL_NOT_ALLOWED",
                message="Import cancellation is only allowed for queued/running jobs.",
                guidance="Start a new import job first or check current status.",
                exit_code=1,
            )

        self._transition_job_or_raise(session, "canceled")
        session["job_timestamps"]["ended_at"] = self._utc_now()
        saved = self._persist_or_raise(session)
        return CommandResult(
            command="audio import cancel",
            payload=self._build_progress_payload(saved),
            message=f"Audio import canceled for session '{session_id}'.",
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

    def _normalize_source_path(self, source_audio_path: str) -> str:
        normalized = source_audio_path.strip()
        if not normalized:
            raise SessionCommandError(
                code="IMPORT_SOURCE_REQUIRED",
                message="Source audio path is required.",
                guidance="Provide a local .wav or .mp3 file path with the import command.",
                exit_code=1,
            )
        return str(Path(normalized).as_posix())

    def _require_supported_import_extension(self, source_audio_path: str) -> str:
        suffix = Path(source_audio_path).suffix.lower().lstrip(".")
        if suffix not in SUPPORTED_IMPORT_EXTENSIONS:
            raise SessionCommandError(
                code="UNSUPPORTED_AUDIO_FORMAT",
                message="Unsupported audio format for import.",
                guidance="Use a .wav or .mp3 file and retry.",
                exit_code=1,
            )
        return suffix

    def _reject_duplicate_import(
        self,
        session: dict[str, Any],
        source_audio_path: str,
        *,
        allow_failed_retry: bool,
    ) -> None:
        if (
            allow_failed_retry
            and session.get("job_status") == "failed"
            and session.get("import_source_audio_path") == source_audio_path
        ):
            return

        if session.get("import_source_audio_path") == source_audio_path:
            raise SessionCommandError(
                code="DUPLICATE_AUDIO_IMPORT",
                message="Duplicate audio import is not allowed for this session.",
                guidance="Use a different file or create a new session.",
                exit_code=1,
            )

    def _transition_job_or_raise(self, session: dict[str, Any], target_state: str) -> None:
        current = session.get("job_status")
        if current not in JOB_ALLOWED_TRANSITIONS:
            raise SessionCommandError(
                code="INVALID_JOB_STATE",
                message=f"Import job state '{current}' is invalid.",
                guidance="Re-run the import command to initialize a new job.",
                exit_code=1,
            )

        if target_state not in JOB_VALID_STATES:
            raise SessionCommandError(
                code="INVALID_JOB_TRANSITION",
                message=f"Unknown import job state '{target_state}'.",
                guidance="Use one of queued/running/succeeded/failed/canceled.",
                exit_code=1,
            )

        allowed = JOB_ALLOWED_TRANSITIONS[current]
        if target_state not in allowed:
            raise SessionCommandError(
                code="INVALID_JOB_TRANSITION",
                message=f"Cannot move import job from '{current}' to '{target_state}'.",
                guidance="Use valid job flow: queued -> running -> succeeded/failed/canceled.",
                exit_code=1,
            )
        session["job_status"] = target_state

    def _copy_import_audio(self, *, source_path: str, destination_relative_path: str) -> None:
        metadata_root = self.store.metadata_file.parent.parent
        destination = metadata_root / destination_relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)

    def _build_progress_payload(self, session: dict[str, Any]) -> dict[str, Any]:
        payload = dict(session)
        job_timestamps = payload.get("job_timestamps") or {}
        payload["progress"] = {
            "started_at": job_timestamps.get("started_at"),
            "ended_at": job_timestamps.get("ended_at"),
            "current_stage": payload.get("job_status"),
            "final_status": payload.get("job_status"),
            "attempt": payload.get("job_attempts", 0),
            "retry_limit": MAX_IMPORT_RETRIES,
        }
        return payload
