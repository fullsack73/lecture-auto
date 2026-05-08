from __future__ import annotations

from dataclasses import dataclass
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
    use_dynaudnorm: bool = False
    dynaudnorm_f: int | None = None
    dynaudnorm_g: int | None = None
    gain_db: float | None = None


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

        if self.dynaudnorm_f is not None and (self.dynaudnorm_f < 10 or self.dynaudnorm_f > 8000):
            raise ValueError("dynaudnorm_f must be between 10 and 8000.")
        if self.dynaudnorm_g is not None and (self.dynaudnorm_g < 3 or self.dynaudnorm_g > 301 or self.dynaudnorm_g % 2 == 0):
            raise ValueError("dynaudnorm_g must be an odd integer between 3 and 301.")
        if self.gain_db is not None and (self.gain_db < -60.0 or self.gain_db > 60.0):
            raise ValueError("gain_db must be between -60.0 and 60.0.")
