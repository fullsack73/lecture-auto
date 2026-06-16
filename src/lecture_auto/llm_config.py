from __future__ import annotations

from dataclasses import dataclass


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMMA4_MODEL_CHOICES = (
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
)
GEMINI_MODEL_CHOICES = (
    DEFAULT_GEMINI_MODEL,
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    *GEMMA4_MODEL_CHOICES,
)
GEMINI_MODEL_ALIASES = {
    "gemini-3.1-flash-lite-preview": DEFAULT_GEMINI_MODEL,
}


def normalize_gemini_model_name(model_name: str) -> str:
    """Normalize known Gemini aliases and deprecated preview IDs."""
    normalized = (model_name or "").strip()
    if normalized.startswith("models/"):
        normalized = normalized.split("/", 1)[1]

    if normalized.startswith("gemini-3.0-"):
        normalized = normalized.replace("gemini-3.0-", "gemini-3-", 1)

    return GEMINI_MODEL_ALIASES.get(normalized, normalized)


@dataclass
class LLMConfig:
    """Configuration contract for selecting LLM provider options."""

    provider: str = "gemini"  # "gemini" or "ollama"
    api_key: str | None = None
    model_name: str = DEFAULT_GEMINI_MODEL
    thinking_level: str = "medium"  # "minimal", "low", "medium", "high"
    chunk_size: int = 4000  # Number of characters per chunk for long transcripts
    language: str | None = None
    ollama_base_url: str = "http://localhost:11434"  # Ollama server URL

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
        if self.provider == "gemini":
            if not self.api_key or not self.api_key.strip():
                raise ValueError("Google API key is required and cannot be empty.")
        elif self.provider == "ollama":
            # Ollama doesn't require API key
            pass
        else:
            raise ValueError(f"Invalid provider: {self.provider}. Must be 'gemini' or 'ollama'.")

        if self.chunk_size < 500:
            raise ValueError("chunk_size must be at least 500 characters.")
        
        valid_thinking_levels = {"minimal", "low", "medium", "high"}
        if self.thinking_level not in valid_thinking_levels:
            raise ValueError(
                f"thinking_level must be one of {valid_thinking_levels}, "
                f"got '{self.thinking_level}'."
            )
