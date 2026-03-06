from __future__ import annotations

from dataclasses import dataclass
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
class STTResult:
    transcript_text: str
    provider: str
    mode: str


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
