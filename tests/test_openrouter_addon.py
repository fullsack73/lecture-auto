from dataclasses import asdict
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lecture_auto.application import AppConfig, ConfigRepository
from lecture_auto.gemini_addon import HostedLLMAddonAdapter
from lecture_auto.gemini_addon_worker import dispatch
from lecture_auto.llm_adapter import LLMConfigError, LLMProviderAuthError
from lecture_auto.llm_config import LLMConfig
from lecture_auto.local_runtime import LocalRuntimeError, LocalRuntimeManager, LocalRuntimeMissingError


def test_openrouter_worker_refines_and_generates_notes(monkeypatch, tmp_path):
    monkeypatch.setattr("lecture_auto.llm_adapter._log_llm_usage", Mock())
    monkeypatch.setattr(sys, "path", list(sys.path))
    config = asdict(LLMConfig(provider="openrouter", api_key="fake", model_name="vendor/model"))
    note = {
        "topic_overview": ["병합"], "core_concepts": ["첫 값 비교"],
        "detailed_explanations": [{"title": "병합 순서", "bullets": ["작은 값부터 놓는다."]}],
        "questions_to_review": ["어느 값을 먼저 놓는가?"],
    }
    def response(content):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None)

    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    create = Mock(side_effect=[
        response("첫 값을 비교한다."),
        response("자료의 병합 정의"),
        response(None),
        response(json.dumps(note)),
        response('{"issues": []}'),
    ])
    sdk = SimpleNamespace(OpenAI=Mock(return_value=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    )))
    monkeypatch.setitem(sys.modules, "openai", sdk)
    refined = dispatch({"action": "openrouter_refine_transcript", "config": config, "raw_text": "첫 값을 비교함"})
    result = dispatch({
        "action": "openrouter_generate_notes",
        "config": config,
        "transcript": refined["text"],
        "material_path": str(pdf),
    })
    assert refined["text"] == "첫 값을 비교한다."
    assert "작은 값부터 놓는다." in result["text"]
    assert sdk.OpenAI.call_args.kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert create.call_args_list[0].kwargs["model"] == "vendor/model"
    assert "response_format" not in create.call_args_list[0].kwargs
    attachment = create.call_args_list[1].kwargs["messages"][0]["content"][1]
    assert attachment == {
        "type": "file",
        "file": {"filename": "slides.pdf", "file_data": "data:application/pdf;base64,JVBERi0xLjc="},
    }
    note_messages = create.call_args_list[2].kwargs["messages"]
    assert "자료의 병합 정의" in note_messages[0]["content"]
    assert "base64" not in str(note_messages)
    assert create.call_args_list[3] == create.call_args_list[2]
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


def test_openrouter_addon_routing_and_errors(tmp_path, monkeypatch):
    manager = LocalRuntimeManager(tmp_path)
    monkeypatch.setattr(manager, "python_for", Mock(return_value=sys.executable))
    worker = Mock(return_value={"text": "note"})
    monkeypatch.setattr(manager, "_run_worker", worker)
    adapter = HostedLLMAddonAdapter(LLMConfig(provider="openrouter", api_key="fake"), manager)
    assert adapter.generate_notes("lecture", "template") == "note"
    assert worker.call_args.args[1]["action"] == "openrouter_generate_notes"
    assert worker.call_args.kwargs["worker_script"] == manager.gemini_worker_script
    worker.side_effect = LocalRuntimeError("Credentials rejected.", code="LLMProviderAuthError")
    with pytest.raises(LLMProviderAuthError, match="Credentials rejected"):
        adapter.generate_notes("lecture", "template")
    manager.python_for.side_effect = LocalRuntimeMissingError("openrouter")
    with pytest.raises(LLMConfigError, match="OpenRouter add-on is not installed"):
        adapter.generate_notes("lecture", "template")


def test_openrouter_key_is_separate_from_gemini_key(tmp_path, monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MODEL", "GEMINI_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    secrets = {"gemini_api_key": "gemini-secret"}
    store = SimpleNamespace(get=secrets.get, set=secrets.__setitem__)
    path = tmp_path / "config.json"
    repo = ConfigRepository(path, secret_store=store)
    repo.save(AppConfig(tmp_path, llm=LLMConfig(
        provider="openrouter", model_name="vendor/model", api_key="router-secret",
    )))
    assert secrets == {"gemini_api_key": "gemini-secret", "openrouter_api_key": "router-secret"}
    assert "router-secret" not in path.read_text()
    assert repo.load().llm.api_key == "router-secret"
    assert repo.load().llm.model_name == "vendor/model"
