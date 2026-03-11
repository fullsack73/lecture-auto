"""Google Cloud Speech-to-Text v2 adapter using Chirp 3 model."""
from __future__ import annotations

import base64
import logging
import os
import time
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


class GoogleChirp3STTRuntimeAdapter:
    """Transcribe audio via Google Cloud STT v2 using the Chirp 3 model.

    Authentication uses a GCP API key passed via STTConfig.api_key
    (set STT_API_KEY env var or ``lecture-auto config set --stt-api-key``).

    Files smaller than 10 MB are transcribed synchronously.
    Larger files are submitted as a batch job and polled until complete.
    """

    def __init__(self, config: STTConfig) -> None:
        if not config.api_key or not config.api_key.strip():
            raise STTConfigError("Google Cloud STT API key is required.")
        if not config.google_project_id or not config.google_project_id.strip():
            raise STTConfigError(
                "Google Cloud project ID is required for the 'google-chirp3' provider. "
                "Set it with: lecture-auto config set --google-project-id <your-project-id>"
            )
        self._api_key = config.api_key
        self._project_id = config.google_project_id
        self._language = config.language
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

        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
        except FileNotFoundError as exc:
            raise STTConfigError(f"Audio file not found: {audio_path}") from exc

        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        file_size = len(audio_bytes)

        config_payload = self._build_recognition_config()

        try:
            with httpx.Client(timeout=_POLL_TIMEOUT_SECONDS + 30.0) as client:
                if file_size <= _SYNC_SIZE_THRESHOLD_BYTES:
                    response_data = self._recognize_sync(
                        client, config_payload, audio_b64
                    )
                else:
                    logger.info(
                        "Audio file is %.1f MB; using batchRecognize.",
                        file_size / (1024 * 1024),
                    )
                    response_data = self._recognize_batch(
                        client, config_payload, audio_b64
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

        return {
            "model": "chirp_3",
            "languageCodes": [self._language],
            "features": features,
        }

    def _base_recognizer_url(self) -> str:
        return (
            f"{_BASE_URL}/projects/{self._project_id}"
            "/locations/global/recognizers/_"
        )

    def _recognize_sync(
        self, client: Any, config: dict[str, Any], audio_b64: str
    ) -> dict[str, Any]:
        url = f"{self._base_recognizer_url()}:recognize"
        body = {"config": config, "content": audio_b64}
        raw = client.post(url, params={"key": self._api_key}, json=body)
        self._check_response_status(raw)
        return raw.json()

    def _recognize_batch(
        self, client: Any, config: dict[str, Any], audio_b64: str
    ) -> dict[str, Any]:
        url = f"{self._base_recognizer_url()}:batchRecognize"
        body = {
            "config": config,
            "files": [{"content": audio_b64}],
            "recognitionOutputConfig": {"inlineResponseConfig": {}},
        }
        raw = client.post(url, params={"key": self._api_key}, json=body)
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
        poll_url = f"https://speech.googleapis.com/v2/{operation_name}"
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            raw = client.get(poll_url, params={"key": self._api_key})
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
                    return inline
                # Fallback — return the whole response if structure is unexpected
                return response_wrapper

            time.sleep(_POLL_INTERVAL_SECONDS)

        raise STTTransientNetworkError(
            f"Google STT batch operation timed out after {_POLL_TIMEOUT_SECONDS}s."
        )

    def _check_response_status(self, raw: Any) -> None:
        if raw.status_code in (401, 403):
            raise STTProviderAuthError(
                f"Google Cloud STT authentication failed "
                f"(HTTP {raw.status_code}): {raw.text}"
            )
        raw.raise_for_status()

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
