from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

STTMode = Literal["local", "api"]

SUPPORTED_API_PROVIDERS = {"openai-compatible", "deepgram"}


@dataclass
class STTConfig:
    """Configuration contract for selecting STT mode and provider options."""

    mode: STTMode = "api"
    api_provider: str | None = "openai-compatible"
    api_key: str | None = None
    local_model_name: str | None = "base"
    language: str | None = None
    diarization: bool = False

    def validate(self) -> None:
        if self.mode not in {"local", "api"}:
            raise ValueError("Unsupported STT mode. Use 'local' or 'api'.")

        if self.mode == "api":
            if not self.api_provider or not self.api_provider.strip():
                raise ValueError("API provider is required when STT mode is 'api'.")
            if not self.api_key or not self.api_key.strip():
                raise ValueError("API key is required when STT mode is 'api'.")

        if self.mode == "local":
            if not self.local_model_name or not self.local_model_name.strip():
                raise ValueError("Local model name is required when STT mode is 'local'.")
