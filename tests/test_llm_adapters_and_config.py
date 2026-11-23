"""Focused tests for LLMConfig and GeminiLLMAdapter config-layer changes (Task Group 1)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest
from unittest.mock import MagicMock, patch

from lecture_auto.llm_config import LLMConfig

from lecture_auto.llm_adapter import (
    GeminiLLMAdapter,
    LLMConfigError,
    LLMNoteQualityError,
    _apply_thinking_config,
    _extract_json_object,
    _normalize_structured_note_data,
    _render_structured_notes_markdown,
)

@pytest.fixture(autouse=True)
def isolate_usage_logging(monkeypatch):
    monkeypatch.setattr("lecture_auto.llm_adapter._log_llm_usage", lambda *args, **kwargs: None)


def test_llm_config_validation_fails_without_api_key() -> None:
    config = LLMConfig(api_key=None)
    with pytest.raises(ValueError, match="Google API key is required"):
        config.validate()


def test_llm_config_validation_passes_with_api_key() -> None:
    config = LLMConfig(api_key="gemini-key-123")
    config.validate()


def test_llm_config_defaults_to_stable_gemini_flash_lite() -> None:
    config = LLMConfig(api_key="gemini-key-123")
    assert config.model_name == "gemini-3.1-flash-lite"


def test_llm_config_validation_rejects_too_small_chunk_size() -> None:
    config = LLMConfig(api_key="gemini-key-123", chunk_size=100)
    with pytest.raises(ValueError, match="chunk_size must be at least 500"):
        config.validate()


def test_gemini_adapter_initializes_with_valid_config() -> None:
    config = LLMConfig(api_key="valid-key")
    with patch("google.genai.Client") as client_cls:
        adapter = GeminiLLMAdapter(config)

    client_cls.assert_called_once_with(
        api_key="valid-key",
        http_options={"retry_options": {"attempts": 2, "http_status_codes": [500, 502, 503, 504],
                                        "initial_delay": 1, "max_delay": 2}},
    )


def test_gemini_adapter_missing_api_key_raises_error() -> None:
    config = LLMConfig(api_key="")
    with pytest.raises(LLMConfigError, match="Google API key is required"):
        GeminiLLMAdapter(config)


def test_gemini_adapter_can_delegate_to_post_install_addon() -> None:
    class FakeRuntime:
        def run_feature(self, feature, request, **kwargs):
            assert feature == "gemini"
            assert request["action"] == "gemini_refine_transcript"
            return {"text": "add-on result"}

    adapter = GeminiLLMAdapter(
        LLMConfig(api_key="valid-key"),
        runtime_manager=FakeRuntime(),
        use_addon=True,
    )

    assert adapter.refine_transcript("raw") == "add-on result"


def test_gemini_addon_preserves_the_note_quality_error(tmp_path, monkeypatch) -> None:
    from lecture_auto.local_runtime import LocalRuntimeManager

    worker = tmp_path / "gemini_worker.py"
    worker.write_text(
        'import sys\nsys.stdin.readline()\n'
        'print(\'{"type":"error","code":"LLMNoteQualityError","message":"Missing formula inputs."}\')\n'
        'sys.exit(1)\n',
        encoding="utf-8",
    )
    runtime = LocalRuntimeManager(runtime_dir=tmp_path / "runtime", gemini_worker_script=worker)
    monkeypatch.setattr(runtime, "python_for", lambda feature: Path(sys.executable))
    adapter = GeminiLLMAdapter(LLMConfig(api_key="fake"), runtime_manager=runtime, use_addon=True)

    with pytest.raises(LLMNoteQualityError, match="Missing formula inputs"):
        adapter.generate_notes("A sample transcript.", "# Test")


def test_gemini_adapter_refine_transcript_empty_text() -> None:
    config = LLMConfig(api_key="valid-key")
    with patch("google.genai.Client"):
        adapter = GeminiLLMAdapter(config)
    result = adapter.refine_transcript("   ")
    assert result == "   "


def test_refine_transcript_uses_adaptive_chunk_size_for_large_input() -> None:
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Refined"
    mock_client_instance.models.generate_content.return_value = mock_response

    config = LLMConfig(api_key="valid-key", chunk_size=4000)
    with patch("google.genai.Client", return_value=mock_client_instance):
        adapter = GeminiLLMAdapter(config)

    raw_text = "word " * 7200  # ~36k chars
    adapter.refine_transcript(raw_text)

    chunk_lengths: list[int] = []
    for call in mock_client_instance.models.generate_content.call_args_list:
        contents = call.kwargs["contents"]
        chunk_text = contents.split("\n", 1)[1] if "\n" in contents else ""
        chunk_lengths.append(len(chunk_text))

    assert mock_client_instance.models.generate_content.call_count > 1
    assert max(chunk_lengths) > 4000


def test_refine_transcript_uses_lecture_transcript_editor_prompt() -> None:
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Clean transcript."
    mock_client_instance.models.generate_content.return_value = mock_response

    config = LLMConfig(api_key="valid-key", language="Korean")
    with patch("google.genai.Client", return_value=mock_client_instance):
        adapter = GeminiLLMAdapter(config)

    adapter.refine_transcript("raw transcript", context_topic="Algorithms")

    call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs
    system_instruction = call_kwargs["config"]["system_instruction"]
    contents = call_kwargs["contents"]

    assert "precise lecture transcript editor" in system_instruction
    assert "not a summary" in system_instruction
    assert "phonetically plausible word substitutions" in system_instruction
    assert "Low ASR confidence alone" in system_instruction
    assert "Only when multiple plausible readings remain" in system_instruction
    assert "Algorithms" in system_instruction
    assert "Korean" in system_instruction
    assert "<<<\nraw transcript\n>>>" in contents


def test_gemini_notes_extract_evidence_and_repair_a_gap_from_its_original_chunk() -> None:
    mock_client_instance = MagicMock()

    payload = {
        "note_title": "Graph Traversal: BFS, DFS, and Complexity",
        "topic_overview": [
            "Long lecture introduces graph search goals.",
            "The lecture moves from traversal mechanics to complexity.",
            "The topic matters because traversal supports many algorithms.",
        ],
        "core_concepts": [
            "Breadth-first search explores vertices by distance from the source.",
            "Depth-first search follows a path before backtracking.",
            "A queue preserves BFS frontier order.",
            "A stack or recursion preserves DFS exploration state.",
            "Visited sets prevent repeated work on cycles.",
            "Time complexity depends on vertices plus edges.",
        ],
        "detailed_explanations": [
            {
                "title": "Breadth-First Search Mechanics",
                "bullets": [
                    "BFS starts from a source vertex and visits neighbors in waves.",
                    "The queue stores discovered vertices waiting for expansion.",
                    "Marking vertices as visited prevents cycles from re-entering the frontier.",
                    "BFS distance layers explain why it finds shortest unweighted paths.",
                ],
            },
            {
                "title": "Depth-First Search Mechanics",
                "bullets": [
                    "DFS explores one branch until it cannot continue.",
                    "Backtracking returns control to the most recent unfinished vertex.",
                    "Recursion or an explicit stack records the active path.",
                    "DFS structure supports topological sorting and component discovery.",
                ],
            },
        ],
        "examples_mentioned": ["Graph traversal from a source vertex."],
        "questions_to_review": [
            "How does BFS frontier order determine traversal layers?",
            "Why does DFS need backtracking to complete graph exploration?",
            "How do visited sets change behavior on cyclic graphs?",
            "Why is graph traversal complexity expressed using vertices plus edges?",
        ],
        "exam_related_mentions": ["Not mentioned."],
    }

    audit_count = 0

    def generate_content(**kwargs):
        nonlocal audit_count
        prompt = kwargs["contents"][0]
        if prompt.startswith("Chunk: "):
            assert "note_title" not in kwargs["config"]["system_instruction"]
            data = {"evidence": [{
                "topic": "BFS",
                "detail": "The queue visits B and C before the next layer, including D.",
            }]}
        elif prompt.startswith("Build the final study note"):
            assert "visits B and C before the next layer" in prompt
            assert "UNRELATED ORIGINAL" not in prompt
            data = payload
        elif prompt.startswith("Repair this JSON"):
            assert "ORIGINAL EXAMPLE" in prompt
            assert "UNRELATED ORIGINAL" not in prompt
            data = {"detailed_explanations": [{
                "title": "Breadth-First Search Mechanics",
                "bullets": ["Starting at A, enqueue B and C. Pop B and enqueue D behind C, so C is expanded before D."],
            }, payload["detailed_explanations"][1]]}
        else:
            assert "Study note:" in prompt
            audit_count += 1
            data = {"issues": []}
            if audit_count == 1:
                data["issues"].append({
                    "section": "detailed_explanations",
                    "message": "Walk through the queue in the BFS example.",
                    "chunk_ids": [1, 999],
                })
            else:
                assert "ORIGINAL EXAMPLE" in prompt
                assert "D behind C" in prompt
        return MagicMock(text=json.dumps(data))

    mock_client_instance.models.generate_content.side_effect = generate_content

    config = LLMConfig(api_key="valid-key", chunk_size=500)
    with patch("google.genai.Client", return_value=mock_client_instance):
        adapter = GeminiLLMAdapter(config)

    transcript = "ORIGINAL EXAMPLE: A enqueues B and C. " + "BFS uses a queue. " * 40
    transcript += "UNRELATED ORIGINAL: " + "DFS uses a stack. " * 80
    notes = adapter.generate_notes(
        transcript,
        "# Structured Lecture Notes\n\n## Topic Overview",
    )

    contents = [
        call.kwargs["contents"][0]
        for call in mock_client_instance.models.generate_content.call_args_list
    ]

    assert audit_count == 2
    assert any("Chunk: 1 of" in content for content in contents)
    assert "Following context:" in contents[0]
    assert notes.startswith("# Graph Traversal: BFS, DFS, and Complexity")
    assert "### Breadth-First Search Mechanics" in notes
    assert "C is expanded before D" in notes
    assert "### Depth-First Search Mechanics" in notes


def test_extract_json_object_preserves_latex_commands_that_look_like_json_escapes() -> None:
    parsed = _extract_json_object(
        r'{"items":["$t \rightarrow \theta \beta \frac{1}{2} \nabla$"]}'
    )

    assert parsed["items"][0] == r"$t \rightarrow \theta \beta \frac{1}{2} \nabla$"


def test_structured_note_title_falls_back_to_topic_overview() -> None:
    note_data = _normalize_structured_note_data(
        {
            "note_title": "Structured Lecture Notes",
            "topic_overview": ["니체의 계보학적 도덕 비판"],
        }
    )

    notes = _render_structured_notes_markdown(note_data)

    assert notes.startswith("# 니체의 계보학적 도덕 비판")
    assert "# Structured Lecture Notes" not in notes


def test_model_name_normalization_maps_gemini_3_0_alias() -> None:
    assert (
        GeminiLLMAdapter._normalize_model_name("gemini-3.0-flash-preview")
        == "gemini-3-flash-preview"
    )


def test_model_name_normalization_strips_models_prefix() -> None:
    assert (
        GeminiLLMAdapter._normalize_model_name("models/gemini-3-flash-preview")
        == "gemini-3-flash-preview"
    )


def test_model_name_normalization_maps_deprecated_flash_lite_preview() -> None:
    assert (
        GeminiLLMAdapter._normalize_model_name("gemini-3.1-flash-lite-preview")
        == "gemini-3.1-flash-lite"
    )


def test_gemma4_omits_non_high_thinking_config() -> None:
    class FakeTypes:
        @staticmethod
        def ThinkingConfig(thinking_level: str) -> dict:
            return {"thinking_level": thinking_level}

    config: dict = {"system_instruction": "test"}

    _apply_thinking_config(config, FakeTypes, "gemma-4-26b-a4b-it", "medium")

    assert "thinking_config" not in config


def test_gemma4_high_thinking_config_is_enabled() -> None:
    class FakeTypes:
        @staticmethod
        def ThinkingConfig(thinking_level: str) -> dict:
            return {"thinking_level": thinking_level}

    config: dict = {"system_instruction": "test"}

    _apply_thinking_config(config, FakeTypes, "gemma-4-26b-a4b-it", "high")

    assert config["thinking_config"] == {"thinking_level": "high"}


@pytest.mark.parametrize("statuses, succeeds", [([500, 200], True), ([500, 500], False), ([400], False), ([403], False), ([429], False)])
def test_gemini_retries_only_transient_server_errors_once(statuses, succeeds):
    from google import genai
    from google.genai import _api_client
    httpx = getattr(_api_client, "httpx2", None) or _api_client.httpx
    from lecture_auto.llm_adapter import LLMTransientNetworkError, LLMProviderAuthError
    real_client = genai.Client
    seen = []
    def handler(request):
        index = len(seen)
        seen.append(json.loads(request.content))
        status = statuses[index]
        if status == 200:
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "clean transcript"}]}}]})
        return httpx.Response(status, json={"error": {"code": status, "message": "An internal error occurred"}})
    def make_client(**kwargs):
        kwargs["http_options"]["client_args"] = {"transport": httpx.MockTransport(handler)}
        return real_client(**kwargs)
    with patch("google.genai.Client", side_effect=make_client):
        adapter = GeminiLLMAdapter(LLMConfig(api_key="fake-key"))
    try:
        if succeeds:
            assert adapter.refine_transcript("synthetic transcript") == "clean transcript"
        else:
            with pytest.raises((LLMTransientNetworkError, LLMProviderAuthError)):
                adapter.refine_transcript("synthetic transcript")
        assert len(seen) == len(statuses)
        if len(seen) == 2:
            assert seen[0] == seen[1]
    finally:
        adapter.client.close()


def test_gemini_retry_does_not_restart_completed_chunks():
    from google import genai
    from google.genai import _api_client
    httpx = getattr(_api_client, "httpx2", None) or _api_client.httpx
    real_client = genai.Client
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 2:
            return httpx.Response(500, json={"error": {"code": 500, "message": "An internal error occurred"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "clean"}]}}]})
    def make_client(**kwargs):
        kwargs["http_options"]["client_args"] = {"transport": httpx.MockTransport(handler)}
        return real_client(**kwargs)
    with patch("google.genai.Client", side_effect=make_client):
        adapter = GeminiLLMAdapter(LLMConfig(api_key="fake-key", chunk_size=500))
    try:
        adapter.refine_transcript("first chunk " * 30 + "second distinct chunk " * 30)
        assert len(requests) == 4
        assert requests[0] != requests[1]
        assert requests[1] == requests[2]
    finally:
        adapter.client.close()
