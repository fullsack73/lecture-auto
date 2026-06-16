from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from lecture_auto.llm_config import LLMConfig, normalize_gemini_model_name

logger = logging.getLogger(__name__)

STRUCTURED_NOTE_SCHEMA_KEYS = (
    "topic_overview",
    "core_concepts",
    "detailed_explanations",
    "examples_mentioned",
    "questions_to_review",
    "exam_related_mentions",
)

OLLAMA_NOTE_SECTION_INSTRUCTIONS = {
    "topic_overview": (
        "Return 3-5 bullets capturing lecture scope, main arc, and why the lecture matters."
    ),
    "core_concepts": (
        "Return bullets defining key terms, concepts, and relationships needed to understand the lecture."
    ),
    "detailed_explanations": (
        "Return 2-6 subtopics. Each subtopic needs a meaningful title and bullets covering reasoning, "
        "mechanisms, steps, formulas, tradeoffs, caveats, and important distinctions."
    ),
    "examples_mentioned": (
        "Return only examples explicitly mentioned in the transcript. If none, return ['Not mentioned.']."
    ),
    "questions_to_review": (
        "Return 4-8 core questions. If a student answers and explores these questions well, "
        "they should be able to reconstruct the lecture's main content, logic, and implications. "
        "Cover central concepts, causal relationships, mechanisms, assumptions, examples, contrasts, "
        "and why ideas matter. Avoid trivia, narrow recall, and generic questions."
    ),
    "exam_related_mentions": (
        "Return only explicit grading, exam, homework, assignment, or assessment cues. "
        "If none, return ['Not mentioned.']."
    ),
}


def _build_transcript_refinement_system_instruction(
    *,
    context_topic: str | None,
    language: str | None,
) -> str:
    topic_prompt = f"The lecture topic or subject is '{context_topic}'. " if context_topic else ""
    lang_prompt = (
        f"Write the refined transcript in {language}, while preserving proper nouns, "
        "technical terms, equations, code, and quoted phrases as spoken. "
        if language
        else ""
    )
    return (
        f"You are a precise lecture transcript editor. {topic_prompt}"
        "Convert the raw ASR transcript into a clean, readable transcript, not a summary. "
        "Preserve the speaker's meaning, order of ideas, examples, terminology, numbers, formulas, and named entities. "
        "Fix obvious transcription mistakes, spacing, punctuation, capitalization, sentence boundaries, and paragraph breaks. "
        "Remove meaningless filler, duplicated starts, and accidental repetitions only when they do not change the lecture content. "
        "Keep uncertainty, emphasis, questions, and instructor cues when they affect meaning. "
        "Do not add new facts, explanations, headings, bullets, timestamps, speaker labels, or commentary. "
        "If wording is ambiguous, keep the closest original wording instead of guessing. "
        f"{lang_prompt}"
        "Output only the refined transcript text."
    )


def _build_transcript_refinement_prompt(chunk: str) -> str:
    return (
        "Refine this transcript chunk according to the system instructions. "
        "Return only the refined transcript chunk.\n\n"
        "Transcript chunk:\n"
        "<<<\n"
        f"{chunk}\n"
        ">>>"
    )


def _build_structured_notes_system_instruction(
    *,
    context_topic: str | None,
    language: str | None,
    material_note: str = "",
) -> str:
    topic_prompt = f"The lecture topic is '{context_topic}'. " if context_topic else ""
    lang_prompt = f"Output your response entirely in {language}. " if language else ""
    return (
        f"You are a lecture note writer. {topic_prompt}"
        "Generate study notes that strictly follow the provided Structured Lecture Notes markdown template. "
        "Output only markdown, with no preface, no code fence, and no conversational text. "
        "Keep the template's top-level headings, order, and section names unchanged. "
        "Replace placeholder subtopic headings such as 'Sub Topic 1' with meaningful lecture subtopic names; "
        "add or remove subtopic blocks only when the transcript supports it. "
        "Use bullet points under every section. If the transcript has no evidence for a section, write '- Not mentioned.' "
        "Topic Overview should capture the lecture scope in a few high-signal bullets. "
        "Core Concepts should define key terms and relationships. "
        "Detailed Explanations should contain the main reasoning, mechanisms, steps, formulas, tradeoffs, and caveats. "
        "Examples Mentioned should include only examples explicitly present in the transcript or attached material. "
        "Questions to Review should be a compact set of core study questions that, if answered and explored well, "
        "would let a student understand and reconstruct the lecture's main content, logic, and implications. "
        "Prioritize questions about central concepts, causal relationships, mechanisms, assumptions, examples, "
        "contrasts, and why each idea matters; avoid trivia, overly narrow recall, and generic questions. "
        "Exam related mentions should capture only explicit grading, test, homework, or assessment cues. "
        "Preserve important terminology, names, equations, and numbers exactly when they appear. "
        "Do not invent facts or overstate uncertain content. "
        f"{lang_prompt}"
        f"{material_note}"
    )


def _build_ollama_structured_notes_system_instruction(
    *,
    context_topic: str | None,
    language: str | None,
    material_note: str = "",
) -> str:
    topic_prompt = f"Lecture topic: {context_topic}. " if context_topic else ""
    lang_prompt = f"Write all JSON string values in {language}. " if language else ""
    return (
        "You extract structured lecture-note data from transcripts. "
        f"{topic_prompt}"
        f"{lang_prompt}"
        "Return valid JSON only. No markdown. No code fence. No explanation. "
        "If a string contains a literal backslash, escape it as a double backslash. "
        "Use transcript evidence only; do not invent facts. "
        "Schema exactly: "
        '{"topic_overview":["..."],'
        '"core_concepts":["..."],'
        '"detailed_explanations":[{"title":"...","bullets":["..."]}],'
        '"examples_mentioned":["..."],'
        '"questions_to_review":["..."],'
        '"exam_related_mentions":["..."]}. '
        "topic_overview: lecture scope and main arc. "
        "core_concepts: key terms, definitions, relationships. "
        "detailed_explanations: main mechanisms, reasoning, steps, formulas, tradeoffs, caveats. "
        "examples_mentioned: examples explicitly stated. If none, use ['Not mentioned.']. "
        "questions_to_review: 4-8 core questions that let a student reconstruct lecture content, logic, and implications if answered well. "
        "Questions must cover central concepts, causal relationships, mechanisms, assumptions, examples, contrasts, and why ideas matter. "
        "Avoid trivia, narrow recall, and generic questions. "
        "exam_related_mentions: explicit grading, test, homework, assessment cues only. If none, use ['Not mentioned.']. "
        "Every array must contain strings. Detailed explanation titles must be meaningful, never placeholders like 'Sub Topic 1'. "
        f"{material_note}"
    )


def _build_ollama_structured_note_section_prompt(*, transcript: str, section_key: str) -> str:
    if section_key == "detailed_explanations":
        schema = '{"detailed_explanations":[{"title":"...","bullets":["..."]}]}'
    else:
        schema = f'{{"{section_key}":["..."]}}'

    return (
        f"Generate only this section: {section_key}.\n"
        f"Instruction: {OLLAMA_NOTE_SECTION_INSTRUCTIONS[section_key]}\n"
        f"Return JSON exactly matching this shape: {schema}\n\n"
        "Transcript:\n"
        "<<<\n"
        f"{transcript}\n"
        ">>>"
    )


def _build_ollama_structured_notes_repair_prompt(
    *,
    transcript: str,
    previous_json: dict[str, Any],
    issues: list[str],
) -> str:
    return (
        "Repair this JSON so it satisfies the schema and fixes all issues. "
        "Return valid JSON only.\n\n"
        f"Issues:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"Previous JSON:\n{json.dumps(previous_json, ensure_ascii=False)}\n\n"
        "Transcript evidence:\n"
        "<<<\n"
        f"{transcript}\n"
        ">>>"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty model response")

    parsed = _load_json_object_candidate(stripped)
    if parsed is None:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            json.loads(stripped)
        parsed = _load_json_object_candidate(stripped[start : end + 1])
        if parsed is None:
            json.loads(stripped[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("model response JSON must be an object")
    return parsed


def _load_json_object_candidate(candidate: str) -> Any:
    for source in (candidate, _escape_invalid_json_backslashes(candidate)):
        try:
            return json.loads(source)
        except json.JSONDecodeError:
            continue
    return None


def _escape_invalid_json_backslashes(candidate: str) -> str:
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", candidate)


def _clean_note_item(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    while text.startswith(("-", "*", "•")):
        text = text[1:].strip()
    return text or None


def _normalize_note_list(value: Any) -> list[str]:
    if isinstance(value, str):
        item = _clean_note_item(value)
        return [item] if item else []
    if isinstance(value, list):
        items = [_clean_note_item(item) for item in value]
        return [item for item in items if item]
    return []


def _normalize_detailed_explanations(value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if isinstance(value, dict):
        iterable = [
            {"title": title, "bullets": bullets}
            for title, bullets in value.items()
        ]
    elif isinstance(value, list):
        iterable = value
    elif isinstance(value, str):
        iterable = [{"title": "Detailed Explanation", "bullets": [value]}]
    else:
        iterable = []

    for index, item in enumerate(iterable, start=1):
        if isinstance(item, dict):
            title = _clean_note_item(item.get("title")) or f"Detailed Topic {index}"
            bullets = _normalize_note_list(item.get("bullets"))
            if not bullets:
                bullets = _normalize_note_list(item.get("content"))
        else:
            title = f"Detailed Topic {index}"
            bullets = _normalize_note_list(item)

        if bullets:
            normalized.append({"title": title, "bullets": bullets})

    return normalized


def _normalize_structured_note_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic_overview": _normalize_note_list(raw_data.get("topic_overview")),
        "core_concepts": _normalize_note_list(raw_data.get("core_concepts")),
        "detailed_explanations": _normalize_detailed_explanations(
            raw_data.get("detailed_explanations")
        ),
        "examples_mentioned": _normalize_note_list(raw_data.get("examples_mentioned")),
        "questions_to_review": _normalize_note_list(raw_data.get("questions_to_review")),
        "exam_related_mentions": _normalize_note_list(raw_data.get("exam_related_mentions")),
    }


def _extract_section_value(parsed: dict[str, Any], section_key: str) -> Any:
    if section_key in parsed:
        return parsed[section_key]
    for fallback_key in ("items", "bullets", "questions", "subtopics", "content"):
        if fallback_key in parsed:
            return parsed[fallback_key]
    return None


def _validate_structured_note_data(note_data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key in STRUCTURED_NOTE_SCHEMA_KEYS:
        value = note_data.get(key)
        if key == "detailed_explanations":
            if not value:
                issues.append("detailed_explanations must contain at least one subtopic with bullets")
            continue
        if not value:
            issues.append(f"{key} must contain at least one bullet")

    questions = note_data.get("questions_to_review") or []
    if len([q for q in questions if q and q != "Not mentioned."]) < 4:
        issues.append("questions_to_review must contain 4-8 core reconstruction questions")

    detailed = note_data.get("detailed_explanations") or []
    for item in detailed:
        title = str(item.get("title", "")).strip().lower()
        if title.startswith("sub topic") or title.startswith("subtopic"):
            issues.append("detailed_explanations titles must be meaningful, not placeholder subtopic names")
            break
    return issues


def _ensure_note_items(items: list[str], fallback: str = "Not mentioned.") -> list[str]:
    return items if items else [fallback]


def _render_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in _ensure_note_items(items))


def _render_structured_notes_markdown(note_data: dict[str, Any]) -> str:
    detailed = note_data.get("detailed_explanations") or []
    if not detailed:
        detailed = [{"title": "Detailed Explanation", "bullets": ["Not mentioned."]}]

    detailed_lines = ["## Detailed Explanations"]
    for item in detailed:
        title = _clean_note_item(item.get("title")) or "Detailed Explanation"
        bullets = _normalize_note_list(item.get("bullets"))
        detailed_lines.extend(["", f"### {title}", _render_bullets(bullets)])

    return "\n\n".join(
        [
            "# Structured Lecture Notes",
            "## Topic Overview\n" + _render_bullets(note_data.get("topic_overview") or []),
            "## Core Concepts\n" + _render_bullets(note_data.get("core_concepts") or []),
            "\n".join(detailed_lines),
            "## Examples Mentioned\n" + _render_bullets(note_data.get("examples_mentioned") or []),
            "## Questions to Review\n" + _render_bullets(note_data.get("questions_to_review") or []),
            "## Exam related mentions\n" + _render_bullets(note_data.get("exam_related_mentions") or []),
        ]
    )


def _apply_thinking_config(
    config_dict: dict,
    types: object | None,
    model_name: str,
    thinking_level: str,
) -> None:
    if not types:
        return

    normalized_model = normalize_gemini_model_name(model_name)
    if normalized_model.startswith("gemma-4-") and thinking_level != "high":
        return

    config_dict["thinking_config"] = types.ThinkingConfig(  # type: ignore[attr-defined]
        thinking_level=thinking_level
    )


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
            raise LLMConfigError("Google API key is required.")
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
        return normalize_gemini_model_name(model_name)

    def refine_transcript(self, raw_text: str, context_topic: str | None = None) -> str:
        """Refines the transcript in chunks using the Gemini model."""
        if not raw_text or not raw_text.strip():
            return raw_text

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded  # type: ignore
        except ImportError:
            PermissionDenied = Exception  # type: ignore
            DeadlineExceeded = Exception  # type: ignore

        try:
            from google.genai import types  # type: ignore
        except ImportError:
            types = None  # type: ignore

        system_instructions = _build_transcript_refinement_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
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
                
                prompt = _build_transcript_refinement_prompt(chunk)

                config_dict: dict = {"system_instruction": system_instructions}
                _apply_thinking_config(
                    config_dict,
                    types,
                    self.config.model_name,
                    self.config.thinking_level,
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
        except ImportError:
            PermissionDenied = Exception  # type: ignore
            DeadlineExceeded = Exception  # type: ignore

        try:
            from google.genai import types  # type: ignore
        except ImportError:
            types = None  # type: ignore

        system_instructions = _build_structured_notes_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
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
                    upload_kwargs: dict = {"file": material_path}
                    if types:
                        upload_kwargs["config"] = types.UploadFileConfig(
                            mime_type="application/pdf"
                        )
                    uploaded_file = self.client.files.upload(**upload_kwargs)
                    contents.append(uploaded_file)
                    system_instructions += (
                        " A lecture material PDF has been provided as supporting context. "
                        "Use it to verify terminology, structure, formulas, and examples, while prioritizing the transcript."
                    )
            
            config_dict: dict = {"system_instruction": system_instructions}
            _apply_thinking_config(
                config_dict,
                types,
                self.config.model_name,
                self.config.thinking_level,
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

        system_instructions = _build_transcript_refinement_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
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
                
                prompt = _build_transcript_refinement_prompt(chunk)

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
        """Generates lecture notes from transcript text through a JSON harness."""
        if not transcript or not transcript.strip():
            return transcript

        material_note = " (Note: PDF material attachment is not supported for Ollama.)" if material_path else ""

        system_instructions = _build_ollama_structured_notes_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
            material_note=material_note,
        )

        try:
            _ = template
            raw_note_data: dict[str, Any] = {}
            for section_key in STRUCTURED_NOTE_SCHEMA_KEYS:
                prompt = _build_ollama_structured_note_section_prompt(
                    transcript=transcript,
                    section_key=section_key,
                )
                response = self.ollama.chat(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": prompt}
                    ],
                    format="json",
                )
                raw_text = response.get("message", {}).get("content", "").strip()
                parsed = _extract_json_object(raw_text)
                raw_note_data[section_key] = _extract_section_value(parsed, section_key)

            note_data = _normalize_structured_note_data(raw_note_data)
            issues = _validate_structured_note_data(note_data)

            if issues:
                repair_prompt = _build_ollama_structured_notes_repair_prompt(
                    transcript=transcript,
                    previous_json=note_data,
                    issues=issues,
                )
                repair_response = self.ollama.chat(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": system_instructions},
                        {"role": "user", "content": repair_prompt}
                    ],
                    format="json",
                )
                repair_text = repair_response.get("message", {}).get("content", "").strip()
                note_data = _normalize_structured_note_data(_extract_json_object(repair_text))

            return _render_structured_notes_markdown(note_data)

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
            raise LLMTransientNetworkError(f"Ollama note generation harness failed: {exc}") from exc

    def _get_available_models(self) -> str:
        """Helper to list available Ollama models for error messages."""
        try:
            models_list = self.ollama.list()
            model_names = [m.get("name", "") for m in models_list.get("models", [])]
            return ", ".join(model_names) if model_names else "none"
        except Exception:
            return "unknown"
