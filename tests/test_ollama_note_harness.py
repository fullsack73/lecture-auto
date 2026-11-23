from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from lecture_auto.llm_adapter import LLMNoteQualityError, OllamaLLMAdapter
from lecture_auto.llm_config import LLMConfig


@pytest.fixture(autouse=True)
def isolate_usage_logging(monkeypatch):
    monkeypatch.setattr("lecture_auto.llm_adapter._log_llm_usage", lambda *args, **kwargs: None)


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
    invalid["questions_to_review"] = []
    adapter.ollama.chat.side_effect = [
        _ollama_response(invalid),
        _ollama_response({"issues": []}),
        _ollama_response({
            "questions_to_review": ["인접 원소 교환이 정렬을 어떻게 진행시키는가?"],
            "note_title": "이 제목은 교체하면 안 된다",
        }),
        _ollama_response({"issues": []}),
    ]
    notes = adapter.generate_notes("정렬 강의", "# ignored template")
    assert notes.startswith("# 정렬 알고리즘과 시간 복잡도")
    assert "### 정렬 알고리즘 비교" in notes
    assert "인접 원소 교환이 정렬을 어떻게 진행시키는가?" in notes
    assert adapter.ollama.chat.call_count == 4
    calls = adapter.ollama.chat.call_args_list
    assert "Repair this JSON" in calls[2].kwargs["messages"][1]["content"]
    assert "# ignored template" in calls[0].kwargs["messages"][0]["content"]
    assert all("# ignored template" not in c.kwargs["messages"][1]["content"] for c in calls)


def test_ollama_notes_harness_uses_valid_json_without_repair() -> None:
    adapter = _adapter()
    adapter.ollama.chat.side_effect = [
        _ollama_response(_valid_payload()), _ollama_response({"issues": []}),
    ]
    notes = adapter.generate_notes("정렬 알고리즘 강의", "# ignored template")
    assert adapter.ollama.chat.call_count == 2
    assert notes.startswith("# 정렬 알고리즘과 시간 복잡도")
    assert "## Topic Overview" in notes
    assert "### 정렬 알고리즘 비교" in notes
    assert "- 버블 정렬" in notes
    assert "중간고사에 시간 복잡도 비교" in notes


def test_ollama_notes_harness_recovers_invalid_backslash_escapes() -> None:
    adapter = _adapter()
    raw = json.dumps(_valid_payload(), ensure_ascii=False).replace("정렬 핵심 개념 1", r"\alpha 핵심 개념 1")
    adapter.ollama.chat.side_effect = [
        _ollama_raw_response(raw), _ollama_response({"issues": []}),
    ]
    notes = adapter.generate_notes("학습률 alpha 강의", "# ignored template")
    assert r"\alpha 핵심 개념 1" in notes
    assert adapter.ollama.chat.call_count == 2


def test_ollama_notes_harness_repairs_malformed_json_syntax() -> None:
    adapter = _adapter()
    raw = json.dumps(_valid_payload(), ensure_ascii=False)
    malformed = raw.replace(', "topic_overview"', ' "topic_overview"', 1)
    adapter.ollama.chat.side_effect = [
        _ollama_raw_response(malformed),
        _ollama_response(_valid_payload()),
        _ollama_response({"issues": []}),
    ]
    notes = adapter.generate_notes("자료구조 강의", "# ignored template")
    assert "## Core Concepts" in notes
    assert adapter.ollama.chat.call_count == 3
    prompt = adapter.ollama.chat.call_args_list[1].kwargs["messages"][1]["content"]
    assert "syntactically invalid" in prompt
    assert "Expecting ',' delimiter" in prompt


def test_short_lecture_renders_concrete_code_and_formula_without_padding() -> None:
    adapter = _adapter()
    adapter.ollama.chat.side_effect = [
        _ollama_response({
            "note_title": "워킹셋 계산",
            "topic_overview": ["최근 참조에서 필요한 프레임을 추정한다."],
            "core_concepts": ["워킹셋 크기는 최근 참조에서 서로 다른 페이지 수다."],
            "detailed_explanations": [{
                "title": "워킹셋과 프레임 수",
                "bullets": ["페이지 1, 2, 1에 접근했다면 2개 프레임이 필요하다. 1개뿐이면 교체가 일어난다."],
                "blocks": [
                    {"kind": "formula", "text": r"\lvert \{1,2\}\rvert = 2"},
                    {"kind": "code", "text": "def wss(pages):\n\toutput = len(set(pages))\n\treturn output", "language": "python"},
                ],
            }],
            "questions_to_review": ["프레임이 1개일 때 어떤 일이 생기는가?"],
            "examples_mentioned": [],
            "exam_related_mentions": [],
        }),
        _ollama_response({"issues": []}),
    ]

    notes = adapter.generate_notes(
        "워킹셋은 최근 참조 중 고유 페이지 수다. 1, 2, 1은 2개다. "
        "프레임이 1개면 페이지를 교체한다. 코드 예시는 "
        "def wss(pages):\n\toutput = len(set(pages))\n\treturn output",
        "# 제목",
    )
    assert "2개 프레임이 필요하다" in notes
    assert "$$\n" + r"\lvert \{1,2\}\rvert = 2" + "\n$$" in notes
    assert "```python\ndef wss(pages):\n\toutput = len(set(pages))\n\treturn output\n```" in notes
    assert "## Exam related mentions\n- Not mentioned." in notes
    assert adapter.ollama.chat.call_count == 2


def test_ollama_rejects_a_note_if_its_explanation_gap_survives_repair() -> None:
    adapter = _adapter()
    original = _valid_payload()
    finding = _ollama_response({"issues": [{
        "section": "detailed_explanations",
        "message": "누락된 병합 과정과 값을 설명해라.",
        "chunk_ids": [1],
    }]})
    adapter.ollama.chat.side_effect = [
        _ollama_response(original),
        finding,
        _ollama_response({"detailed_explanations": original["detailed_explanations"]}),
        finding,
    ]

    with pytest.raises(LLMNoteQualityError, match="Note quality issues remain after repair"):
        adapter.generate_notes("정렬한 두 배열의 첫 값을 비교해 작은 값부터 꺼내서 병합한다.", "# 제목")
    assert adapter.ollama.chat.call_count == 4
