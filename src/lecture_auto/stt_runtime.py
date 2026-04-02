from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class STTRuntimeError(RuntimeError):
    """Base class for transcription runtime failures."""


class STTConfigError(STTRuntimeError):
    """Raised when STT mode/provider config is invalid."""


class STTProviderAuthError(STTRuntimeError):
    """Raised when STT provider credentials are invalid."""


class STTTransientNetworkError(STTRuntimeError):
    """Raised for retryable provider/network failures."""


class STTAudioDecodeError(STTRuntimeError):
    """Raised when the audio input cannot be decoded by STT runtime."""


@dataclass
class DiarizedSegment:
    """A single speaker-attributed segment of transcription."""

    speaker: str
    start_time: float
    end_time: float
    text: str


@dataclass
class STTResult:
    transcript_text: str
    provider: str
    mode: str
    language: str | None = None
    segments: list[DiarizedSegment] = field(default_factory=list)

    def to_plain_text(self) -> str:
        """Return a horizontal plain-text transcript."""
        if not self.segments:
            return self.transcript_text

        text_parts = [seg.text.strip() for seg in self.segments if seg.text.strip()]
        return " ".join(text_parts).strip()

    def to_diarized_markdown(self) -> str:
        """Format transcription with speaker diarization as Markdown."""
        if not self.segments:
            return self.transcript_text

        lines: list[str] = []
        current_speaker: str | None = None
        for seg in self.segments:
            if seg.speaker != current_speaker:
                current_speaker = seg.speaker
                lines.append(f"\n**{current_speaker}**\n")
            timestamp = f"[{_format_ts(seg.start_time)} - {_format_ts(seg.end_time)}]"
            lines.append(f"{timestamp} {seg.text}")

        return "\n".join(lines).strip()


def _format_ts(seconds: float) -> str:
    """Convert seconds to MM:SS format."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


class STTRuntimeAdapter(Protocol):
    def transcribe(self, *, audio_path: str) -> STTResult:
        ...


class LocalSTTRuntimeAdapter:
    """Deterministic local adapter used for non-device/unit-test environments."""

    def __init__(self, model_name: str = "base") -> None:
        self.model_name = model_name

    def transcribe(self, *, audio_path: str) -> STTResult:
        if not audio_path.strip():
            raise STTConfigError("Audio path is required for transcription.")
        return STTResult(
            transcript_text=f"[local:{self.model_name}] transcript for {audio_path}",
            provider="local-model",
            mode="local",
        )


class APISTTRuntimeAdapter:
    """Deterministic API adapter placeholder for contract and tests."""

    def __init__(self, provider: str, api_key: str) -> None:
        self.provider = provider
        self.api_key = api_key

    def transcribe(self, *, audio_path: str) -> STTResult:
        if not self.provider.strip():
            raise STTConfigError("API provider is required.")
        if not self.api_key.strip():
            raise STTProviderAuthError("API key is missing.")
        if not audio_path.strip():
            raise STTConfigError("Audio path is required for transcription.")

        return STTResult(
            transcript_text=f"[api:{self.provider}] transcript for {audio_path}",
            provider=self.provider,
            mode="api",
        )
