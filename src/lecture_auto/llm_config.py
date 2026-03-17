from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration contract for selecting LLM provider options."""

    api_key: str | None = None
    model_name: str = "gemini-3.1-flash-lite-preview"
    thinking_level: str = "medium"  # "minimal", "low", "medium", "high"
    chunk_size: int = 4000  # Number of characters per chunk for long transcripts
    language: str | None = None

    def validate(self) -> None:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Gemini API key is required and cannot be empty.")
        
        valid_thinking_levels = {"minimal", "low", "medium", "high"}
        if self.thinking_level not in valid_thinking_levels:
            raise ValueError(
                f"thinking_level must be one of {valid_thinking_levels}, "
                f"got '{self.thinking_level}'."
            )
