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

    def resolve_chunk_size(self, text_length: int) -> int:
        """Resolves a practical chunk size based on transcript length.

        Keeps the configured chunk size as the minimum, then scales up for
        larger transcripts to reduce request count and provider pressure.
        """
        base_size = max(500, int(self.chunk_size))
        if text_length <= 0:
            return base_size

        adaptive_size = max(base_size, text_length // 6)
        return min(10000, adaptive_size)

    def validate(self) -> None:
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Gemini API key is required and cannot be empty.")

        if self.chunk_size < 500:
            raise ValueError("chunk_size must be at least 500 characters.")
        
        valid_thinking_levels = {"minimal", "low", "medium", "high"}
        if self.thinking_level not in valid_thinking_levels:
            raise ValueError(
                f"thinking_level must be one of {valid_thinking_levels}, "
                f"got '{self.thinking_level}'."
            )
