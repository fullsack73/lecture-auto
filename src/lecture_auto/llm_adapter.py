from __future__ import annotations

import json
import hashlib
from dataclasses import asdict
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Protocol

from lecture_auto.llm_config import LLMConfig, normalize_gemini_model_name

logger = logging.getLogger(__name__)


def _log_llm_usage(
    provider: str, stage: str, response: Any, *, input_characters: dict[str, int] | None = None,
) -> None:
    usage = getattr(response, "usage_metadata", None) if provider == "gemini" else response
    fields = ({"input_tokens": "prompt_token_count", "output_tokens": "candidates_token_count",
               "cached_tokens": "cached_content_token_count", "thinking_tokens": "thoughts_token_count"} if provider == "gemini" else
              {"input_tokens": "prompt_eval_count", "output_tokens": "eval_count"})
    record: dict[str, Any] = {"time": datetime.now(timezone.utc).isoformat(), "provider": provider, "stage": stage, "requests": 1}
    if input_characters is not None:
        record["input_characters"] = input_characters
    for name, field in fields.items():
        value = usage.get(field) if isinstance(usage, dict) else getattr(usage, field, None)
        if type(value) is int:
            record[name] = value
    usage_logger = logging.getLogger("lecture_auto.llm_usage")
    try:
        if not usage_logger.handlers:
            directory = Path.home() / ".lecture_auto" / "logs"
            directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(directory / "llm-usage.jsonl", maxBytes=1_000_000,
                                          backupCount=2, encoding="utf-8")
            usage_logger.addHandler(handler)
            usage_logger.setLevel(logging.INFO)
            usage_logger.propagate = False
        usage_logger.info(json.dumps(record))
    except OSError:
        logger.warning("Unable to write LLM usage log.")

STRUCTURED_NOTE_SCHEMA_KEYS = (
    "topic_overview",
    "core_concepts",
    "detailed_explanations",
    "examples_mentioned",
    "questions_to_review",
    "exam_related_mentions",
)

STRUCTURED_NOTE_SCHEMA_DESCRIPTION = (
    '{"note_title":"...",'
    '"topic_overview":["..."],'
    '"core_concepts":["..."],'
    '"detailed_explanations":[{"title":"...","bullets":["..."],'
    '"blocks":[{"kind":"formula or code","text":"...","language":"..."}]}],'
    '"examples_mentioned":["..."],'
    '"questions_to_review":["..."],'
    '"exam_related_mentions":["..."]}'
)

NOTE_EVIDENCE_SCHEMA = '{"evidence":[{"topic":"...","detail":"..."}]}'
NOTE_AUDIT_SCHEMA = '{"issues":[{"section":"...","message":"...","chunk_ids":[1]}]}'
NOTE_CHUNK_CONTEXT = 240

STRUCTURED_NOTE_TITLE_INSTRUCTION = (
    "Return one concise, content-specific title that identifies this lecture's central subject. "
    "Use the requested output language, preserve essential proper nouns or technical terms, "
    "and do not use generic titles such as 'Structured Lecture Notes' or 'Lecture Notes'."
)

STRUCTURED_NOTE_SECTION_INSTRUCTIONS = {
    "topic_overview": (
        "Return 3-5 bullets capturing lecture scope, main arc, and why the lecture matters. "
        "Each bullet should be specific to this lecture, not a generic course summary."
    ),
    "core_concepts": (
        "Define the terms and relationships needed to follow the explanations. Keep this a quick reference."
    ),
    "detailed_explanations": (
        "Give each major topic enough room to explain the actual reasoning. Where supported, name the "
        "inputs or starting state, explain what changes at each step and why, state the result and when it differs. "
        "Connect causes to effects explicitly. Define symbols and give the instructor's worked examples beside "
        "the relevant explanation, preserving inputs, intermediate steps and results. "
        "Use bullets for prose and optional blocks for standalone formulas or code. "
        "A block has kind 'formula' (LaTeX without math delimiters) or 'code' (raw code without fences, "
        "with a language identifier if known). Describe code behavior in prose when no exact code is available."
    ),
    "examples_mentioned": (
        "Index the examples actually explained in the lecture. Put their reasoning in detailed_explanations. "
        "If no examples were given, return an empty array."
    ),
    "questions_to_review": (
        "Ask questions about mechanisms, conditions, or applications that can be answered from the note itself. "
        "Cover the major topics without padding."
    ),
    "exam_related_mentions": (
        "Return only explicit grading, exam, homework, assignment, or assessment cues. "
        "If none, return an empty array."
    ),
}


def _format_structured_note_section_requirements() -> str:
    return " ".join(
        f"{section_key}: {instruction}"
        for section_key, instruction in STRUCTURED_NOTE_SECTION_INSTRUCTIONS.items()
    )


def _build_transcript_refinement_system_instruction(
    *,
    context_topic: str | None,
    language: str | None,
) -> str:
    return (
        "You are a precise lecture transcript editor, not a summary writer. Preserve meaning, order, examples, terms, "
        "numbers, formulas, names, code, quotes and meaningful uncertainty/emphasis. "
        "Fix spacing, punctuation and phonetically plausible word substitutions supported by context. "
        "Remove only meaningless filler/repetition. Change names/numbers/formulas only with strong source evidence. "
        "Add no facts, headings or commentary. Materials validate spelling, not speech. "
        "Low ASR confidence alone does not make text unclear. Only when multiple plausible readings remain, "
        "use [불명확 mm:ss] with evidence time; otherwise keep original wording. Output only edited text. "
        + (f"Topic: {context_topic}. " if context_topic else "")
        + (f"Language: {language}." if language else "Preserve the source language.")
    )


def _build_transcript_refinement_prompt(
    chunk: str,
    *,
    evidence: dict[str, object] | None = None,
) -> str:
    from lecture_auto.stt_refinement import format_refinement_evidence

    return (
        "Refine this transcript chunk according to the system instructions. "
        "Return only the refined transcript chunk.\n\n"
        "Transcript chunk:\n"
        "<<<\n"
        f"{chunk}\n"
        ">>>"
        f"{format_refinement_evidence(evidence)}"
    )


def _build_structured_notes_json_system_instruction(
    *,
    context_topic: str | None,
    language: str | None,
    material_note: str = "",
    template_note: str = "",
) -> str:
    topic_prompt = f"Lecture topic: {context_topic}. " if context_topic else ""
    lang_prompt = f"Write the explanatory prose in {language}. " if language else ""
    return (
        "You extract structured lecture-note data from transcripts. "
        f"{topic_prompt}"
        f"{lang_prompt}"
        "Return valid JSON only, without an outer Markdown fence. "
        "If a string contains a literal backslash, escape it as a double backslash. "
        "Use transcript evidence only; do not invent facts. "
        "Preserve proper nouns, technical terms, equations, code, and quoted phrases from the transcript. "
        "Prefer dense study notes over broad summaries: capture definitions, mechanisms, assumptions, dependencies, "
        "formulas, code behavior, examples, caveats, contrasts, misconceptions, and instructor emphasis when present. "
        f"Schema exactly: {STRUCTURED_NOTE_SCHEMA_DESCRIPTION}. "
        f"note_title: {STRUCTURED_NOTE_TITLE_INSTRUCTION} "
        f"Section requirements: {_format_structured_note_section_requirements()} "
        "All bullet arrays must contain strings. Omit blocks or use an empty array when there is no formula or code. "
        "Detailed explanation titles must be meaningful, never placeholders like 'Sub Topic 1'. "
        "Do not copy placeholder text from templates. "
        f"{template_note}"
        f"{material_note}"
    )


def _build_template_note(template: str) -> str:
    template = (template or "").strip()
    if not template:
        return ""
    headings = [
        line.strip()
        for line in template.splitlines()
        if line.lstrip().startswith("#")
    ]
    if not headings:
        return ""
    heading_text = "; ".join(headings[:12])
    return (
        " Final Markdown template headings for organization: "
        f"{heading_text}. Use these as layout guidance only; still return the JSON schema exactly."
    )


def _build_structured_notes_json_prompt(*, transcript: str) -> str:
    return (
        "Generate complete structured lecture-note JSON for this transcript. "
        "Return every schema key exactly once. Return JSON only.\n\n"
        f"JSON shape: {STRUCTURED_NOTE_SCHEMA_DESCRIPTION}\n\n"
        "Transcript:\n"
        "<<<\n"
        f"{transcript}\n"
        ">>>"
    )


def _build_structured_notes_chunk_prompt(
    *,
    chunks: list[str],
    index: int,
) -> str:
    previous = chunks[index - 1][-NOTE_CHUNK_CONTEXT:] if index else ""
    following = chunks[index + 1][:NOTE_CHUNK_CONTEXT] if index + 1 < len(chunks) else ""
    return (
        f"Chunk: {index + 1} of {len(chunks)}\n"
        f"Required JSON shape: {NOTE_EVIDENCE_SCHEMA}\n"
        "Previous and following context can clarify sentences. Extract details anchored in the target chunk.\n"
        f"Previous context: {previous}\n"
        f"Transcript chunk:\n<<<\n{chunks[index]}\n>>>\n"
        f"Following context: {following}"
    )


def _build_structured_notes_repair_prompt(
    *,
    sources: dict[int, str],
    previous_json: dict[str, Any],
    issues: dict[str, list[str]],
) -> str:
    return (
        "Repair this JSON using the numbered original transcript chunks. "
        "Return complete replacement values only for the section keys listed under Issues. "
        "Inside each replacement, preserve correct explanations and examples and fix the specific gaps.\n\n"
        f"Issues:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
        f"Previous JSON:\n{json.dumps(previous_json, ensure_ascii=False)}\n\n"
        f"Original transcript chunks:\n{json.dumps(sources, ensure_ascii=False)}"
    )


def _build_json_syntax_repair_prompt(
    *,
    invalid_json: str,
    expected_schema: str,
    parser_error: str,
) -> str:
    return (
        "The previous response was intended to be JSON but is syntactically invalid. "
        "Repair JSON syntax only, preserve all original content, and return valid JSON only. "
        "Do not add markdown, code fences, or explanations.\n\n"
        f"Required JSON shape: {expected_schema}\n"
        f"Parser error: {parser_error}\n\n"
        f"Invalid response as a JSON string:\n{json.dumps(invalid_json, ensure_ascii=False)}"
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
    latex_safe_candidate = _escape_latex_json_backslashes(candidate)
    for source in (
        latex_safe_candidate,
        candidate,
        _escape_invalid_json_backslashes(latex_safe_candidate),
        _escape_invalid_json_backslashes(candidate),
    ):
        try:
            return json.loads(source)
        except json.JSONDecodeError:
            continue
    return None


_LATEX_JSON_COMMAND_PREFIXES = (
    "rightarrow",
    "leftarrow",
    "leftrightarrow",
    "epsilon",
    "partial",
    "approx",
    "forall",
    "exists",
    "lambda",
    "nabla",
    "theta",
    "alpha",
    "gamma",
    "delta",
    "omega",
    "sigma",
    "times",
    "sqrt",
    "frac",
    "beta",
    "cdot",
    "leq",
    "geq",
    "neq",
    "phi",
    "sum",
    "int",
    "log",
    "sin",
    "cos",
    "tan",
    "exp",
    "min",
    "max",
    "argmin",
    "argmax",
    "mathbb",
    "mathcal",
    "text",
    "vec",
    "hat",
    "bar",
    "tilde",
    "dot",
    "infty",
    "subset",
    "supset",
    "cup",
    "cap",
    "emptyset",
    "land",
    "lor",
    "neg",
    "pm",
    "mp",
    "div",
    "to",
    "in",
)
_LATEX_JSON_COMMAND = re.compile(
    r"(?:" + "|".join(_LATEX_JSON_COMMAND_PREFIXES) + r")(?![A-Za-z])"
)


def _escape_latex_json_backslashes(candidate: str) -> str:
    """Protect common LaTeX commands before JSON parsing consumes them as escapes."""
    result: list[str] = []
    in_string = False
    i = 0

    while i < len(candidate):
        char = candidate[i]
        if not in_string:
            result.append(char)
            if char == '"':
                in_string = True
            i += 1
            continue

        if char == '"':
            result.append(char)
            in_string = False
            i += 1
            continue

        if char == "\\":
            if _LATEX_JSON_COMMAND.match(candidate, i + 1):
                result.append("\\\\")
                i += 1
                continue

            result.append(char)
            if i + 1 < len(candidate):
                result.append(candidate[i + 1])
                i += 2
            else:
                i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def _escape_invalid_json_backslashes(candidate: str) -> str:
    return re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", candidate)


def _clean_note_item(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"^(?:[-*]\s+|•\s*)+", "", value.strip())
    return text or None


def _normalize_note_list(value: Any) -> list[str]:
    if isinstance(value, str):
        item = _clean_note_item(value)
        return [item] if item else []
    if isinstance(value, list):
        items = [_clean_note_item(item) for item in value]
        return [item for item in items if item]
    return []


def _normalize_note_blocks(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    blocks = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind, content = item.get("kind"), item.get("text")
        if kind not in ("formula", "code") or not isinstance(content, str) or not content.strip():
            continue
        block = {"kind": kind, "text": content.strip("\r\n")}
        language = item.get("language")
        if kind == "code" and isinstance(language, str) and re.fullmatch(r"[\w+#.-]+", language):
            block["language"] = language
        blocks.append(block)
    return blocks


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

        blocks = _normalize_note_blocks(item.get("blocks")) if isinstance(item, dict) else []
        if bullets or blocks:
            normalized.append({"title": title, "bullets": bullets, "blocks": blocks})

    return normalized


def _normalize_note_title(value: Any, topic_overview: list[str]) -> str:
    if isinstance(value, list):
        value = value[0] if value else None

    title = _clean_note_item(value)
    if title:
        title = re.sub(r"\s+", " ", title).lstrip("#").strip()

    generic_titles = {
        "structured lecture notes",
        "structured notes",
        "lecture notes",
        "강의 노트",
        "구조화 강의 노트",
    }
    if not title or title.casefold() in generic_titles:
        title = topic_overview[0] if topic_overview else "Lecture Notes"

    if len(title) > 100:
        shortened = title[:97].rsplit(" ", 1)[0].rstrip(".,;:")
        title = f"{shortened or title[:97]}..."
    return title


def _normalize_structured_note_data(raw_data: dict[str, Any]) -> dict[str, Any]:
    topic_overview = _normalize_note_list(raw_data.get("topic_overview"))
    return {
        "note_title": _normalize_note_title(
            raw_data.get("note_title"),
            topic_overview,
        ),
        "topic_overview": topic_overview,
        "core_concepts": _normalize_note_list(raw_data.get("core_concepts")),
        "detailed_explanations": _normalize_detailed_explanations(
            raw_data.get("detailed_explanations")
        ),
        "examples_mentioned": _normalize_note_list(raw_data.get("examples_mentioned")),
        "questions_to_review": _normalize_note_list(raw_data.get("questions_to_review")),
        "exam_related_mentions": _normalize_note_list(raw_data.get("exam_related_mentions")),
    }


def _validate_structured_note_data(note_data: dict[str, Any]) -> dict[str, list[str]]:
    issues = {}
    for key in ("topic_overview", "core_concepts", "questions_to_review"):
        if not any(item.casefold().rstrip(".") != "not mentioned" for item in note_data[key]):
            issues[key] = ["Provide at least one substantive entry grounded in the lecture."]

    detailed = note_data["detailed_explanations"]
    if not detailed:
        issues["detailed_explanations"] = ["Explain at least one substantive lecture topic."]
    for item in detailed:
        title = item["title"].casefold()
        if title.startswith(("sub topic", "subtopic", "detailed topic")) or title in {
            "detailed explanation", "topic", "main topic",
        }:
            issues.setdefault("detailed_explanations", []).append(
                f"Replace the placeholder title {item['title']!r} with the actual topic."
            )
    return issues


def _ensure_note_items(items: list[str], fallback: str = "Not mentioned.") -> list[str]:
    return items if items else [fallback]


def _render_bullets(items: list[str]) -> str:
    return "\n".join("- " + item.replace("\n", "\n  ") for item in _ensure_note_items(items))


def _render_note_block(block: dict[str, str]) -> str:
    content = block["text"]
    if block["kind"] == "formula":
        formula = content.strip()
        for start, end in (("$$", "$$"), (r"\[", r"\]"), ("$", "$")):
            if formula.startswith(start) and formula.endswith(end):
                formula = formula[len(start):-len(end)].strip()
                break
        return f"$$\n{formula}\n$$"

    longest_run = max((len(run) for run in re.findall(r"`+", content)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}{block.get('language', '')}\n{content}\n{fence}"


def _render_structured_notes_markdown(note_data: dict[str, Any]) -> str:
    note_title = _normalize_note_title(
        note_data.get("note_title"),
        _normalize_note_list(note_data.get("topic_overview")),
    )
    detailed = note_data.get("detailed_explanations") or []
    if not detailed:
        detailed = [{"title": "Detailed Explanation", "bullets": ["Not mentioned."]}]

    detailed_lines = ["## Detailed Explanations"]
    for item in detailed:
        detail_title = _clean_note_item(item.get("title")) or "Detailed Explanation"
        bullets = _normalize_note_list(item.get("bullets"))
        detailed_lines.extend(["", f"### {detail_title}"])
        if bullets:
            detailed_lines.append(_render_bullets(bullets))
        for block in item.get("blocks", []):
            detailed_lines.extend(["", _render_note_block(block)])

    return "\n\n".join(
        [
            f"# {note_title}",
            "## Topic Overview\n" + _render_bullets(note_data.get("topic_overview") or []),
            "## Core Concepts\n" + _render_bullets(note_data.get("core_concepts") or []),
            "\n".join(detailed_lines),
            "## Examples Mentioned\n" + _render_bullets(note_data.get("examples_mentioned") or []),
            "## Questions to Review\n" + _render_bullets(note_data.get("questions_to_review") or []),
            "## Exam related mentions\n" + _render_bullets(note_data.get("exam_related_mentions") or []),
        ]
    )


class _NoteJSONRequest(Protocol):
    def __call__(
        self, *, system_instructions: str, prompt: str, expected_schema: str, stage: str,
    ) -> dict[str, Any]: ...


def _audit_note_content(
    request: _NoteJSONRequest,
    note_data: dict[str, Any],
    evidence: dict[int, str | list[dict[str, str]]],
) -> tuple[dict[str, list[str]], set[int]]:
    response = request(
        stage="note_audit",
        system_instructions=(
            "Review the study note against the numbered lecture evidence. "
            "Report material gaps only: missing cause-and-effect links, prerequisites, steps or results "
            "that the source supports, worked examples reduced to titles, unsupported claims, "
            "and review questions the note cannot answer. "
            "For a question whose answer is supported by the source, flag the missing explanation first. "
            "If the lecture evidence cannot answer it, flag the question instead. "
            "Name what to fix, select the affected section key and list the supporting chunk IDs. "
            "Use an empty chunk_ids array when the issue has no specific source. "
            "Return an empty issues array for a study note with no material gaps. Return only JSON."
        ),
        prompt=(
            f"Required JSON shape: {NOTE_AUDIT_SCHEMA}\n"
            f"Study note:\n{json.dumps(note_data, ensure_ascii=False)}\n"
            f"Numbered lecture evidence:\n{json.dumps(evidence, ensure_ascii=False)}"
        ),
        expected_schema=NOTE_AUDIT_SCHEMA,
    )
    findings = response.get("issues")
    if not isinstance(findings, list):
        raise LLMNoteQualityError("Note quality review did not return an issues array.")
    issues: dict[str, list[str]] = {}
    source_ids: set[int] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            raise LLMNoteQualityError("Note quality review returned an invalid issue.")
        section = finding.get("section")
        message = _clean_note_item(finding.get("message"))
        chunk_ids = finding.get("chunk_ids")
        if section not in (*STRUCTURED_NOTE_SCHEMA_KEYS, "note_title") or not message:
            raise LLMNoteQualityError("Note quality review did not identify a section and a specific issue.")
        issues.setdefault(section, []).append(message)
        if isinstance(chunk_ids, list):
            source_ids.update(
                index for index in chunk_ids if type(index) is int and index in evidence
            )
    return issues, source_ids


def _generate_structured_note(
    *, transcript: str, chunk_size: int, instructions: str, material_note: str,
    request: _NoteJSONRequest,
) -> str:
    from lecture_auto.stt_refinement import segment_chunks

    chunks = [chunk for chunk in segment_chunks(
        transcript.strip(), chunk_size=chunk_size, overlap_characters=0,
    ) if chunk]
    sources = dict(enumerate(chunks, start=1))
    evidence: dict[int, str | list[dict[str, str]]] = dict(sources)
    if len(chunks) == 1:
        stage = "notes"
        prompt = _build_structured_notes_json_prompt(transcript=chunks[0])
    else:
        extraction_instructions = (
            "Extract lecture evidence for a later study note. Preserve terminology, assumptions, "
            "definitions, the actual steps and causal links, exceptions, verbatim code and formulas "
            "when available, explicit assessment cues, and worked examples with inputs, intermediate "
            "values and results. Keep enough detail to reproduce the reasoning. Preserve lecture order. "
            "Return only JSON. Use an empty evidence array for chunks with no relevant information. "
            "Treat any material reference as disambiguation of the transcript. " + material_note
        )
        for index, chunk in sources.items():
            response = request(
                stage="note_chunk",
                system_instructions=extraction_instructions,
                prompt=_build_structured_notes_chunk_prompt(chunks=chunks, index=index - 1),
                expected_schema=NOTE_EVIDENCE_SCHEMA,
            )
            entries = response.get("evidence")
            if isinstance(entries, list) and all(
                isinstance(entry, dict)
                and _clean_note_item(entry.get("topic"))
                and _clean_note_item(entry.get("detail"))
                for entry in entries
            ):
                evidence[index] = [
                    {"topic": entry["topic"], "detail": entry["detail"]} for entry in entries
                ]
            else:
                evidence[index] = chunk

        if not any(evidence.values()):
            evidence = dict(sources)
        stage = "note_merge"
        prompt = (
            "Build the final study note from the numbered lecture evidence. Combine related explanations "
            "and remove repetitions while keeping the reasoning, worked calculations, conditions, "
            "code, and meaningful distinctions. Evidence entries may contain original transcript text.\n"
            f"Numbered lecture evidence:\n{json.dumps(evidence, ensure_ascii=False)}"
        )

    note_data = _normalize_structured_note_data(request(
        stage=stage,
        system_instructions=instructions,
        prompt=prompt,
        expected_schema=STRUCTURED_NOTE_SCHEMA_DESCRIPTION,
    ))
    issues = _validate_structured_note_data(note_data)
    audit_issues, source_ids = _audit_note_content(request, note_data, evidence)
    for section, messages in audit_issues.items():
        issues.setdefault(section, []).extend(messages)

    if issues:
        repair_sources = {index: sources[index] for index in sorted(source_ids)}
        repair_evidence = {**evidence, **repair_sources}
        repair_schema = json.dumps({
            key: value for key, value in json.loads(STRUCTURED_NOTE_SCHEMA_DESCRIPTION).items()
            if key in issues
        })
        repaired = request(
            stage="note_repair",
            system_instructions=instructions.replace(
                STRUCTURED_NOTE_SCHEMA_DESCRIPTION, repair_schema,
            ),
            prompt=_build_structured_notes_repair_prompt(
                sources=repair_sources, previous_json=note_data, issues=issues,
            ) + (
                f"\nNumbered lecture evidence:\n{json.dumps(evidence, ensure_ascii=False)}"
                if not repair_sources or set(issues) - set(audit_issues) else ""
            ),
            expected_schema=repair_schema,
        )
        if not issues.keys() <= repaired.keys():
            raise LLMNoteQualityError("Note quality repair omitted a requested section.")
        note_data = _normalize_structured_note_data(
            {**note_data, **{key: repaired[key] for key in issues}}
        )
        remaining = _validate_structured_note_data(note_data)
        if not remaining:
            remaining, _ = _audit_note_content(request, note_data, repair_evidence)
        if remaining:
            raise LLMNoteQualityError(f"Note quality issues remain after repair: {', '.join(remaining)}.")

    return _render_structured_notes_markdown(note_data)


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


class LLMNoteQualityError(Exception):
    """Note review or repair could not produce an acceptable note."""


class LLMProviderAdapter(Protocol):
    """Interface for LLM-based transcript refinement."""

    def refine_transcript(
        self,
        raw_text: str,
        context_topic: str | None = None,
        evidence: dict[str, object] | None = None,
        checkpoint_path: str | None = None,
    ) -> str:
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

    def __init__(
        self,
        config: LLMConfig,
        *,
        runtime_manager: Any | None = None,
        use_addon: bool | None = None,
    ) -> None:
        if not config.api_key or not config.api_key.strip():
            raise LLMConfigError("Google API key is required.")
        self.config = config
        self._addon = None

        if use_addon is None:
            use_addon = "__compiled__" in globals()
        if use_addon:
            from lecture_auto.gemini_addon import GeminiAddonAdapter
            from lecture_auto.local_runtime import LocalRuntimeManager

            self._addon = GeminiAddonAdapter(
                config,
                runtime_manager or LocalRuntimeManager(),
            )
            self.client = None
            return

        try:
            from google import genai
        except ImportError as exc:
            raise LLMConfigError(
                "google-genai is not installed. Run: pip install google-genai"
            ) from exc

        self.client = genai.Client(
            api_key=self.config.api_key,
            http_options={"retry_options": {
                "attempts": 2,
                "http_status_codes": [500, 502, 503, 504],
                "initial_delay": 1,
                "max_delay": 2,
            }},
        )

    def _call_addon(self, method: str, *args: Any, **kwargs: Any) -> str:
        if self._addon is None:
            raise RuntimeError("Gemini add-on adapter is not active.")
        try:
            return str(getattr(self._addon, method)(*args, **kwargs))
        except Exception as exc:
            from lecture_auto.local_runtime import LocalRuntimeError, LocalRuntimeMissingError

            if isinstance(exc, LocalRuntimeMissingError):
                raise LLMConfigError(
                    "Gemini add-on is not installed. Open Settings > Add-ons and install Gemini."
                ) from exc
            if isinstance(exc, LocalRuntimeError):
                if exc.code == LLMNoteQualityError.__name__:
                    raise LLMNoteQualityError(str(exc)) from exc
                raise LLMTransientNetworkError(f"Gemini add-on failed: {exc}") from exc
            raise

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """Normalizes common Gemini model aliases to API-accepted IDs."""
        return normalize_gemini_model_name(model_name)

    def refine_transcript(
        self,
        raw_text: str,
        context_topic: str | None = None,
        evidence: dict[str, object] | None = None,
        checkpoint_path: str | None = None,
    ) -> str:
        """Refines the transcript in chunks using the Gemini model."""
        if not raw_text or not raw_text.strip():
            return raw_text
        if self._addon is not None:
            return self._call_addon(
                "refine_transcript",
                raw_text,
                context_topic=context_topic,
                evidence=evidence,
                checkpoint_path=checkpoint_path,
            )

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded  # type: ignore
        except ImportError:
            class PermissionDenied(Exception):  # type: ignore[no-redef]
                pass

            class DeadlineExceeded(Exception):  # type: ignore[no-redef]
                pass

        try:
            from google.genai import types  # type: ignore
        except ImportError:
            types = None  # type: ignore

        system_instructions = _build_transcript_refinement_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
        )

        chunk_size = self.config.resolve_chunk_size(len(raw_text))
        from lecture_auto.stt_refinement import segment_chunks, chunk_refinement_evidence

        chunks = segment_chunks(
            raw_text,
            chunk_size=chunk_size,
            overlap_characters=0,
        )
        from lecture_auto.stt_refinement import RefinementCheckpoint

        fingerprint = hashlib.sha256(json.dumps(
            [raw_text, chunks, evidence, system_instructions, asdict(self.config)],
            ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()
        checkpoint = RefinementCheckpoint(checkpoint_path, fingerprint, len(chunks))
        scoped = chunk_refinement_evidence(raw_text, chunks, evidence)

        try:
            for index in range(len(checkpoint.completed), len(chunks)):
                chunk, chunk_evidence = chunks[index], scoped[index]
                prompt = _build_transcript_refinement_prompt(
                    chunk,
                    evidence=chunk_evidence,
                )

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
                _log_llm_usage("gemini", "refine", response, input_characters={
                        "transcript": len(chunk), "context": len(prompt) - len(chunk),
                        "system": len(system_instructions),
                    })
                text = (getattr(response, "text", "") or "").strip()
                checkpoint.append(text)
                
            return "\n".join(checkpoint.completed)

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
        """Generates structured notes through provider-neutral JSON data."""
        if not transcript or not transcript.strip():
            return transcript
        if self._addon is not None:
            return self._call_addon(
                "generate_notes",
                transcript,
                template,
                context_topic=context_topic,
                material_path=material_path,
            )

        try:
            from google.api_core.exceptions import PermissionDenied, DeadlineExceeded  # type: ignore
        except ImportError:
            class PermissionDenied(Exception):  # type: ignore[no-redef]
                pass

            class DeadlineExceeded(Exception):  # type: ignore[no-redef]
                pass

        try:
            from google.genai import types  # type: ignore
        except ImportError:
            types = None  # type: ignore

        try:
            template_note = _build_template_note(template)
            uploaded_file = None
            material_note = ""

            if material_path:
                import os
                if os.path.exists(material_path):
                    upload_kwargs: dict = {"file": material_path}
                    if types:
                        upload_kwargs["config"] = types.UploadFileConfig(
                            mime_type="application/pdf"
                        )
                    uploaded_file = self.client.files.upload(**upload_kwargs)
                    material_note = (
                        " A lecture material reference has been provided as supporting context. "
                        "Use it to verify terminology, structure, formulas, and examples, while prioritizing the transcript."
                    )

            config_dict: dict = {"response_mime_type": "application/json"}
            _apply_thinking_config(
                config_dict,
                types,
                self.config.model_name,
                self.config.thinking_level,
            )

            def request_json(
                *, system_instructions: str, prompt: str, expected_schema: str, stage: str,
            ) -> dict[str, Any]:
                response = self.client.models.generate_content(
                    model=self._normalize_model_name(self.config.model_name),
                    contents=[prompt],
                    config={**config_dict, "system_instruction": system_instructions},
                )
                _log_llm_usage("gemini", stage, response)
                return _extract_json_object((getattr(response, "text", "") or "").strip())

            try:
                if uploaded_file:
                    reference_response = self.client.models.generate_content(
                        model=self._normalize_model_name(self.config.model_name),
                        contents=[
                            "Extract a compact lecture-material reference in at most 8000 characters. "
                            "Preserve technical terms, exact formulas, structure and named examples. "
                            "Do not invent facts. Return plain text only.",
                            uploaded_file,
                        ],
                        config={"max_output_tokens": 4096},
                    )
                    _log_llm_usage("gemini", "material_reference", reference_response)
                    reference = (getattr(reference_response, "text", "") or "").strip()
                    if not reference:
                        raise ValueError("Lecture material reference extraction returned empty text.")
                    material_note += (
                        "\nMaterial reference (spelling/context only; not proof of spoken facts):\n"
                        + reference[:8000]
                    )
                return _generate_structured_note(
                    transcript=transcript,
                    chunk_size=self.config.resolve_chunk_size(len(transcript)),
                    instructions=_build_structured_notes_json_system_instruction(
                        context_topic=context_topic,
                        language=self.config.language,
                        material_note=material_note,
                        template_note=template_note,
                    ),
                    material_note=material_note,
                    request=request_json,
                )
            finally:
                if uploaded_file and hasattr(uploaded_file, "name") and uploaded_file.name:
                    try:
                        self.client.files.delete(name=uploaded_file.name)
                    except Exception:
                        pass  # Best effort cleanup

        except LLMNoteQualityError:
            raise
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
            client_type = getattr(ollama, "Client", None)
            self.ollama = client_type(host=config.ollama_base_url) if client_type else ollama
        except ImportError as exc:
            raise LLMConfigError(
                "ollama package is not installed. Run: pip install ollama"
            ) from exc

    def refine_transcript(
        self,
        raw_text: str,
        context_topic: str | None = None,
        evidence: dict[str, object] | None = None,
        checkpoint_path: str | None = None,
    ) -> str:
        """Refines the transcript in chunks using the Ollama model."""
        if not raw_text or not raw_text.strip():
            return raw_text

        system_instructions = _build_transcript_refinement_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
        )

        chunk_size = self.config.resolve_chunk_size(len(raw_text))
        from lecture_auto.stt_refinement import segment_chunks, chunk_refinement_evidence

        chunks = segment_chunks(
            raw_text,
            chunk_size=chunk_size,
            overlap_characters=0,
        )
        from lecture_auto.stt_refinement import RefinementCheckpoint

        fingerprint = hashlib.sha256(json.dumps(
            [raw_text, chunks, evidence, system_instructions, asdict(self.config)],
            ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()
        checkpoint = RefinementCheckpoint(checkpoint_path, fingerprint, len(chunks))
        scoped = chunk_refinement_evidence(raw_text, chunks, evidence)

        try:
            for index in range(len(checkpoint.completed), len(chunks)):
                chunk, chunk_evidence = chunks[index], scoped[index]
                prompt = _build_transcript_refinement_prompt(
                    chunk,
                    evidence=chunk_evidence,
                )

                try:
                    response = self.ollama.chat(
                        model=self.config.model_name,
                        messages=[
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    _log_llm_usage("ollama", "refine", response, input_characters={
                        "transcript": len(chunk), "context": len(prompt) - len(chunk),
                        "system": len(system_instructions),
                    })
                    text = response.get("message", {}).get("content", "").strip()
                    checkpoint.append(text)
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
                
            return "\n".join(checkpoint.completed)

        except (LLMConfigError, LLMProviderAuthError, LLMTransientNetworkError):
            raise
        except Exception as exc:
            raise LLMTransientNetworkError(f"Ollama LLM request failed: {exc}") from exc

    def _chat_for_structured_json(
        self,
        *,
        system_instructions: str,
        prompt: str,
        expected_schema: str,
        stage: str = "notes",
    ) -> dict[str, Any]:
        response = self.ollama.chat(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": prompt},
            ],
            format="json",
        )
        _log_llm_usage("ollama", stage, response)
        raw_text = response.get("message", {}).get("content", "").strip()

        try:
            return _extract_json_object(raw_text)
        except (TypeError, ValueError) as parse_error:
            repair_response = self.ollama.chat(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {
                        "role": "user",
                        "content": _build_json_syntax_repair_prompt(
                            invalid_json=raw_text,
                            expected_schema=expected_schema,
                            parser_error=str(parse_error),
                        ),
                    },
                ],
                format="json",
            )
            _log_llm_usage("ollama", "syntax_repair", repair_response)
            repaired_text = (
                repair_response.get("message", {}).get("content", "").strip()
            )
            try:
                return _extract_json_object(repaired_text)
            except (TypeError, ValueError) as repair_error:
                raise ValueError(
                    "Ollama returned invalid JSON after one syntax repair attempt: "
                    f"{repair_error}"
                ) from repair_error

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
        template_note = _build_template_note(template)

        system_instructions = _build_structured_notes_json_system_instruction(
            context_topic=context_topic,
            language=self.config.language,
            material_note=material_note,
            template_note=template_note,
        )

        try:
            return _generate_structured_note(
                transcript=transcript,
                chunk_size=self.config.resolve_chunk_size(len(transcript)),
                instructions=system_instructions,
                material_note=material_note,
                request=self._chat_for_structured_json,
            )

        except LLMNoteQualityError:
            raise
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
