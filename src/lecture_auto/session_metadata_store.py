from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any

METADATA_FIELDS = (
    "session_id",
    "date",
    "title",
    "course",
    "status",
    "job_status",
    "job_attempts",
    "job_timestamps",
    "job_error_code",
    "import_source_audio_path",
    "audio_file_path",
    "transcript_file_path",
    "transcription_status",
    "transcription_error_category",
    "transcription_retry_count",
    "timestamps",
    "naming_pending",
)

REQUIRED_FIELDS = {"session_id", "date", "status", "timestamps", "naming_pending"}


class SessionMetadataValidationError(ValueError):
    """Raised when session metadata does not match the expected schema."""


class SessionMetadataStore:
    def __init__(self, metadata_file: Path) -> None:
        self.metadata_file = metadata_file

    def load_all(self) -> list[dict[str, Any]]:
        if not self.metadata_file.exists():
            return []

        with self.metadata_file.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if not isinstance(payload, list):
            raise SessionMetadataValidationError("Metadata file must contain a list of sessions")

        validated: list[dict[str, Any]] = []
        for entry in payload:
            validated.append(self._normalize_session(entry))
        return validated

    def upsert(self, session: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_session(session)
        current = self.load_all()

        replaced = False
        updated: list[dict[str, Any]] = []
        for row in current:
            if row["session_id"] == normalized["session_id"]:
                updated.append(normalized)
                replaced = True
            else:
                updated.append(row)

        if not replaced:
            updated.append(normalized)

        self._safe_write(updated)
        return normalized

    def delete(self, session_id: str) -> bool:
        current = self.load_all()
        filtered = [row for row in current if row["session_id"] != session_id]
        if len(filtered) == len(current):
            return False

        self._safe_write(filtered)
        return True

    def list_recent_first(self) -> list[dict[str, Any]]:
        sessions = self.load_all()
        return sorted(sessions, key=lambda row: row["date"], reverse=True)

    def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        for row in self.load_all():
            if row["session_id"] == session_id:
                return row
        return None

    def _normalize_session(self, session: Any) -> dict[str, Any]:
        if not isinstance(session, dict):
            raise SessionMetadataValidationError("Session metadata must be a JSON object")

        missing = REQUIRED_FIELDS - set(session.keys())
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise SessionMetadataValidationError(f"Missing required fields: {missing_list}")

        normalized: dict[str, Any] = {}
        for key in METADATA_FIELDS:
            if key in session:
                normalized[key] = session[key]
            elif key in (
                "title",
                "course",
                "audio_file_path",
                "job_status",
                "job_error_code",
                "import_source_audio_path",
                "transcript_file_path",
                "transcription_status",
                "transcription_error_category",
            ):
                normalized[key] = None
            elif key == "job_attempts":
                normalized[key] = 0
            elif key == "transcription_retry_count":
                normalized[key] = 0
            elif key == "job_timestamps":
                normalized[key] = {}

        self._validate_types(normalized)
        return normalized

    def _validate_types(self, session: dict[str, Any]) -> None:
        string_fields = ("session_id", "date", "status")
        for field in string_fields:
            if not isinstance(session[field], str) or not session[field].strip():
                raise SessionMetadataValidationError(f"Field '{field}' must be a non-empty string")

        optional_string_fields = (
            "title",
            "course",
            "audio_file_path",
            "transcript_file_path",
            "transcription_status",
            "transcription_error_category",
        )
        for field in optional_string_fields:
            value = session[field]
            if value is not None and not isinstance(value, str):
                raise SessionMetadataValidationError(f"Field '{field}' must be a string or null")

        if session["job_status"] is not None and not isinstance(session["job_status"], str):
            raise SessionMetadataValidationError("Field 'job_status' must be a string or null")

        if not isinstance(session["job_attempts"], int) or session["job_attempts"] < 0:
            raise SessionMetadataValidationError("Field 'job_attempts' must be a non-negative integer")

        if not isinstance(session["job_timestamps"], dict):
            raise SessionMetadataValidationError("Field 'job_timestamps' must be an object")

        if session["job_error_code"] is not None and not isinstance(session["job_error_code"], str):
            raise SessionMetadataValidationError("Field 'job_error_code' must be a string or null")

        import_source = session["import_source_audio_path"]
        if import_source is not None and not isinstance(import_source, str):
            raise SessionMetadataValidationError(
                "Field 'import_source_audio_path' must be a string or null"
            )

        if session["audio_file_path"] is not None:
            self._validate_audio_path_for_session(
                session_id=session["session_id"],
                audio_file_path=session["audio_file_path"],
            )

        transcript_file_path = session["transcript_file_path"]
        if transcript_file_path is not None:
            self._validate_transcript_path_for_session(
                session_id=session["session_id"],
                transcript_file_path=transcript_file_path,
            )

        if (
            not isinstance(session["transcription_retry_count"], int)
            or session["transcription_retry_count"] < 0
        ):
            raise SessionMetadataValidationError(
                "Field 'transcription_retry_count' must be a non-negative integer"
            )

        if not isinstance(session["timestamps"], dict):
            raise SessionMetadataValidationError("Field 'timestamps' must be an object")

        if not isinstance(session["naming_pending"], bool):
            raise SessionMetadataValidationError("Field 'naming_pending' must be a boolean")

    def build_recording_path(self, session_id: str, extension: str = "wav") -> str:
        if not session_id.strip():
            raise SessionMetadataValidationError("session_id must be a non-empty string")

        clean_extension = extension.lstrip(".").strip()
        if not clean_extension:
            raise SessionMetadataValidationError("Recording extension must be a non-empty string")

        return f"recordings/{session_id}.{clean_extension}"

    def build_imported_audio_path(self, session_id: str, extension: str, *, ordinal: int = 1) -> str:
        if not session_id.strip():
            raise SessionMetadataValidationError("session_id must be a non-empty string")
        if ordinal < 1:
            raise SessionMetadataValidationError("ordinal must be >= 1")

        clean_extension = extension.lstrip(".").strip().lower()
        if not clean_extension:
            raise SessionMetadataValidationError("Import extension must be a non-empty string")

        suffix = "" if ordinal == 1 else f"-{ordinal}"
        return f"recordings/{session_id}-imported{suffix}.{clean_extension}"

    def next_imported_audio_path(self, session_id: str, extension: str) -> str:
        normalized_extension = extension.lstrip(".").strip().lower()
        existing_paths = {
            row["audio_file_path"]
            for row in self.load_all()
            if row.get("audio_file_path") is not None
        }

        ordinal = 1
        while True:
            candidate = self.build_imported_audio_path(
                session_id,
                normalized_extension,
                ordinal=ordinal,
            )
            if candidate not in existing_paths:
                return candidate
            ordinal += 1

    def build_raw_transcript_path(self, session_id: str, extension: str = "md") -> str:
        if not session_id.strip():
            raise SessionMetadataValidationError("session_id must be a non-empty string")

        clean_extension = extension.lstrip(".").strip().lower()
        if clean_extension not in {"md", "txt"}:
            raise SessionMetadataValidationError("Transcript extension must be 'md' or 'txt'")

        return f"transcripts/{session_id}-raw.{clean_extension}"

    def build_note_path(self, session_id: str, extension: str = "md") -> str:
        if not session_id.strip():
            raise SessionMetadataValidationError("session_id must be a non-empty string")

        clean_extension = extension.lstrip(".").strip().lower()
        if clean_extension != "md":
            raise SessionMetadataValidationError("Note extension must be 'md'")

        return f"notes/{session_id}.{clean_extension}"

    def _validate_audio_path_for_session(self, session_id: str, audio_file_path: str) -> None:
        expected_prefixes = (
            f"recordings/{session_id}.",
            f"recordings/{session_id}-imported.",
            f"recordings/{session_id}-imported-",
        )
        normalized = PurePosixPath(audio_file_path).as_posix()

        if not normalized.startswith(expected_prefixes):
            raise SessionMetadataValidationError(
                "Field 'audio_file_path' must follow recordings/{session_id}.* convention"
            )

    def _validate_transcript_path_for_session(
        self,
        session_id: str,
        transcript_file_path: str,
    ) -> None:
        normalized = PurePosixPath(transcript_file_path).as_posix()
        expected_prefix = f"transcripts/{session_id}-raw."
        if not normalized.startswith(expected_prefix):
            raise SessionMetadataValidationError(
                "Field 'transcript_file_path' must follow transcripts/{session_id}-raw.* convention"
            )

    def _safe_write(self, sessions: list[dict[str, Any]]) -> None:
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

        temp_name: str | None = None
        with NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.metadata_file.parent, delete=False
        ) as temp_file:
            json.dump(sessions, temp_file, ensure_ascii=False, separators=(",", ":"))
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_name = temp_file.name

        try:
            os.replace(temp_name, self.metadata_file)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.remove(temp_name)
