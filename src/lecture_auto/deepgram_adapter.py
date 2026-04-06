"""Deepgram STT adapter using the official deepgram-sdk."""
from __future__ import annotations

import logging
import os
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


class DeepgramSTTRuntimeAdapter:
    """Transcribe audio via Deepgram API with speaker diarization support."""

    def __init__(self, config: STTConfig) -> None:
        if not config.api_key or not config.api_key.strip():
            raise STTConfigError("Deepgram API key is required.")
        self._api_key = config.api_key
        self._language = config.language
        self._diarization = config.diarization

    def transcribe(self, *, audio_path: str) -> STTResult:
        if not audio_path.strip():
            raise STTConfigError("Audio path is required for transcription.")

        try:
            import httpx
            import time
        except ImportError as exc:
            raise STTConfigError(
                "httpx is not installed. Run: pip install httpx"
            ) from exc

        try:
            params: dict[str, str] = {
                "model": "nova-3",
                "smart_format": "true",
                "prerecorded": "true",
            }
            if self._diarization:
                params["diarize"] = "true"
                params["paragraphs"] = "true"
            if not self._language:
                raise STTConfigError(
                    "Language must be specified in STT config for Deepgram "
                    "(e.g. 'ko', 'en', 'ja')."
                )
            params["language"] = self._language

            ext = os.path.splitext(audio_path)[1].lower()
            content_type_map = {
                ".wav": "audio/wav",
                ".mp3": "audio/mp3",
                ".m4a": "audio/mp4",
                ".flac": "audio/flac",
                ".ogg": "audio/ogg",
            }
            content_type = content_type_map.get(ext, "audio/wav")

            headers = {
                "Authorization": f"Token {self._api_key}",
                "Content-Type": content_type,
            }

            with httpx.Client(timeout=300.0) as client:
                with open(audio_path, "rb") as audio_file:
                    # Stream upload to avoid loading large files into memory
                    raw_response = client.post(
                        "https://api.deepgram.com/v1/listen",
                        params=params,
                        headers=headers,
                        content=audio_file,
                    )

                if raw_response.status_code == 401 or raw_response.status_code == 403:
                    raise STTProviderAuthError(
                        f"Deepgram authentication failed (HTTP {raw_response.status_code}): {raw_response.text}"
                    )

                raw_response.raise_for_status()
                response = raw_response.json()

            # If the response doesn't contain results, it might be an async job
            # (Though /v1/listen usually returns sync unless specified or too large)
            # To be robust for very long files, we check for a request_id or if results are missing.
            results = self._field(response, "results")
            if results is None:
                request_id = self._field(response, "request_id")
                if request_id:
                    response = self._poll_for_result(audio_path, request_id)
                else:
                    # This case shouldn't happen with /v1/listen but good for safety
                    raise STTConfigError(f"Deepgram response missing results and request_id: {response}")

            transcript_text = ""
            segments: list[DiarizedSegment] = []
            results = self._field(response, "results")
            channels = self._field(results, "channels") or []
            if channels:
                channel = channels[0]
                alternatives = self._field(channel, "alternatives") or []
                if alternatives:
                    alt = alternatives[0]
                    transcript_text = self._field(alt, "transcript") or ""

                    if self._diarization:
                        segments = self._extract_segments(alt)

            return STTResult(
                transcript_text=transcript_text,
                provider="deepgram",
                mode="api",
                language=self._language,
                segments=segments,
            )

        except FileNotFoundError as exc:
            raise STTConfigError(f"Audio file not found: {audio_path}") from exc
        except STTProviderAuthError:
            raise
        except Exception as exc:
            error_msg = str(exc).lower()
            if "401" in error_msg or "unauthorized" in error_msg or "forbidden" in error_msg:
                raise STTProviderAuthError(
                    f"Deepgram authentication failed: {exc}"
                ) from exc
            if "timeout" in error_msg or "timed out" in error_msg or "connection" in error_msg or "network" in error_msg:
                raise STTTransientNetworkError(
                    f"Deepgram network error: {exc}"
                ) from exc
            raise STTConfigError(
                f"Deepgram transcription failed: {exc}"
            ) from exc

    def _poll_for_result(self, audio_path: str, request_id: str) -> dict[str, Any]:
        """Poll Deepgram API until the asynchronous transcription is complete."""
        import httpx
        import time

        headers = {"Authorization": f"Token {self._api_key}"}
        url = f"https://api.deepgram.com/v1/listen?request_id={request_id}"

        max_timeout = 1200  # 20 minutes
        start_time = time.time()
        poll_interval = 2.0

        with httpx.Client(timeout=30.0) as client:
            while True:
                if time.time() - start_time > max_timeout:
                    raise STTTransientNetworkError(
                        f"Deepgram transcription timed out after {max_timeout} seconds."
                    )

                raw_response = client.get(url, headers=headers)

                if raw_response.status_code == 401 or raw_response.status_code == 403:
                    raise STTProviderAuthError(
                        f"Deepgram authentication failed during polling (HTTP {raw_response.status_code}): {raw_response.text}"
                    )

                raw_response.raise_for_status()
                response = raw_response.json()

                # Check if transcription is complete.
                # Deepgram async results typically contain 'results' when done.
                if self._field(response, "results") is not None:
                    return response

                # Otherwise, wait and poll again
                time.sleep(poll_interval)
                # Exponential backoff to be polite, capped at 10s
                poll_interval = min(poll_interval * 1.5, 10.0)

    def _field(self, obj: Any, name: str) -> Any:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, name, None)

    def _extract_segments(self, alt: Any) -> list[DiarizedSegment]:
        segments: list[DiarizedSegment] = []

        paragraphs = self._field(self._field(alt, "paragraphs"), "paragraphs") or []
        for para in paragraphs:
            para_speaker = self._field(para, "speaker")
            speaker_label = f"Speaker {int(para_speaker) + 1}" if para_speaker is not None else "Speaker"
            sentences = self._field(para, "sentences") or []
            for sentence in sentences:
                text = self._field(sentence, "text") or ""
                if not text:
                    continue
                segments.append(
                    DiarizedSegment(
                        speaker=speaker_label,
                        start_time=float(self._field(sentence, "start") or 0.0),
                        end_time=float(self._field(sentence, "end") or 0.0),
                        text=text,
                    )
                )

        if segments:
            return segments

        words = self._field(alt, "words") or []
        current_speaker: int | None = None
        current_text_parts: list[str] = []
        seg_start = 0.0
        last_end = 0.0

        for word in words:
            word_speaker = self._field(word, "speaker")
            start = float(self._field(word, "start") or last_end)
            end = float(self._field(word, "end") or start)
            text = self._field(word, "word") or ""
            if not text:
                continue

            if word_speaker != current_speaker:
                if current_text_parts and current_speaker is not None:
                    segments.append(
                        DiarizedSegment(
                            speaker=f"Speaker {current_speaker + 1}",
                            start_time=seg_start,
                            end_time=last_end,
                            text=" ".join(current_text_parts),
                        )
                    )
                current_speaker = word_speaker
                current_text_parts = []
                seg_start = start

            current_text_parts.append(text)
            last_end = end

        if current_text_parts and current_speaker is not None:
            segments.append(
                DiarizedSegment(
                    speaker=f"Speaker {current_speaker + 1}",
                    start_time=seg_start,
                    end_time=last_end,
                    text=" ".join(current_text_parts),
                )
            )

        return segments
