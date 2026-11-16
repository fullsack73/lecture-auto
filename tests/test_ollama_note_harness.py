from __future__ import annotations

import json
from unittest.mock import MagicMock

from lecture_auto.llm_adapter import OllamaLLMAdapter
from lecture_auto.llm_config import LLMConfig


def _adapter() -> OllamaLLMAdapter:
    adapter = OllamaLLMAdapter(
        LLMConfig(provider="ollama", model_name="test-model", language="Korean")
    )
    adapter.ollama = MagicMock()
    return adapter


def _ollama_response(payload: dict) -> dict:
    return {"message": {"content": json.dumps(payload, ensure_ascii=False)}}


def _ollama_raw_response(content: str) -> dict:
    return {"message": {"content": content}}


def _six_core_concepts(seed: str) -> list[str]:
    return [f"{seed} 핵심 개념 {index}는 강의 이해에 필요한 구체 항목이다." for index in range(1, 7)]


def _detailed_sections() -> list[dict[str, list[str] | str]]:
    return [
        {
            "title": "정렬 알고리즘 비교",
            "bullets": [
                "정렬 알고리즘은 데이터를 기준에 맞게 재배열하는 절차다.",
                "버블 정렬은 인접 원소를 반복 비교해 위치를 바꾼다.",
                "병합 정렬은 배열을 나눈 뒤 정렬된 부분 결과를 합친다.",
                "입력 크기가 커질수록 시간 복잡도 차이가 선택 기준이 된다.",
            ],
        },
        {
            "title": "시간 복잡도 해석",
            "bullets": [
                "시간 복잡도는 입력 크기 증가에 따른 실행 시간 증가율을 설명한다.",
                "복잡도 비교는 같은 문제를 푸는 여러 알고리즘의 효율을 구분한다.",
                "최악의 경우 분석은 성능 보장을 이해하는 데 중요하다.",
                "강의는 정렬 방식의 구조와 비용을 함께 비교한다.",
            ],
        },
    ]



def _valid_payload() -> dict:
    return {
        "note_title": "정렬 알고리즘과 시간 복잡도",
        "topic_overview": ["정렬 알고리즘의 목적과 비교 기준"],
        "core_concepts": _six_core_concepts("정렬"),
        "detailed_explanations": _detailed_sections(),
        "examples_mentioned": ["버블 정렬", "병합 정렬"],
        "questions_to_review": [
            "정렬 알고리즘은 어떤 문제를 해결하는가?",
            "시간 복잡도는 알고리즘 비교에서 왜 중요한가?",
            "버블 정렬과 병합 정렬의 핵심 차이는 무엇인가?",
            "입력 크기가 커질 때 정렬 방식 선택은 어떻게 달라지는가?",
        ],
        "exam_related_mentions": ["중간고사에 시간 복잡도 비교가 나온다고 언급했다."],
    }


def test_ollama_notes_harness_repairs_json_and_renders_structured_markdown() -> None:
    adapter = _adapter()
    invalid = _valid_payload()
    invalid["questions_to_review"] = ["정렬이란?"]
    adapter.ollama.chat.side_effect = [_ollama_response(invalid), _ollama_response(_valid_payload())]
    notes = adapter.generate_notes("정렬 강의", "# ignored template")
    assert notes.startswith("# 정렬 알고리즘과 시간 복잡도")
    assert "### 정렬 알고리즘 비교" in notes
    assert adapter.ollama.chat.call_count == 2
    calls = adapter.ollama.chat.call_args_list
    assert "Repair this JSON" in calls[1].kwargs["messages"][1]["content"]
    assert "# ignored template" in calls[0].kwargs["messages"][0]["content"]
    assert all("# ignored template" not in c.kwargs["messages"][1]["content"] for c in calls)


def test_ollama_notes_harness_uses_valid_json_without_repair() -> None:
    adapter = _adapter()
    adapter.ollama.chat.return_value = _ollama_response(_valid_payload())
    notes = adapter.generate_notes("정렬 알고리즘 강의", "# ignored template")
    assert adapter.ollama.chat.call_count == 1
    assert notes.startswith("# 정렬 알고리즘과 시간 복잡도")
    assert "## Topic Overview" in notes
    assert "### 정렬 알고리즘 비교" in notes
    assert "- 버블 정렬" in notes
    assert "중간고사에 시간 복잡도 비교" in notes


def test_ollama_notes_harness_recovers_invalid_backslash_escapes() -> None:
    adapter = _adapter()
    raw = json.dumps(_valid_payload(), ensure_ascii=False).replace("정렬 핵심 개념 1", r"\alpha 핵심 개념 1")
    adapter.ollama.chat.return_value = _ollama_raw_response(raw)
    notes = adapter.generate_notes("학습률 alpha 강의", "# ignored template")
    assert r"\alpha 핵심 개념 1" in notes
    assert adapter.ollama.chat.call_count == 1


def test_ollama_notes_harness_repairs_malformed_json_syntax() -> None:
    adapter = _adapter()
    raw = json.dumps(_valid_payload(), ensure_ascii=False)
    malformed = raw.replace(', "topic_overview"', ' "topic_overview"', 1)
    adapter.ollama.chat.side_effect = [_ollama_raw_response(malformed), _ollama_response(_valid_payload())]
    notes = adapter.generate_notes("자료구조 강의", "# ignored template")
    assert "## Core Concepts" in notes
    assert adapter.ollama.chat.call_count == 2
    prompt = adapter.ollama.chat.call_args_list[1].kwargs["messages"][1]["content"]
    assert "syntactically invalid" in prompt
    assert "Expecting ',' delimiter" in prompt
