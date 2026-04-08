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
        context_topic: str | None = None, material_path: str | None = None,
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
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded  # type: ignore
            from google.genai import types  # type: ignore
        except ImportError:
            PermissionDenied = Exception  # type: ignore
            DeadlineExceeded = Exception  # type: ignore
            types = None  # type: ignore

        topic_prompt = f"The overall topic or subject is '{context_topic}'. " if context_topic else ""
        lang_prompt = f"Output your response entirely in {self.config.language}. " if self.config.language else ""
        system_instructions = (
            f"You are a helpful assistant that refines lecture transcripts. {topic_prompt}"
            "Your task is to improve the provided transcript chunk by fixing typos, spacing, punctuation, "
            "and awkward wording. You must preserve the original lecture meaning and terminology entirely. "
            f"{lang_prompt}"
            "Only output the refined text, without any conversational padding."
            "Try to preserve original source's form and it's content as best as possible."
        )

        chunk_size = self.config.resolve_chunk_size(len(raw_text))
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

                config_dict: dict = {"system_instruction": system_instructions}
                if types:
                    config_dict["thinking_config"] = types.ThinkingConfig(
                        thinking_level=self.config.thinking_level  # type: ignore
                    )

                response = self.client.models.generate_content(
                    model=self._normalize_model_name(self.config.model_name),
                    contents=prompt,
                    config=config_dict,  # type: ignore
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
        context_topic: str | None = None, material_path: str | None = None,
    ) -> str:
        """Generates lecture notes from transcript text and template in chunks."""
        if not transcript or not transcript.strip():
            return transcript

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded  # type: ignore
            from google.genai import types  # type: ignore
        except ImportError:
            PermissionDenied = Exception  # type: ignore
            DeadlineExceeded = Exception  # type: ignore
            types = None  # type: ignore

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

            contents: list = [prompt]
            uploaded_file = None

            if material_path:
                import os
                if os.path.exists(material_path):
                    uploaded_file = self.client.files.upload(file=material_path)
                    contents.append(uploaded_file)
                    system_instructions += " A lecture material PDF has been provided as context. Please actively refer to it for accurately capturing terminology and overall structure."
            
            config_dict: dict = {"system_instruction": system_instructions}
            if types:
                config_dict["thinking_config"] = types.ThinkingConfig(
                    thinking_level=self.config.thinking_level  # type: ignore
                )

            try:
                response = self.client.models.generate_content(
                    model=self._normalize_model_name(self.config.model_name),
                    contents=contents,
                    config=config_dict,  # type: ignore
                )
            finally:
                if uploaded_file and hasattr(uploaded_file, "name") and uploaded_file.name:
                    try:
                        self.client.files.delete(name=uploaded_file.name)
                    except Exception:
                        pass # Best effort cleanup

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


class OllamaLLMAdapter:
    """Implementation of Ollama API for transcript refinement using local models."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        
        # Check if ollama package is available
        try:
            import ollama
            self.ollama = ollama
        except ImportError as exc:
            raise LLMConfigError(
                "ollama package is not installed. Run: pip install ollama"
            ) from exc

    def refine_transcript(self, raw_text: str, context_topic: str | None = None) -> str:
        """Refines the transcript in chunks using the Ollama model."""
        if not raw_text or not raw_text.strip():
            return raw_text

        topic_prompt = f"The overall topic or subject is '{context_topic}'. " if context_topic else ""
        lang_prompt = f"Output your response entirely in {self.config.language}. " if self.config.language else ""
        system_instructions = (
            f"You are a helpful assistant that refines lecture transcripts. {topic_prompt}"
            "Your task is to improve the provided transcript chunk by fixing typos, spacing, punctuation, "
            "and awkward wording. You must preserve the original lecture meaning and terminology entirely. "
            f"{lang_prompt}"
            "Only output the refined text, without any conversational padding."
            "Try to preserve original source's form and it's content as best as possible."
        )

        chunk_size = self.config.resolve_chunk_size(len(raw_text))
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

                try:
                    response = self.ollama.chat(
                        model=self.config.model_name,
                        messages=[
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    text = response.get("message", {}).get("content", "").strip()
                    refined_chunks.append(text)
                except Exception as exc:
                    error_msg = str(exc).lower()
                    if "connection" in error_msg or "refused" in error_msg:
                        raise LLMTransientNetworkError(
                            f"Cannot connect to Ollama server at {self.config.ollama_base_url}. "
                            f"Make sure Ollama is running: {exc}"
                        ) from exc
                    if "not found" in error_msg or "model" in error_msg:
                        raise LLMConfigError(
                            f"Model '{self.config.model_name}' not found. "
                            f"Available models: {self._get_available_models()}"
                        ) from exc
                    raise LLMTransientNetworkError(f"Ollama request failed: {exc}") from exc
                
                start_idx = end_idx + 1 if end_idx < len(raw_text) and raw_text[end_idx] == ' ' else end_idx

            return "\n".join(refined_chunks)

        except (LLMConfigError, LLMProviderAuthError, LLMTransientNetworkError):
            raise
        except Exception as exc:
            raise LLMTransientNetworkError(f"Ollama LLM request failed: {exc}") from exc

    def generate_notes(
        self,
        transcript: str,
        template: str,
        context_topic: str | None = None, 
        material_path: str | None = None,
    ) -> str:
        """Generates lecture notes from transcript text and template."""
        if not transcript or not transcript.strip():
            return transcript

        topic_prompt = f"The lecture topic is '{context_topic}'. " if context_topic else ""
        lang_prompt = f"Output your response entirely in {self.config.language}. " if self.config.language else ""
        material_note = " (Note: PDF material attachment is not supported for Ollama.)" if material_path else ""
        
        system_instructions = (
            f"You are a helpful assistant that generates lecture notes. {topic_prompt}"
            "Use the provided markdown template exactly as the output structure. "
            "Fill each section with concise, accurate lecture notes from the transcript. "
            f"{lang_prompt}"
            f"Do not invent facts not present in the transcript.{material_note}"
        )

        try:
            prompt = (
                f"Template:\n{template}\n\n"
                f"Transcript:\n{transcript}\n"
            )

            response = self.ollama.chat(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": prompt}
                ]
            )
            
            text = response.get("message", {}).get("content", "").strip()
            return text

        except Exception as exc:
            error_msg = str(exc).lower()
            if "connection" in error_msg or "refused" in error_msg:
                raise LLMTransientNetworkError(
                    f"Cannot connect to Ollama server at {self.config.ollama_base_url}. "
                    f"Make sure Ollama is running: {exc}"
                ) from exc
            if "not found" in error_msg or "model" in error_msg:
                raise LLMConfigError(
                    f"Model '{self.config.model_name}' not found. "
                    f"Available models: {self._get_available_models()}"
                ) from exc
            raise LLMTransientNetworkError(f"Ollama LLM request failed: {exc}") from exc

    def _get_available_models(self) -> str:
        """Helper to list available Ollama models for error messages."""
        try:
            models_list = self.ollama.list()
            model_names = [m.get("name", "") for m in models_list.get("models", [])]
            return ", ".join(model_names) if model_names else "none"
        except Exception:
            return "unknown"

