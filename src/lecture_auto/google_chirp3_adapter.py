"""Google Cloud Speech-to-Text v2 adapter using Chirp 3 model."""
from __future__ import annotations

import base64
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from lecture_auto.stt_config import STTConfig
from lecture_auto.stt_runtime import (
    DiarizedSegment,
    STTConfigError,
    STTProviderAuthError,
    STTResult,
    STTTransientNetworkError,
)

logger = logging.getLogger(__name__)

# Files larger than this threshold use batchRecognize (async) instead of recognize (sync).
# Google STT v2 synchronous recognize is limited to ~1 minute / ~10 MB.
_SYNC_SIZE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB

_BASE_URL = "https://speech.googleapis.com/v2"
_POLL_INTERVAL_SECONDS = 2
_POLL_TIMEOUT_SECONDS = 300
_LOCAL_CHUNK_SECONDS = 50


class GoogleChirp3STTRuntimeAdapter:
    """Transcribe audio via Google Cloud STT v2 using the Chirp 3 model.

    Authentication uses a GCP API key passed via STTConfig.api_key
    (set STT_API_KEY env var or ``lecture-auto config set --stt-api-key``).

    For local files, synchronous recognize is used (max ~10 MB / <60 sec).
    If local input is larger, the adapter auto-splits audio into short chunks
    and transcribes each chunk sequentially.
    For batch recognition, pass a Cloud Storage URI (gs://...) and this adapter
    will call batchRecognize and poll the operation.
    """

    def __init__(self, config: STTConfig) -> None:
        if not config.google_project_id or not config.google_project_id.strip():
            raise STTConfigError(
                "Google Cloud project ID is required for the 'google-chirp3' provider. "
                "Set it with: lecture-auto config set --google-project-id <your-project-id>"
            )
        self._api_key = (config.api_key or "").strip() or None
        self._gcp_credentials = self._load_adc()
        if not self._api_key and not self._gcp_credentials and not self._read_access_token():
            raise STTConfigError(
                "Google Cloud STT authentication is required. Run: "
                "gcloud auth application-default login"
            )
        self._project_id = config.google_project_id
        self._location = self._normalize_location(config.google_location)
        self._language = self._normalize_language(config.language)
        self._diarization = config.diarization

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(self, *, audio_path: str) -> STTResult:
        if not audio_path.strip():
            raise STTConfigError("Audio path is required for transcription.")

        try:
            import httpx
        except ImportError as exc:
            raise STTConfigError(
                "httpx is not installed. Run: pip install httpx"
            ) from exc

        if not self._language:
            raise STTConfigError(
                "Language must be specified in STT config for Google Chirp 3 "
                "(e.g. 'ko', 'en', 'ja')."
            )

        config_payload = self._build_recognition_config()
        source_is_gcs_uri = audio_path.startswith("gs://")

        if self._diarization and not source_is_gcs_uri:
            raise STTConfigError(
                "Chirp 3 diarization should be used with batchRecognize using a "
                "Cloud Storage URI (gs://...)."
            )

        try:
            with httpx.Client(timeout=_POLL_TIMEOUT_SECONDS + 30.0) as client:
                recognizer_base = self._resolve_recognizer_url(client)
                if source_is_gcs_uri:
                    response_data = self._recognize_batch(
                        client, config_payload, audio_path, recognizer_base
                    )
                else:
                    try:
                        with open(audio_path, "rb") as f:
                            audio_bytes = f.read()
                    except FileNotFoundError as exc:
                        raise STTConfigError(f"Audio file not found: {audio_path}") from exc

                    file_size = len(audio_bytes)
                    duration_seconds = self._probe_audio_duration(audio_path)
                    needs_chunking = (
                        file_size > _SYNC_SIZE_THRESHOLD_BYTES
                        or (duration_seconds is not None and duration_seconds > _LOCAL_CHUNK_SECONDS)
                    )
                    if needs_chunking:
                        reason = (
                            f"{file_size / (1024 * 1024):.1f} MB"
                            if file_size > _SYNC_SIZE_THRESHOLD_BYTES
                            else f"{duration_seconds:.0f}s > {_LOCAL_CHUNK_SECONDS}s limit"
                        )
                        logger.warning(
                            "Local audio (%s); using chunked synchronous "
                            "recognition for Google Chirp 3.",
                            reason,
                        )
                        return self._transcribe_large_local_file(
                            client=client,
                            config=config_payload,
                            audio_path=audio_path,
                            recognizer_base=recognizer_base,
                        )

                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                    response_data = self._recognize_sync(
                        client, config_payload, content_b64=audio_b64,
                        recognizer_base=recognizer_base,
                    )
        except STTProviderAuthError:
            raise
        except STTTransientNetworkError:
            raise
        except STTConfigError:
            raise
        except Exception as exc:
            self._reraise_as_stt_error(exc)

        return self._parse_response(response_data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_recognition_config(self) -> dict[str, Any]:
        features: dict[str, Any] = {"enableAutomaticPunctuation": True}
        if self._diarization:
            features["diarizationConfig"] = {"enableSpeakerDiarization": True}
            features["enableWordTimeOffsets"] = True

        return {
            "model": "chirp_3",
            "languageCodes": [self._language],
            "autoDecodingConfig": {},
            "features": features,
        }

    def _api_root(self) -> str:
        if self._location == "global":
            return _BASE_URL
        return f"https://{self._location}-speech.googleapis.com/v2"

    def _base_recognizer_url(self) -> str:
        return (
            f"{self._api_root()}/projects/{self._project_id}"
            f"/locations/{self._location}/recognizers/_"
        )

    def _resolve_recognizer_url(self, client: Any) -> str:
        del client
        return self._base_recognizer_url()

    def _recognize_sync(
        self,
        client: Any,
        config: dict[str, Any],
        *,
        content_b64: str | None = None,
        audio_uri: str | None = None,
        recognizer_base: str | None = None,
    ) -> dict[str, Any]:
        url = f"{recognizer_base or self._base_recognizer_url()}:recognize"
        body: dict[str, Any] = {"config": config}
        if content_b64:
            body["content"] = content_b64
        elif audio_uri:
            body["uri"] = audio_uri
        else:
            raise STTConfigError("Either content_b64 or audio_uri is required.")
        raw = client.post(url, json=body, **self._auth_kwargs())
        self._check_response_status(raw)
        return raw.json()

    def _recognize_batch(
        self, client: Any, config: dict[str, Any], audio_uri: str,
        recognizer_base: str | None = None,
    ) -> dict[str, Any]:
        url = f"{recognizer_base or self._base_recognizer_url()}:batchRecognize"
        body = {
            "config": config,
            "files": [{"uri": audio_uri}],
            "recognitionOutputConfig": {"inlineResponseConfig": {}},
        }
        raw = client.post(url, json=body, **self._auth_kwargs())
        self._check_response_status(raw)
        operation = raw.json()

        operation_name = operation.get("name") or ""
        if not operation_name:
            raise STTConfigError(
                "Google STT batchRecognize did not return an operation name."
            )

        return self._poll_operation(client, operation_name)

    def _poll_operation(self, client: Any, operation_name: str) -> dict[str, Any]:
        """Poll a long-running operation until done."""
        # operation_name is like
        # "projects/.../locations/global/operations/<id>"
        # The v2 poll endpoint is: GET /v2/{operation_name}
        poll_url = f"{self._api_root()}/{operation_name}"
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            raw = client.get(poll_url, **self._auth_kwargs())
            self._check_response_status(raw)
            data = raw.json()
            if data.get("done"):
                if "error" in data:
                    err = data["error"]
                    raise STTConfigError(
                        f"Google STT batch operation failed: {err.get('message', err)}"
                    )
                # batchRecognize wraps result in response.results
                response_wrapper = data.get("response") or {}
                results_map = response_wrapper.get("results") or {}
                # results_map is a dict keyed by filename/index; grab first entry
                for entry in results_map.values():
                    inline = (entry.get("inlineResult") or {})
                    transcript = (inline.get("transcript") or {})
                    if transcript:
                        return transcript
                    # Backward compatibility with deprecated response shape.
                    deprecated_transcript = entry.get("transcript") or {}
                    if deprecated_transcript:
                        return deprecated_transcript
                # Fallback — return the whole response if structure is unexpected
                return response_wrapper

            time.sleep(_POLL_INTERVAL_SECONDS)

        raise STTTransientNetworkError(
            f"Google STT batch operation timed out after {_POLL_TIMEOUT_SECONDS}s."
        )

    def _transcribe_large_local_file(
        self,
        *,
        client: Any,
        config: dict[str, Any],
        audio_path: str,
        recognizer_base: str | None = None,
    ) -> STTResult:
        """Split large local audio and transcribe each chunk via recognize."""
        chunks = self._split_audio_into_chunks(audio_path)
        if not chunks:
            raise STTConfigError("No audio chunks were produced from local file.")

        logger.warning(
            "Google Chirp 3 chunked transcription started: %d chunks.",
            len(chunks),
        )

        transcript_parts: list[str] = []
        try:
            for idx, chunk_path in enumerate(chunks, start=1):
                logger.warning(
                    "Google Chirp 3 transcribing chunk %d/%d...",
                    idx,
                    len(chunks),
                )
                with open(chunk_path, "rb") as f:
                    chunk_bytes = f.read()
                chunk_b64 = base64.b64encode(chunk_bytes).decode("ascii")
                chunk_response = self._recognize_sync(
                    client,
                    config,
                    content_b64=chunk_b64,
                    recognizer_base=recognizer_base,
                )
                chunk_result = self._parse_response(chunk_response)
                if chunk_result.transcript_text:
                    transcript_parts.append(chunk_result.transcript_text)
            logger.warning("Google Chirp 3 chunked transcription completed.")
        finally:
            for chunk_path in chunks:
                try:
                    Path(chunk_path).unlink(missing_ok=True)
                except OSError:
                    pass

        return STTResult(
            transcript_text=" ".join(transcript_parts).strip(),
            provider="google-chirp3",
            mode="api",
            language=self._language,
            segments=[],
        )

    def _probe_audio_duration(self, audio_path: str) -> float | None:
        """Return audio duration in seconds via ffprobe, or None on failure."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode == 0:
                return float(result.stdout.decode().strip())
        except (FileNotFoundError, ValueError):
            pass
        return None

    def _split_audio_into_chunks(self, audio_path: str) -> list[str]:
        """Split local audio into <= ~60s WAV chunks using ffmpeg."""
        try:
            temp_dir = tempfile.TemporaryDirectory(prefix="lecture_auto_chirp3_")
        except Exception as exc:
            raise STTConfigError(f"Failed to create temp directory: {exc}") from exc

        try:
            output_pattern = str(Path(temp_dir.name) / "chunk_%04d.wav")
            command = [
                "ffmpeg",
                "-y",
                "-i",
                audio_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-f",
                "segment",
                "-segment_time",
                str(_LOCAL_CHUNK_SECONDS),
                output_pattern,
            ]
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
                raise STTConfigError(
                    "Failed to split local audio with ffmpeg. "
                    f"Detail: {stderr or 'unknown ffmpeg error'}"
                )

            chunk_paths = sorted(Path(temp_dir.name).glob("chunk_*.wav"))
            if not chunk_paths:
                raise STTConfigError("ffmpeg did not generate any audio chunks.")

            materialized_paths: list[str] = []
            for chunk in chunk_paths:
                # Copy content into a second temp file that survives after temp_dir cleanup.
                with tempfile.NamedTemporaryFile(
                    prefix="lecture_auto_chirp3_chunk_",
                    suffix=".wav",
                    delete=False,
                ) as out:
                    out.write(chunk.read_bytes())
                    materialized_paths.append(out.name)
            return materialized_paths
        except FileNotFoundError as exc:
            raise STTConfigError(
                "ffmpeg is required to transcribe large local files with "
                "google-chirp3. Install ffmpeg and retry."
            ) from exc
        finally:
            temp_dir.cleanup()

    def _check_response_status(self, raw: Any) -> None:
        if raw.status_code in (401, 403):
            raise STTProviderAuthError(
                f"Google Cloud STT authentication failed "
                f"(HTTP {raw.status_code}): {raw.text}"
            )
        if raw.status_code >= 400:
            raise STTConfigError(
                f"Google Cloud STT request failed (HTTP {raw.status_code}): {raw.text}"
            )

    def _auth_kwargs(self) -> dict[str, Any]:
        # Priority 1: Application Default Credentials (auto-refreshing)
        if self._gcp_credentials is not None:
            token = self._get_adc_token(self._gcp_credentials)
            if token:
                return {"headers": {"Authorization": f"Bearer {token}"}}
        # Priority 2: manually exported env var token
        token = self._read_access_token()
        if token:
            return {"headers": {"Authorization": f"Bearer {token}"}}
        # Priority 3: API key
        if self._api_key:
            return {"params": {"key": self._api_key}}
        raise STTConfigError(
            "No Google Cloud STT auth method available. Run: "
            "gcloud auth application-default login"
        )

    @staticmethod
    def _load_adc() -> Any:
        """Load Application Default Credentials, returning None if unavailable."""
        try:
            import google.auth
            import google.auth.transport.requests
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            return credentials
        except Exception:
            return None

    @staticmethod
    def _get_adc_token(credentials: Any) -> str | None:
        """Refresh credentials if needed and return a valid Bearer token."""
        try:
            import google.auth.transport.requests
            request = google.auth.transport.requests.Request()
            if not credentials.valid:
                credentials.refresh(request)
            return credentials.token
        except Exception:
            return None

    @staticmethod
    def _read_access_token() -> str | None:
        token = os.environ.get("GOOGLE_ACCESS_TOKEN") or os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
        if token and token.strip():
            return token.strip()
        return None

    @staticmethod
    def _normalize_location(location: str | None) -> str:
        requested = (location or "us").strip() or "us"
        aliases = {
            "global": "us",
            "us-central1": "us",
        }
        normalized = aliases.get(requested, requested)
        if normalized != requested:
            logger.warning(
                "google-chirp3 location '%s' is remapped to '%s' to match the documented regional endpoint.",
                requested,
                normalized,
            )
        return normalized

    @staticmethod
    def _normalize_language(language: str | None) -> str | None:
        if language is None:
            return None
        requested = language.strip()
        if not requested:
            return requested
        if requested == "auto" or "-" in requested:
            return requested

        aliases = {
            "ko": "ko-KR",
            "en": "en-US",
            "ja": "ja-JP",
        }
        normalized = aliases.get(requested, requested)
        if normalized != requested:
            logger.warning(
                "google-chirp3 language '%s' is remapped to '%s'.",
                requested,
                normalized,
            )
        return normalized

    def _parse_response(self, data: dict[str, Any]) -> STTResult:
        """Parse a Google STT v2 recognizeResponse into STTResult."""
        results = data.get("results") or []

        text_parts: list[str] = []
        all_words: list[dict[str, Any]] = []

        for result in results:
            alternatives = result.get("alternatives") or []
            if not alternatives:
                continue
            best = alternatives[0]
            transcript = best.get("transcript") or ""
            if transcript:
                text_parts.append(transcript.strip())
            words = best.get("words") or []
            all_words.extend(words)

        transcript_text = " ".join(text_parts)

        segments: list[DiarizedSegment] = []
        if self._diarization and all_words:
            segments = self._extract_segments(all_words)

        return STTResult(
            transcript_text=transcript_text,
            provider="google-chirp3",
            mode="api",
            language=self._language,
            segments=segments,
        )

    def _extract_segments(self, words: list[dict[str, Any]]) -> list[DiarizedSegment]:
        """Group word-level results by speakerLabel into DiarizedSegment list."""
        segments: list[DiarizedSegment] = []
        current_speaker: str | None = None
        current_parts: list[str] = []
        seg_start = 0.0
        last_end = 0.0

        for word in words:
            speaker = str(word.get("speakerLabel") or "")
            if not speaker:
                speaker = "Speaker 1"
            word_text = word.get("word") or ""
            if not word_text:
                continue

            start = self._parse_duration(word.get("startOffset") or word.get("startTime") or "0s")
            end = self._parse_duration(word.get("endOffset") or word.get("endTime") or "0s")

            if speaker != current_speaker:
                if current_parts and current_speaker is not None:
                    segments.append(
                        DiarizedSegment(
                            speaker=current_speaker,
                            start_time=seg_start,
                            end_time=last_end,
                            text=" ".join(current_parts),
                        )
                    )
                current_speaker = speaker
                current_parts = []
                seg_start = start

            current_parts.append(word_text)
            last_end = end

        if current_parts and current_speaker is not None:
            segments.append(
                DiarizedSegment(
                    speaker=current_speaker,
                    start_time=seg_start,
                    end_time=last_end,
                    text=" ".join(current_parts),
                )
            )

        return segments

    @staticmethod
    def _parse_duration(value: Any) -> float:
        """Parse a Google duration string like '1.234s' or a plain float."""
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).rstrip("s").strip()
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def _reraise_as_stt_error(exc: Exception) -> None:
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg or "connection" in msg or "network" in msg:
            raise STTTransientNetworkError(
                f"Google Cloud STT network error: {exc}"
            ) from exc
        raise STTConfigError(f"Google Cloud STT transcription failed: {exc}") from exc
