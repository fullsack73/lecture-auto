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
    segments = [{"text": f"segment-{i} content.", "start_time": i, "end_time": i + 1, "avg_logprob": -1.2}
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
    assert [s[2] for s in scoped[1]["segments"]] == [99, 100, 101]
    assert all(isinstance(s, list) and len(s) == 5 for s in scoped[1]["segments"])
    assert scoped[1]["asr_passes"]["candidate_pairs"][0]["retry"] == "relevant"
    assert len(scoped[1]["asr_passes"]["candidate_pairs"]) == 1
    assert "large_report" not in json.dumps(scoped)
    assert len(json.dumps(scoped)) < len(json.dumps(evidence)) / 10


def test_evidence_alignment_handles_whitespace_repetition_and_unmatched_text():
    evidence = build_refinement_evidence({"segments": [
        {"text": "same words", "start_time": 1, "end_time": 2, "avg_logprob": -1.2},
        {"text": "same words", "start_time": 3, "end_time": 4, "avg_logprob": -1.2},
    ]})
    raw = "same\nwords\nsame words"
    scoped = chunk_refinement_evidence(raw, ["same\nwords", "same words"], evidence)
    assert [s[2] for s in scoped[1]["segments"]] == [1, 3]
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
                                           cached_content_token_count=10), text="private transcript"),
            input_characters={"transcript": 100, "context": 20, "system": 10})
        _log_llm_usage("ollama", "notes", {"prompt_eval_count": 77, "eval_count": 22,
                                          "message": {"content": "private notes"}})
        _log_llm_usage("gemini", "notes", SimpleNamespace(text="private"))
        content = (tmp_path / ".lecture_auto/logs/llm-usage.jsonl").read_text()
        records = [json.loads(line) for line in content.splitlines()]
        assert records[0]["input_tokens"] == 123
        assert records[0]["cached_tokens"] == 10
        assert records[0]["input_characters"] == {"transcript": 100, "context": 20, "system": 10}
        assert records[1]["output_tokens"] == 22
        assert records[2] == {"time": records[2]["time"], "provider": "gemini", "stage": "notes", "requests": 1}
        assert "private" not in content
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers[:] = previous


def test_one_large_segment_cannot_repeat_entire_lecture_in_every_chunk():
    raw = "lecture " * 2000
    evidence = build_refinement_evidence({"segments": [{"text": raw, "start_time": 0, "end_time": 100, "avg_logprob": -1.2}]})
    chunks = [raw[i:i + 4000] for i in range(0, len(raw), 4000)]
    scoped = chunk_refinement_evidence(raw, chunks, evidence)
    assert all(item["segments"][0][1] - item["segments"][0][0] <= 4480 for item in scoped)
    assert all("text" not in row for item in scoped for row in item["segments"])


def test_dense_short_segments_have_compact_evidence_without_duplicate_transcript():
    segments = [{"text": f"고유구간{i} 문장입니다.", "start_time": i * 0.7123456789,
                 "end_time": (i + 1) * 0.7123456789,
                 "avg_logprob": -1.887654321, "no_speech_prob": 0.0123456789}
                for i in range(300)]
    raw = " ".join(s["text"] for s in segments)
    chunks = [raw[:2000], raw[2000:4000], raw[4000:]]
    scoped = chunk_refinement_evidence(raw, chunks, build_refinement_evidence({"segments": segments}))
    for item in scoped:
        assert item["segment_fields"] == ["start_char", "end_char", "start_seconds", "avg_logprob", "no_speech_prob"]
        assert len(json.dumps(item, ensure_ascii=False, separators=(",", ":"))) < 4000
        assert all(row[3:] == [-1.888, 0.012] for row in item["segments"])
        assert "고유구간10 문장입니다." not in json.dumps(item["segments"], ensure_ascii=False)
        assert len(item["context_before"]) <= 240 and len(item["context_after"]) <= 240
    assert scoped[-1]["segments"][-1][2] > 100


def test_asr_candidates_keep_alternatives_without_copying_transcript():
    raw = "강의의 실제 원문입니다."
    evidence = build_refinement_evidence({"segments": [
        {"text": raw, "start_time": 1, "end_time": 3}], "metadata": {"asr_passes": {
            "candidate_pairs": [
                {"start_time": 1, "end_time": 3, "primary": "다른 ASR 후보입니다.", "retry": raw},
                {"start_time": 1, "end_time": 3, "primary": raw, "retry": raw},
            ]}}})
    scoped = chunk_refinement_evidence(raw, [raw], evidence)[0]
    assert scoped["asr_passes"]["candidate_pairs"] == [
        {"start_time": 1, "end_time": 3, "primary": "다른 ASR 후보입니다."}]
    assert raw not in json.dumps(scoped, ensure_ascii=False)


def test_offsets_stay_valid_when_an_unaligned_gap_separates_segments():
    raw = "first matched" + " gap" * 200 + " last matched"
    evidence = build_refinement_evidence({"segments": [
        {"text": "first matched", "start_time": 0, "end_time": 1, "avg_logprob": -1.2},
        {"text": "last matched", "start_time": 100, "end_time": 101, "avg_logprob": -1.2},
    ]})
    scoped = chunk_refinement_evidence(raw, ["last matched"], evidence)[0]
    assert len(scoped["segments"]) == 1
    assert all(row[0] < row[1] for row in scoped["segments"])
