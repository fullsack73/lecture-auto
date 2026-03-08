"""Deepgram STT adapter using the official deepgram-sdk."""
from __future__ import annotations

import logging
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
        except ImportError as exc:
            raise STTConfigError(
                "httpx is not installed. Run: pip install httpx"
            ) from exc

        try:
            with open(audio_path, "rb") as audio_file:
                buffer_data = audio_file.read()

            params: dict[str, str] = {
                "model": "nova-2",
                "smart_format": "true",
            }
            if self._diarization:
                params["diarize"] = "true"
                params["paragraphs"] = "true"
            if self._language:
                params["language"] = self._language
            else:
                params["detect_language"] = "true"

            headers = {
                "Authorization": f"Token {self._api_key}",
                "Content-Type": "audio/wav",
            }

            with httpx.Client(timeout=None) as client:
                raw_response = client.post(
                    "https://api.deepgram.com/v1/listen",
                    params=params,
                    headers=headers,
                    content=buffer_data,
                )

            if raw_response.status_code == 401 or raw_response.status_code == 403:
                raise STTProviderAuthError(
                    f"Deepgram authentication failed (HTTP {raw_response.status_code}): {raw_response.text}"
                )

            raw_response.raise_for_status()
            response = raw_response.json()

            transcript_text = ""
            segments: list[DiarizedSegment] = []
            detected_language: str | None = self._language

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

                channel_language = self._field(channel, "detected_language")
                if channel_language:
                    detected_language = channel_language

            return STTResult(
                transcript_text=transcript_text,
                provider="deepgram",
                mode="api",
                language=detected_language,
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
