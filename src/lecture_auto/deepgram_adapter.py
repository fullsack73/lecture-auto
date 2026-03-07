"""Deepgram STT adapter using the official deepgram-sdk."""
from __future__ import annotations

import logging

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
            from deepgram import DeepgramClient, PrerecordedOptions, FileSource
        except ImportError as exc:
            raise STTConfigError(
                "deepgram-sdk is not installed. Run: pip install deepgram-sdk"
            ) from exc

        try:
            client = DeepgramClient(self._api_key)

            with open(audio_path, "rb") as audio_file:
                buffer_data = audio_file.read()

            payload: FileSource = {"buffer": buffer_data}

            options = PrerecordedOptions(
                model="nova-2",
                smart_format=True,
                diarize=self._diarization,
            )
            if self._language:
                options.language = self._language
            else:
                options.detect_language = True

            response = client.listen.rest.v("1").transcribe_file(payload, options)

            transcript_text = ""
            segments: list[DiarizedSegment] = []
            detected_language: str | None = self._language

            results = response.results
            if results and results.channels:
                channel = results.channels[0]
                if channel.alternatives:
                    alt = channel.alternatives[0]
                    transcript_text = alt.transcript or ""

                    if (
                        hasattr(alt, "paragraphs")
                        and alt.paragraphs
                        and hasattr(alt.paragraphs, "paragraphs")
                    ):
                        for para in alt.paragraphs.paragraphs:
                            speaker_label = f"Speaker {para.speaker + 1}" if hasattr(para, "speaker") else "Speaker"
                            for sentence in para.sentences:
                                segments.append(
                                    DiarizedSegment(
                                        speaker=speaker_label,
                                        start_time=sentence.start,
                                        end_time=sentence.end,
                                        text=sentence.text,
                                    )
                                )

                    if not segments and hasattr(alt, "words") and alt.words:
                        current_speaker: int | None = None
                        current_text_parts: list[str] = []
                        seg_start = 0.0

                        for word in alt.words:
                            word_speaker = getattr(word, "speaker", None)
                            if word_speaker != current_speaker:
                                if current_text_parts and current_speaker is not None:
                                    segments.append(
                                        DiarizedSegment(
                                            speaker=f"Speaker {current_speaker + 1}",
                                            start_time=seg_start,
                                            end_time=word.start,
                                            text=" ".join(current_text_parts),
                                        )
                                    )
                                current_speaker = word_speaker
                                current_text_parts = []
                                seg_start = word.start
                            current_text_parts.append(word.word)

                        if current_text_parts and current_speaker is not None:
                            segments.append(
                                DiarizedSegment(
                                    speaker=f"Speaker {current_speaker + 1}",
                                    start_time=seg_start,
                                    end_time=alt.words[-1].end,
                                    text=" ".join(current_text_parts),
                                )
                            )

                if hasattr(channel, "detected_language") and channel.detected_language:
                    detected_language = channel.detected_language

            return STTResult(
                transcript_text=transcript_text,
                provider="deepgram",
                mode="api",
                language=detected_language,
                segments=segments,
            )

        except Exception as exc:
            error_msg = str(exc).lower()
            if "401" in error_msg or "unauthorized" in error_msg or "forbidden" in error_msg:
                raise STTProviderAuthError(
                    f"Deepgram authentication failed: {exc}"
                ) from exc
            if "timeout" in error_msg or "connection" in error_msg or "network" in error_msg:
                raise STTTransientNetworkError(
                    f"Deepgram network error: {exc}"
                ) from exc
            raise STTTransientNetworkError(
                f"Deepgram transcription failed: {exc}"
            ) from exc
