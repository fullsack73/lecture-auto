from __future__ import annotations

import logging
from typing import Protocol

from lecture_auto.llm_config import LLMConfig

logger = logging.getLogger(__name__)


class LLMConfigError(Exception):
    """Configuration missing or invalid."""

class LLMProviderAuthError(Exception):
    """LLM provider authentication failed."""

class LLMTransientNetworkError(Exception):
    """Network connection or timeout error."""


class LLMProviderAdapter(Protocol):
    """Interface for LLM-based transcript refinement."""

    def refine_transcript(self, raw_text: str, context_topic: str | None = None) -> str:
        """Refines transcript by fixing typos, spacing, and wording, while preserving meaning."""
        ...


class GeminiLLMAdapter:
    """Implementation of Gemini API for transcript refinement."""

    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key or not config.api_key.strip():
            raise LLMConfigError("Gemini API key is required.")
        self.config = config

        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise LLMConfigError(
                "google-generativeai is not installed. Run: pip install google-generativeai"
            ) from exc

        genai.configure(api_key=self.config.api_key)
        self.model = genai.GenerativeModel(self.config.model_name)

    def refine_transcript(self, raw_text: str, context_topic: str | None = None) -> str:
        """Refines the transcript in chunks using the Gemini model."""
        if not raw_text or not raw_text.strip():
            return raw_text

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded
        except ImportError:
            PermissionDenied = Exception
            DeadlineExceeded = Exception

        topic_prompt = f"The overall topic or subject is '{context_topic}'. " if context_topic else ""
        system_instructions = (
            f"You are a helpful assistant that refines lecture transcripts. {topic_prompt}"
            "Your task is to improve the provided transcript chunk by fixing typos, spacing, punctuation, "
            "and awkward wording. You must preserve the original lecture meaning and terminology entirely. "
            "Only output the refined text, without any conversational padding."
        )

        chunk_size = self.config.chunk_size
        refined_chunks = []
        start_idx = 0

        try:
            while start_idx < len(raw_text):
                end_idx = min(start_idx + chunk_size, len(raw_text))
                
                if end_idx < len(raw_text):
                    last_space = raw_text.rfind(' ', start_idx, end_idx)
                    if last_space > start_idx + chunk_size // 2:
                        end_idx = last_space
                
                chunk = raw_text[start_idx:end_idx]
                
                prompt = f"{system_instructions}\n\nRefine the following text:\n{chunk}"
                
                # We use model.generate_content for Gemini API call
                response = self.model.generate_content(prompt)
                refined_chunks.append(response.text.strip())
                
                start_idx = end_idx + 1 if end_idx < len(raw_text) and raw_text[end_idx] == ' ' else end_idx

            return "\n".join(refined_chunks)

        except PermissionDenied as exc:
            raise LLMProviderAuthError(f"Gemini authentication failed: {exc}") from exc
        except DeadlineExceeded as exc:
            raise LLMTransientNetworkError(f"Gemini network/timeout error: {exc}") from exc
        except Exception as exc:
            error_msg = str(exc).lower()
            if "api_key_invalid" in error_msg or "unauthorized" in error_msg or "401" in error_msg or "403" in error_msg:
                raise LLMProviderAuthError(f"Gemini authentication failed: {exc}") from exc
            if "timeout" in error_msg or "connection" in error_msg or "503" in error_msg or "504" in error_msg:
                raise LLMTransientNetworkError(f"Gemini network error: {exc}") from exc
            
            raise LLMTransientNetworkError(f"Gemini LLM request failed: {exc}") from exc
