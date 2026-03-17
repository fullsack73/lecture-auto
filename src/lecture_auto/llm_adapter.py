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

    def generate_notes(
        self,
        transcript: str,
        template: str,
        context_topic: str | None = None,
    ) -> str:
        """Generates notes from transcript text and a markdown template."""
        ...


class GeminiLLMAdapter:
    """Implementation of Gemini API for transcript refinement."""

    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key or not config.api_key.strip():
            raise LLMConfigError("Gemini API key is required.")
        self.config = config

        try:
            from google import genai
        except ImportError as exc:
            raise LLMConfigError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

        self.client = genai.Client(api_key=self.config.api_key)

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """Normalizes common Gemini model aliases to API-accepted IDs."""
        normalized = (model_name or "").strip()
        if normalized.startswith("models/"):
            normalized = normalized.split("/", 1)[1]

        # Gemini 3 preview IDs use `gemini-3-*`, not `gemini-3.0-*`.
        if normalized.startswith("gemini-3.0-"):
            normalized = normalized.replace("gemini-3.0-", "gemini-3-", 1)

        return normalized

    def refine_transcript(self, raw_text: str, context_topic: str | None = None) -> str:
        """Refines the transcript in chunks using the Gemini model."""
        if not raw_text or not raw_text.strip():
            return raw_text

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded
            from google.genai import types
        except ImportError:
            PermissionDenied = Exception
            DeadlineExceeded = Exception
            types = None

        topic_prompt = f"The overall topic or subject is '{context_topic}'. " if context_topic else ""
        lang_prompt = f"Output your response entirely in {self.config.language}. " if self.config.language else ""
        system_instructions = (
            f"You are a helpful assistant that refines lecture transcripts. {topic_prompt}"
            "Your task is to improve the provided transcript chunk by fixing typos, spacing, punctuation, "
            "and awkward wording. You must preserve the original lecture meaning and terminology entirely. "
            f"{lang_prompt}"
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
                
                prompt = f"Refine the following text:\n{chunk}"

                config_dict = {"system_instruction": system_instructions}
                if types:
                    config_dict["thinking_config"] = types.ThinkingConfig(
                        thinking_level=self.config.thinking_level
                    )

                response = self.client.models.generate_content(
                    model=self._normalize_model_name(self.config.model_name),
                    contents=prompt,
                    config=config_dict,
                )
                text = (getattr(response, "text", "") or "").strip()
                refined_chunks.append(text)
                
                start_idx = end_idx + 1 if end_idx < len(raw_text) and raw_text[end_idx] == ' ' else end_idx

            return "\n".join(refined_chunks)

        except PermissionDenied as exc:
            raise LLMProviderAuthError(f"Gemini authentication failed: {exc}") from exc
        except DeadlineExceeded as exc:
            raise LLMTransientNetworkError(f"Gemini network/timeout error: {exc}") from exc
        except Exception as exc:
            error_msg = str(exc).lower()
            if "404" in error_msg or "model" in error_msg and "not found" in error_msg:
                raise LLMConfigError(f"Gemini model configuration failed: {exc}") from exc
            if "api_key_invalid" in error_msg or "unauthorized" in error_msg or "401" in error_msg or "403" in error_msg:
                raise LLMProviderAuthError(f"Gemini authentication failed: {exc}") from exc
            if "timeout" in error_msg or "connection" in error_msg or "503" in error_msg or "504" in error_msg:
                raise LLMTransientNetworkError(f"Gemini network error: {exc}") from exc
            
            raise LLMTransientNetworkError(f"Gemini LLM request failed: {exc}") from exc

    def generate_notes(
        self,
        transcript: str,
        template: str,
        context_topic: str | None = None,
    ) -> str:
        """Generates lecture notes from transcript text and template in chunks."""
        if not transcript or not transcript.strip():
            return transcript

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded
            from google.genai import types
        except ImportError:
            PermissionDenied = Exception
            DeadlineExceeded = Exception
            types = None

        topic_prompt = f"The lecture topic is '{context_topic}'. " if context_topic else ""
        lang_prompt = f"Output your response entirely in {self.config.language}. " if self.config.language else ""
        system_instructions = (
            f"You are a helpful assistant that generates lecture notes. {topic_prompt}"
            "Use the provided markdown template exactly as the output structure. "
            "Fill each section with concise, accurate lecture notes from the transcript. "
            f"{lang_prompt}"
            "Do not invent facts not present in the transcript."
        )

        try:
            prompt = (
                f"Template:\n{template}\n\n"
                f"Transcript:\n{transcript}\n"
            )
            
            config_dict = {"system_instruction": system_instructions}
            if types:
                config_dict["thinking_config"] = types.ThinkingConfig(
                    thinking_level=self.config.thinking_level
                )

            response = self.client.models.generate_content(
                model=self._normalize_model_name(self.config.model_name),
                contents=prompt,
                config=config_dict,
            )
            text = (getattr(response, "text", "") or "").strip()
            return text

        except PermissionDenied as exc:
            raise LLMProviderAuthError(f"Gemini authentication failed: {exc}") from exc
        except DeadlineExceeded as exc:
            raise LLMTransientNetworkError(f"Gemini network/timeout error: {exc}") from exc
        except Exception as exc:
            error_msg = str(exc).lower()
            if "404" in error_msg or "model" in error_msg and "not found" in error_msg:
                raise LLMConfigError(f"Gemini model configuration failed: {exc}") from exc
            if (
                "api_key_invalid" in error_msg
                or "unauthorized" in error_msg
                or "401" in error_msg
                or "403" in error_msg
            ):
                raise LLMProviderAuthError(f"Gemini authentication failed: {exc}") from exc
            if (
                "timeout" in error_msg
                or "connection" in error_msg
                or "503" in error_msg
                or "504" in error_msg
            ):
                raise LLMTransientNetworkError(f"Gemini network error: {exc}") from exc

            raise LLMTransientNetworkError(f"Gemini LLM request failed: {exc}") from exc
