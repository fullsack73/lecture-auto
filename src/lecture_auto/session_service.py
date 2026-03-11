from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import typer

from lecture_auto.capture_runtime import (
    CaptureDependencyError,
    CaptureDeviceError,
    CaptureInterruptedError,
    CapturePermissionError,
    CaptureRuntimeAdapter,
    CaptureRuntimeError,
    NoopCaptureRuntimeAdapter,
)
from lecture_auto.stt_config import STTConfig
from lecture_auto.stt_runtime import (
    APISTTRuntimeAdapter,
    LocalSTTRuntimeAdapter,
    STTAudioDecodeError,
    STTConfigError,
    STTProviderAuthError,
    STTRuntimeAdapter,
    STTRuntimeError,
    STTTransientNetworkError,
)
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.llm_adapter import (
    LLMProviderAdapter,
    LLMConfigError,
    LLMProviderAuthError,
    LLMTransientNetworkError,
)

VALID_STATES = {"idle", "recording", "stopping", "completed", "failed"}
ALLOWED_TRANSITIONS = {
    "idle": {"recording"},
    "recording": {"stopping", "failed"},
    "stopping": {"completed", "failed"},
    "completed": {"recording"},
    "failed": {"recording"},
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
MAX_STT_API_RETRIES = 2
DEFAULT_NOTE_TEMPLATE_NAME = "bullet-summary"


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
        stt_config: STTConfig | None = None,
        local_stt_adapter: STTRuntimeAdapter | None = None,
        api_stt_adapter: STTRuntimeAdapter | None = None,
        llm_adapter: LLMProviderAdapter | None = None,
        audio_format: str = "wav",
    ) -> None:
        self.store = store
        self.runtime_adapter = runtime_adapter or NoopCaptureRuntimeAdapter()
        self.stt_config = stt_config or STTConfig()
        self._local_stt_adapter = local_stt_adapter
        self._api_stt_adapter = api_stt_adapter
        self.llm_adapter = llm_adapter
        self.audio_format = audio_format

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
        resolved_audio_path = audio_file_path or self.store.build_recording_path(
            session_id, extension=self.audio_format
        )
        metadata_root = self.store.metadata_file.parent.parent
        runtime_output_path = resolved_audio_path
        if not Path(resolved_audio_path).is_absolute():
            runtime_output_path = str((metadata_root / resolved_audio_path).resolve())

        try:
            handle = self.runtime_adapter.start_capture(
                session_id=session_id,
                output_path=runtime_output_path,
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
        process_id_raw = session.get("timestamps", {}).get("capture_process_id")
        process_id = process_id_raw if isinstance(process_id_raw, int) else None

        try:
            self.runtime_adapter.stop_capture(
                session_id=session_id,
                interrupted=not success,
                process_id=process_id,
            )
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

    def session_delete(self, session_id: str) -> CommandResult:
        session = self._require_session(session_id)
        
        metadata_root = self.store.metadata_file.parent.parent
        files_to_delete = []
        if session.get("audio_file_path"):
            files_to_delete.append(metadata_root / session["audio_file_path"])
        if session.get("transcript_file_path"):
            files_to_delete.append(metadata_root / session["transcript_file_path"])
        
        edited_transcript = metadata_root / f"transcripts/{session_id}-edited.md"
        if edited_transcript.exists():
            files_to_delete.append(edited_transcript)
            
        deleted = self.store.delete(session_id)
        if not deleted:
            raise SessionCommandError(
                code="SESSION_DELETE_FAILED",
                message=f"Session '{session_id}' could not be deleted.",
                guidance="It might have been removed already.",
                exit_code=1,
            )
            
        for f in files_to_delete:
            try:
                if f.exists():
                    f.unlink()
            except OSError:
                pass
                
        return CommandResult(
            command="session delete",
            payload={"session_id": session_id},
            message=f"Session '{session_id}' and associated files have been deleted.",
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

    def transcribe_session(
        self,
        session_id: str,
        *,
        source_audio_path: str | None = None,
    ) -> CommandResult:
        session = self._require_session(session_id)
        if source_audio_path is not None:
            raise SessionCommandError(
                code="TRANSCRIPTION_SESSION_AUDIO_ONLY",
                message="Transcription accepts only session-linked audio.",
                guidance="Attach/import audio to the session first, then retry transcription.",
                exit_code=1,
            )

        audio_relative_path = session.get("audio_file_path")
        if not isinstance(audio_relative_path, str) or not audio_relative_path.strip():
            raise SessionCommandError(
                code="TRANSCRIPTION_AUDIO_NOT_FOUND",
                message="No session audio is attached for transcription.",
                guidance="Run capture or audio import for this session first.",
                exit_code=1,
            )

        stages = [
            "preflight_checks",
            "mode_provider_initialization",
            "transcription_in_progress",
            "file_write_complete",
        ]
        metadata_root = self.store.metadata_file.parent.parent
        mode = self.stt_config.mode
        attempt = 0
        retry_limit = MAX_STT_API_RETRIES if mode == "api" else 0

        self._run_transcription_preflight()

        adapter = self._build_stt_adapter()
        adapter_audio_path = audio_relative_path
        if mode == "api" and self.stt_config.api_provider in ("deepgram", "google-chirp3"):
            candidate = Path(audio_relative_path)
            if not candidate.is_absolute():
                metadata_candidate = (metadata_root / candidate).resolve()
                cwd_candidate = candidate.resolve()
                adapter_audio_path = str(
                    metadata_candidate if metadata_candidate.exists() else cwd_candidate
                )

        transcript_text: str | None = None
        transcript_result = None
        while True:
            try:
                attempt += 1
                transcript_result = adapter.transcribe(audio_path=adapter_audio_path)
                transcript_text = transcript_result.transcript_text
                break
            except STTTransientNetworkError as exc:
                if mode == "api" and attempt <= retry_limit:
                    continue
                self._mark_transcription_failure(session, "network/transient")
                raise self.map_transcription_failure(
                    "network/transient", detail=str(exc)
                ) from exc
            except STTProviderAuthError as exc:
                self._mark_transcription_failure(session, "provider_auth")
                raise self.map_transcription_failure(
                    "provider_auth", detail=str(exc)
                ) from exc
            except STTAudioDecodeError as exc:
                self._mark_transcription_failure(session, "audio_decode")
                raise self.map_transcription_failure(
                    "audio_decode", detail=str(exc)
                ) from exc
            except STTConfigError as exc:
                self._mark_transcription_failure(session, "configuration")
                raise self.map_transcription_failure(
                    "configuration", detail=str(exc)
                ) from exc
            except STTRuntimeError as exc:
                self._mark_transcription_failure(session, "runtime")
                raise self.map_transcription_failure("runtime", detail=str(exc)) from exc

        output_text = transcript_text or ""
        if transcript_result and transcript_result.segments:
            output_text = transcript_result.to_diarized_markdown()

        transcript_relative_path = self.store.build_raw_transcript_path(session_id)
        try:
            self._write_transcript_file(
                transcript_relative_path=transcript_relative_path,
                transcript_text=output_text,
            )
        except OSError as exc:
            self._mark_transcription_failure(session, "configuration")
            raise SessionCommandError(
                code="TRANSCRIPTION_WRITE_ERROR",
                message="Failed to write raw transcript to local storage.",
                guidance="Check filesystem permissions and available disk space, then retry.",
                exit_code=8,
            ) from exc

        session["transcript_file_path"] = transcript_relative_path
        session["transcription_status"] = "succeeded"
        session["transcription_error_category"] = None
        session["transcription_retry_count"] = max(0, attempt - 1)
        session.setdefault("timestamps", {})["transcription_completed_at"] = self._utc_now()

        saved = self._persist_or_raise(session)
        payload = dict(saved)
        payload["transcription_progress"] = {
            "stages": stages,
            "current_stage": "file_write_complete",
            "final_status": "succeeded",
            "attempt": attempt,
            "retry_limit": retry_limit,
            "mode": mode,
            "transcript_file_path": transcript_relative_path,
        }

        return CommandResult(
            command="transcription run",
            payload=payload,
            message=f"Transcription completed for session '{session_id}'.",
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

    def map_transcription_failure(
        self,
        failure_kind: str,
        *,
        detail: str | None = None,
    ) -> SessionCommandError:
        mapping = {
            "configuration": SessionCommandError(
                code="TRANSCRIPTION_CONFIG_ERROR",
                message="Transcription configuration is invalid.",
                guidance="Check STT mode/provider/model settings and retry.",
                exit_code=2,
            ),
            "provider_auth": SessionCommandError(
                code="TRANSCRIPTION_PROVIDER_AUTH_ERROR",
                message="STT provider authentication failed.",
                guidance="Verify API key/provider settings and retry.",
                exit_code=3,
            ),
            "network/transient": SessionCommandError(
                code="TRANSCRIPTION_NETWORK_TRANSIENT_ERROR",
                message="Transient network/provider failure during transcription.",
                guidance="Retry later or verify provider/network availability.",
                exit_code=4,
            ),
            "audio_decode": SessionCommandError(
                code="TRANSCRIPTION_AUDIO_DECODE_ERROR",
                message="Audio format or decoding failed during transcription.",
                guidance="Verify session audio format/quality and retry.",
                exit_code=5,
            ),
            "runtime": SessionCommandError(
                code="TRANSCRIPTION_RUNTIME_ERROR",
                message="Transcription failed due to an unknown runtime error.",
                guidance="Inspect logs and retry transcription.",
                exit_code=6,
            ),
        }
        result = mapping.get(
            failure_kind,
            SessionCommandError(
                code="TRANSCRIPTION_RUNTIME_ERROR",
                message="Transcription failed due to an unknown runtime error.",
                guidance="Inspect logs and retry transcription.",
                exit_code=6,
            ),
        )
        if detail and detail.strip():
            return SessionCommandError(
                code=result.code,
                message=result.message,
                guidance=f"{result.guidance} Detail: {detail.strip()}",
                exit_code=result.exit_code,
            )
        return result

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

    def transcript_search(self, title_query: str) -> CommandResult:
        sessions = self.store.load_all()
        matches = []
        lowered_query = title_query.lower()
        for session in sessions:
            title = session.get("title") or ""
            if lowered_query in title.lower():
                matches.append(session)
        
        matches = sorted(matches, key=lambda row: row["date"], reverse=True)
        return CommandResult(
            command="transcript search",
            payload={"matches": matches, "query": title_query},
            message=f"Found {len(matches)} session(s) matching '{title_query}'."
        )

    def transcript_open(self, session_reference: str) -> CommandResult:
        sessions = self.store.load_all()
        session = None
        for row in sessions:
            if row["session_id"] == session_reference or \
               (row.get("title") and row.get("title").lower() == session_reference.lower()):
                session = row
                break
        
        if not session:
            raise SessionCommandError(
                code="SESSION_NOT_FOUND",
                message=f"Session matching '{session_reference}' was not found.",
                guidance="Run 'lecture search <title>' to find valid sessions.",
                exit_code=1,
            )

        session_id = session["session_id"]
        
        raw_transcript_path_str = session.get("transcript_file_path")
        if not raw_transcript_path_str:
            raise SessionCommandError(
                code="TRANSCRIPT_NOT_FOUND",
                message=f"No transcript found for session '{session_id}'.",
                guidance="Run transcription for this session first.",
                exit_code=1,
            )
        
        metadata_root = self.store.metadata_file.parent.parent
        raw_transcript_path = metadata_root / raw_transcript_path_str
        edited_transcript_path = metadata_root / f"transcripts/{session_id}-edited.md"

        active_path = edited_transcript_path if edited_transcript_path.exists() else raw_transcript_path
        
        if not active_path.exists():
            raise SessionCommandError(
                code="TRANSCRIPT_FILE_MISSING",
                message=f"Transcript file missing at '{active_path}'.",
                guidance="Ensure the file hasn't been manually deleted.",
                exit_code=1,
            )

        pre_edit_mtime = active_path.stat().st_mtime
        
        typer.launch(str(active_path.resolve()), wait=True)

        post_edit_mtime = active_path.stat().st_mtime
        
        if post_edit_mtime > pre_edit_mtime:
            if active_path == raw_transcript_path:
                import shutil
                shutil.copyfile(raw_transcript_path, edited_transcript_path)
                return CommandResult(
                    command="transcript open",
                    payload={"session_id": session_id, "state": "edited"},
                    message=f"Transcript for '{session_id}' edited and saved as new version."
                )
            else:
                return CommandResult(
                    command="transcript open",
                    payload={"session_id": session_id, "state": "edited"},
                    message=f"Edited transcript for '{session_id}' updated."
                )
        
        return CommandResult(
            command="transcript open",
            payload={"session_id": session_id, "state": "unmodified"},
            message=f"Transcript for '{session_id}' reviewed (no changes)."
        )

    def transcript_refine(self, session_reference: str, *, raw: bool = False) -> CommandResult:
        if not self.llm_adapter:
            raise SessionCommandError(
                code="LLM_NOT_CONFIGURED",
                message="No LLM adapter configured for refinement.",
                guidance="Configure an LLM provider (e.g., Gemini) to use the refine command.",
                exit_code=1,
            )

        sessions = self.store.load_all()
        session = next(
            (r for r in sessions if r["session_id"] == session_reference or 
             (r.get("title") and r.get("title").lower() == session_reference.lower())),
            None
        )

        if not session:
            raise SessionCommandError(
                code="SESSION_NOT_FOUND",
                message=f"Session matching '{session_reference}' was not found.",
                guidance="Run 'lecture search <title>' to find valid sessions.",
                exit_code=1,
            )

        session_id = session["session_id"]
        raw_transcript_path_str = session.get("transcript_file_path")
        if not raw_transcript_path_str:
            raise SessionCommandError(
                code="TRANSCRIPT_NOT_FOUND",
                message=f"No transcript found for session '{session_id}'.",
                guidance="Run transcription for this session first.",
                exit_code=1,
            )

        metadata_root = self.store.metadata_file.parent.parent
        raw_transcript_path = metadata_root / raw_transcript_path_str
        edited_transcript_path = metadata_root / f"transcripts/{session_id}-edited.md"

        target_path = raw_transcript_path
        if not raw and edited_transcript_path.exists():
            if not raw_transcript_path.exists() or edited_transcript_path.stat().st_mtime > raw_transcript_path.stat().st_mtime:
                target_path = edited_transcript_path

        if not target_path.exists():
            raise SessionCommandError(
                code="TRANSCRIPT_FILE_MISSING",
                message=f"Transcript file missing at '{target_path}'.",
                guidance="Ensure the file hasn't been manually deleted.",
                exit_code=1,
            )

        raw_text = target_path.read_text(encoding="utf-8")
        if not raw_text.strip():
            raise SessionCommandError(
                code="TRANSCRIPT_EMPTY",
                message=f"The selected transcript file is empty.",
                guidance="Cannot refine an empty transcript.",
                exit_code=1,
            )

        context_topic = session.get("title") or session.get("course")
        
        try:
            refined_text = self.llm_adapter.refine_transcript(raw_text, context_topic=context_topic)
        except LLMConfigError as exc:
            raise SessionCommandError(code="LLM_CONFIG_FAILED", message=str(exc), guidance="Check LLM configuration.", exit_code=1)
        except LLMProviderAuthError as exc:
            raise SessionCommandError(code="LLM_AUTH_FAILED", message=str(exc), guidance="Verify your API key.", exit_code=1)
        except LLMTransientNetworkError as exc:
            raise SessionCommandError(code="LLM_NETWORK_ERROR", message=str(exc), guidance="Try again later.", exit_code=1)
        except Exception as exc:
            raise SessionCommandError(code="LLM_UNKNOWN_ERROR", message=f"Unexpected refinement failure: {exc}", guidance="Check debug logs.", exit_code=1)

        self._write_transcript_file(
            transcript_relative_path=f"transcripts/{session_id}-edited.md",
            transcript_text=refined_text
        )

        # Output payload logic for formatting
        target_used = "raw" if target_path == raw_transcript_path else "edited"
        return CommandResult(
            command="transcript refine",
            payload={"session_id": session_id, "target_used": target_used},
            message=f"Transcript successfully refined from {target_used} source."
        )

    def summarize_session(
        self,
        session_reference: str,
        *,
        template_name: str | None = None,
        preview: bool = False,
    ) -> CommandResult:
        if not self.llm_adapter:
            raise SessionCommandError(
                code="LLM_NOT_CONFIGURED",
                message="No LLM adapter configured for summarize.",
                guidance="Configure an LLM provider (e.g., Gemini) to use summarize.",
                exit_code=1,
            )

        session = self._resolve_session_for_reference(session_reference)
        session_id = session["session_id"]
        transcript_text, transcript_source = self._load_summary_transcript(session)
        resolved_template_name, template_text = self._resolve_note_template(template_name)

        context_topic = session.get("title") or session.get("course")
        try:
            notes = self.llm_adapter.generate_notes(
                transcript=transcript_text,
                template=template_text,
                context_topic=context_topic,
            )
        except LLMConfigError as exc:
            raise SessionCommandError(
                code="LLM_CONFIG_FAILED",
                message=str(exc),
                guidance="Check LLM configuration.",
                exit_code=1,
            ) from exc
        except LLMProviderAuthError as exc:
            raise SessionCommandError(
                code="LLM_AUTH_FAILED",
                message=str(exc),
                guidance="Verify your API key.",
                exit_code=1,
            ) from exc
        except LLMTransientNetworkError as exc:
            raise SessionCommandError(
                code="LLM_NETWORK_ERROR",
                message=str(exc),
                guidance="Try again later.",
                exit_code=1,
            ) from exc
        except Exception as exc:
            raise SessionCommandError(
                code="LLM_UNKNOWN_ERROR",
                message=f"Unexpected summarize failure: {exc}",
                guidance="Check debug logs.",
                exit_code=1,
            ) from exc

        note_relative_path = self.store.build_note_path(session_id)
        payload = {
            "session_id": session_id,
            "template": resolved_template_name,
            "preview": preview,
            "source_transcript": transcript_source,
            "note_file_path": note_relative_path,
        }

        if preview:
            payload["notes"] = notes
            return CommandResult(command="summarize", payload=payload, message=notes)

        self._write_note_file(note_relative_path=note_relative_path, note_text=notes)
        return CommandResult(
            command="summarize",
            payload=payload,
            message=(
                f"Summary notes saved for session '{session_id}' at '{note_relative_path}'."
            ),
        )

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

    def _run_transcription_preflight(self) -> None:
        try:
            self.stt_config.validate()
        except ValueError as exc:
            raise SessionCommandError(
                code="TRANSCRIPTION_CONFIG_ERROR",
                message="Transcription preflight checks failed.",
                guidance=str(exc),
                exit_code=2,
            ) from exc

    def _build_stt_adapter(self) -> STTRuntimeAdapter:
        if self.stt_config.mode == "local":
            if self._local_stt_adapter is not None:
                return self._local_stt_adapter
            from lecture_auto.whisper_adapter import FasterWhisperSTTRuntimeAdapter
            return FasterWhisperSTTRuntimeAdapter(config=self.stt_config)

        if self._api_stt_adapter is not None:
            return self._api_stt_adapter

        if self.stt_config.api_provider == "deepgram":
            from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter
            return DeepgramSTTRuntimeAdapter(config=self.stt_config)

        if self.stt_config.api_provider == "google-chirp3":
            from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter
            return GoogleChirp3STTRuntimeAdapter(config=self.stt_config)

        return APISTTRuntimeAdapter(
            provider=self.stt_config.api_provider or "openai-compatible",
            api_key=self.stt_config.api_key or "",
        )

    def _mark_transcription_failure(self, session: dict[str, Any], category: str) -> None:
        session["transcription_status"] = "failed"
        session["transcription_error_category"] = category
        retries = int(session.get("transcription_retry_count", 0))
        session["transcription_retry_count"] = retries + 1
        session.setdefault("timestamps", {})["transcription_failed_at"] = self._utc_now()
        self._persist_or_raise(session)

    def _write_transcript_file(self, *, transcript_relative_path: str, transcript_text: str) -> None:
        metadata_root = self.store.metadata_file.parent.parent
        target = metadata_root / transcript_relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(transcript_text, encoding="utf-8")

    def _write_note_file(self, *, note_relative_path: str, note_text: str) -> None:
        metadata_root = self.store.metadata_file.parent.parent
        target = metadata_root / note_relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(note_text, encoding="utf-8")

    def _resolve_session_for_reference(self, session_reference: str) -> dict[str, Any]:
        sessions = self.store.list_recent_first()
        if not sessions:
            raise SessionCommandError(
                code="SESSION_NOT_FOUND",
                message="No sessions are available.",
                guidance="Run 'session create' to create your first session.",
                exit_code=1,
            )

        if not session_reference.strip():
            return sessions[0]

        reference = session_reference.strip().lower()
        for row in sessions:
            if row["session_id"] == session_reference:
                return row
            title = row.get("title")
            if isinstance(title, str) and title.lower() == reference:
                return row

        raise SessionCommandError(
            code="SESSION_NOT_FOUND",
            message=f"Session matching '{session_reference}' was not found.",
            guidance="Run 'session history' to find a valid session id.",
            exit_code=1,
        )

    def _load_summary_transcript(self, session: dict[str, Any]) -> tuple[str, str]:
        session_id = session["session_id"]
        metadata_root = self.store.metadata_file.parent.parent
        edited_path = metadata_root / f"transcripts/{session_id}-edited.md"

        raw_relative_path = session.get("transcript_file_path") or self.store.build_raw_transcript_path(
            session_id
        )
        raw_path = metadata_root / raw_relative_path

        target_path = edited_path if edited_path.exists() else raw_path
        source_name = "edited" if target_path == edited_path else "raw"
        if not target_path.exists():
            raise SessionCommandError(
                code="TRANSCRIPT_NOT_FOUND",
                message=f"No transcript found for session '{session_id}'.",
                guidance="Run transcription for this session first.",
                exit_code=1,
            )

        return target_path.read_text(encoding="utf-8"), source_name

    def list_note_templates(self) -> list[str]:
        """List available summary note templates."""
        preset_dir = Path(__file__).resolve().parent / "templates"
        user_dir = self.store.metadata_file.parent.parent / "templates"
        
        templates = set()
        for directory in (preset_dir, user_dir):
            if directory.exists() and directory.is_dir():
                for p in directory.glob("*.md"):
                    templates.add(p.stem)
                    
        return sorted(list(templates))

    def _resolve_note_template(self, template_name: str | None) -> tuple[str, str]:
        resolved_name = (template_name or DEFAULT_NOTE_TEMPLATE_NAME).strip()
        if not resolved_name:
            resolved_name = DEFAULT_NOTE_TEMPLATE_NAME
        if resolved_name.lower().endswith(".md"):
            resolved_name = resolved_name[:-3]

        preset_dir = Path(__file__).resolve().parent / "templates"
        user_dir = self.store.metadata_file.parent.parent / "templates"
        candidates = [
            preset_dir / f"{resolved_name}.md",
            user_dir / f"{resolved_name}.md",
        ]

        for path in candidates:
            if path.exists() and path.is_file():
                return resolved_name, path.read_text(encoding="utf-8")

        raise SessionCommandError(
            code="TEMPLATE_NOT_FOUND",
            message=f"Template '{resolved_name}' was not found.",
            guidance=f"Use a preset template or create {user_dir}/<name>.md.",
            exit_code=1,
        )
