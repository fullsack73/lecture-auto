from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration contract for selecting LLM provider options."""

    api_key: str | None = None
    model_name: str = "gemini-1.5-flash"
    chunk_size: int = 4000  # Number of characters per chunk for long transcripts

    def validate(self) -> None:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Gemini API key is required and cannot be empty.")
