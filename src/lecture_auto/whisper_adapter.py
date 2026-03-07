"""Local STT adapter using faster-whisper for Whisper model inference."""
from __future__ import annotations

import logging

from lecture_auto.stt_config import STTConfig
from lecture_auto.stt_runtime import (
    DiarizedSegment,
    STTAudioDecodeError,
    STTConfigError,
    STTResult,
)

logger = logging.getLogger(__name__)


class FasterWhisperSTTRuntimeAdapter:
    """Transcribe audio locally using faster-whisper with large-v3 support."""

    def __init__(self, config: STTConfig) -> None:
        model_name = config.local_model_name or "large-v3"
        self._model_name = model_name
        self._language = config.language
        self._diarization = config.diarization
        self._model = None

    def _load_model(self):
        """Lazy-load the faster-whisper model on first transcription call."""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise STTConfigError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            ) from exc

        logger.info("Loading faster-whisper model: %s", self._model_name)
        self._model = WhisperModel(self._model_name, compute_type="int8")
        return self._model

    def transcribe(self, *, audio_path: str) -> STTResult:
        if not audio_path.strip():
            raise STTConfigError("Audio path is required for transcription.")

        model = self._load_model()

        transcribe_kwargs: dict = {}
        if self._language:
            transcribe_kwargs["language"] = self._language

        try:
            raw_segments, info = model.transcribe(audio_path, **transcribe_kwargs)
        except Exception as exc:
            error_msg = str(exc).lower()
            if "no such file" in error_msg or "not found" in error_msg:
                raise STTConfigError(f"Audio file not found: {audio_path}") from exc
            raise STTAudioDecodeError(f"Failed to decode audio: {exc}") from exc

        detected_language = getattr(info, "language", None) or self._language

        segments: list[DiarizedSegment] = []
        text_parts: list[str] = []

        for seg in raw_segments:
            text_parts.append(seg.text.strip())
            segments.append(
                DiarizedSegment(
                    speaker="Speaker 1",
                    start_time=seg.start,
                    end_time=seg.end,
                    text=seg.text.strip(),
                )
            )

        transcript_text = " ".join(text_parts)

        return STTResult(
            transcript_text=transcript_text,
            provider="faster-whisper",
            mode="local",
            language=detected_language,
            segments=segments,
        )
