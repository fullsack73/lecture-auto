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


def test_ollama_notes_harness_repairs_json_and_renders_structured_markdown() -> None:
    adapter = _adapter()
    adapter.ollama.chat.side_effect = [
        _ollama_response({"topic_overview": ["머신러닝의 기본 학습 방식 비교"]}),
        _ollama_response({"core_concepts": ["지도학습은 레이블이 있는 데이터로 모델을 학습한다."]}),
        _ollama_response(
            {"detailed_explanations": [{"title": "Sub Topic 1", "bullets": ["지도학습과 비지도학습을 구분한다."]}]}
        ),
        _ollama_response({"examples_mentioned": ["Not mentioned."]}),
        _ollama_response({"questions_to_review": ["지도학습이란 무엇인가?"]}),
        _ollama_response({"exam_related_mentions": ["Not mentioned."]}),
        _ollama_response(
            {
                "topic_overview": ["머신러닝의 기본 학습 방식 비교"],
                "core_concepts": ["지도학습은 레이블이 있는 데이터로 모델을 학습한다."],
                "detailed_explanations": [
                    {
                        "title": "지도학습과 비지도학습",
                        "bullets": ["지도학습과 비지도학습을 데이터 레이블 기준으로 구분한다."],
                    }
                ],
                "examples_mentioned": ["Not mentioned."],
                "questions_to_review": [
                    "지도학습은 어떤 데이터 조건에서 작동하는가?",
                    "비지도학습은 지도학습과 어떤 점에서 다른가?",
                    "레이블 유무는 모델 학습 방식에 어떤 영향을 주는가?",
                    "두 학습 방식의 차이를 알면 강의의 핵심 구조를 어떻게 재구성할 수 있는가?",
                ],
                "exam_related_mentions": ["Not mentioned."],
            }
        ),
    ]

    notes = adapter.generate_notes(
        "지도학습은 레이블 데이터를 사용하고 비지도학습도 있습니다.",
        "# ignored template",
        context_topic="머신러닝 기초",
    )

    assert "# Structured Lecture Notes" in notes
    assert "### 지도학습과 비지도학습" in notes
    assert "## Questions to Review" in notes
    assert "레이블 유무는 모델 학습 방식에 어떤 영향을 주는가?" in notes
    assert adapter.ollama.chat.call_count == 7
    assert adapter.ollama.chat.call_args_list[0].kwargs["format"] == "json"
    all_prompts = [
        call.kwargs["messages"][1]["content"]
        for call in adapter.ollama.chat.call_args_list
    ]
    assert all("# ignored template" not in prompt for prompt in all_prompts)
    assert "Generate only this section: topic_overview" in all_prompts[0]
    assert "Generate only this section: questions_to_review" in all_prompts[4]


def test_ollama_notes_harness_uses_valid_json_without_repair() -> None:
    adapter = _adapter()
    adapter.ollama.chat.side_effect = [
        _ollama_response({"topic_overview": ["정렬 알고리즘의 목적과 비교 기준"]}),
        _ollama_response({"core_concepts": ["시간 복잡도는 입력 크기에 따른 실행 시간 증가를 설명한다."]}),
        _ollama_response(
            {
                "detailed_explanations": [
                    {
                        "title": "정렬 알고리즘 비교",
                        "bullets": ["버블 정렬과 병합 정렬은 시간 복잡도에서 차이가 난다."],
                    }
                ]
            }
        ),
        _ollama_response({"examples_mentioned": ["버블 정렬", "병합 정렬"]}),
        _ollama_response(
            {
                "questions_to_review": [
                    "정렬 알고리즘은 어떤 문제를 해결하는가?",
                    "시간 복잡도는 알고리즘 비교에서 왜 중요한가?",
                    "버블 정렬과 병합 정렬의 핵심 차이는 무엇인가?",
                    "입력 크기가 커질 때 정렬 방식 선택은 어떻게 달라지는가?",
                ]
            }
        ),
        _ollama_response({"exam_related_mentions": ["중간고사에 시간 복잡도 비교가 나온다고 언급했다."]}),
    ]

    notes = adapter.generate_notes("정렬 알고리즘 강의", "# ignored template")

    assert adapter.ollama.chat.call_count == 6
    assert "## Topic Overview" in notes
    assert "### 정렬 알고리즘 비교" in notes
    assert "- 버블 정렬" in notes
    assert "중간고사에 시간 복잡도 비교" in notes


def test_ollama_notes_harness_recovers_invalid_backslash_escapes() -> None:
    adapter = _adapter()
    adapter.ollama.chat.side_effect = [
        _ollama_response({"topic_overview": ["미분 기호와 최적화 개요"]}),
        _ollama_raw_response(r'{"core_concepts":["\alpha는 학습률을 나타낸다."]}'),
        _ollama_response(
            {
                "detailed_explanations": [
                    {
                        "title": "학습률과 업데이트",
                        "bullets": [r"가중치 업데이트는 \alpha 값에 영향을 받는다."],
                    }
                ]
            }
        ),
        _ollama_response({"examples_mentioned": ["Not mentioned."]}),
        _ollama_response(
            {
                "questions_to_review": [
                    "학습률은 최적화 과정에서 어떤 역할을 하는가?",
                    "학습률이 너무 크면 어떤 문제가 생기는가?",
                    "학습률이 너무 작으면 학습 과정은 어떻게 달라지는가?",
                    "업데이트 식에서 학습률을 이해하면 강의 흐름을 어떻게 재구성할 수 있는가?",
                ]
            }
        ),
        _ollama_response({"exam_related_mentions": ["Not mentioned."]}),
    ]

    notes = adapter.generate_notes("학습률 alpha 강의", "# ignored template")

    assert r"\alpha는 학습률을 나타낸다." in notes
    assert r"가중치 업데이트는 \alpha 값에 영향을 받는다." in notes
