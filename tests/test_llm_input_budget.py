from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lecture_auto.llm_adapter import GeminiLLMAdapter, OllamaLLMAdapter, _log_llm_usage
from lecture_auto.llm_config import LLMConfig
from lecture_auto.stt_refinement import build_refinement_evidence, chunk_refinement_evidence


def test_evidence_is_scoped_after_alignment_and_includes_late_segments():
    segments = [{"text": f"segment-{i} content.", "start_time": i, "end_time": i + 1}
                for i in range(120)]
    raw = "\n".join(s["text"] for s in segments)
    evidence = build_refinement_evidence({"segments": segments, "metadata": {
        "quality": {"large_report": "x" * 50000},
        "asr_passes": {"candidate_pairs": [
            {"start_time": 0, "end_time": 1, "retry": "unrelated"},
            {"start_time": 100, "end_time": 101, "retry": "relevant"},
        ]},
    }})
    scoped = chunk_refinement_evidence(raw, [segments[0]["text"], segments[100]["text"]], evidence)
    assert len(evidence["segments"]) == 120
    assert [s["text"] for s in scoped[1]["segments"]] == [s["text"] for s in segments[99:102]]
    assert scoped[1]["asr_passes"]["candidate_pairs"][0]["retry"] == "relevant"
    assert len(scoped[1]["asr_passes"]["candidate_pairs"]) == 1
    assert "large_report" not in json.dumps(scoped)
    assert len(json.dumps(scoped)) < len(json.dumps(evidence)) / 10


def test_evidence_alignment_handles_whitespace_repetition_and_unmatched_text():
    evidence = build_refinement_evidence({"segments": [
        {"text": "same words", "start_time": 1, "end_time": 2},
        {"text": "same words", "start_time": 3, "end_time": 4},
    ]})
    raw = "same\nwords\nsame words"
    scoped = chunk_refinement_evidence(raw, ["same\nwords", "same words"], evidence)
    assert [s["start_time"] for s in scoped[1]["segments"]] == [1, 3]
    assert chunk_refinement_evidence(raw, ["not found"], evidence)[0]["segments"] == []
    assert chunk_refinement_evidence(raw, [raw], None) == [None]


@pytest.mark.parametrize("provider", ["gemini", "ollama"])
def test_adapters_do_not_send_global_quality_reports(provider):
    config = LLMConfig(provider=provider, api_key="test", chunk_size=500)
    with patch("google.genai.Client"):
        adapter = GeminiLLMAdapter(config) if provider == "gemini" else OllamaLLMAdapter(config)
    if provider == "gemini":
        adapter.client.models.generate_content.return_value = SimpleNamespace(text="clean")
        calls = adapter.client.models.generate_content
    else:
        adapter.ollama = MagicMock()
        adapter.ollama.chat.return_value = {"message": {"content": "clean"}}
        calls = adapter.ollama.chat
    adapter.refine_transcript("lecture " * 300, evidence={"quality": {"secret_report": "x" * 10000}})
    assert calls.call_count > 1
    assert all("secret_report" not in str(call.kwargs) for call in calls.call_args_list)


def test_usage_log_has_counts_and_no_response_text(tmp_path, monkeypatch):
    monkeypatch.setattr("lecture_auto.llm_adapter.Path.home", lambda: tmp_path)
    logger = logging.getLogger("lecture_auto.llm_usage")
    previous = logger.handlers[:]
    logger.handlers.clear()
    try:
        _log_llm_usage("gemini", "refine", SimpleNamespace(
            usage_metadata=SimpleNamespace(prompt_token_count=123, candidates_token_count=45,
                                           cached_content_token_count=10), text="private transcript"))
        _log_llm_usage("ollama", "notes", {"prompt_eval_count": 77, "eval_count": 22,
                                          "message": {"content": "private notes"}})
        _log_llm_usage("gemini", "notes", SimpleNamespace(text="private"))
        content = (tmp_path / ".lecture_auto/logs/llm-usage.jsonl").read_text()
        records = [json.loads(line) for line in content.splitlines()]
        assert records[0]["input_tokens"] == 123
        assert records[0]["cached_tokens"] == 10
        assert records[1]["output_tokens"] == 22
        assert records[2] == {"time": records[2]["time"], "provider": "gemini", "stage": "notes", "requests": 1}
        assert "private" not in content
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = previous


def test_one_large_segment_cannot_repeat_entire_lecture_in_every_chunk():
    raw = "lecture " * 2000
    evidence = build_refinement_evidence({"segments": [{"text": raw, "start_time": 0, "end_time": 100}]})
    chunks = [raw[i:i + 4000] for i in range(0, len(raw), 4000)]
    scoped = chunk_refinement_evidence(raw, chunks, evidence)
    assert all(len(item["segments"][0]["text"]) <= 4480 for item in scoped)
