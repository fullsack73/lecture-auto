import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from lecture_auto.llm_adapter import GeminiLLMAdapter, OllamaLLMAdapter, LLMTransientNetworkError
from lecture_auto.llm_config import LLMConfig
from lecture_auto.stt_refinement import RefinementCheckpoint, build_refinement_evidence, chunk_refinement_evidence


@pytest.mark.parametrize('provider', ['gemini', 'ollama'])
def test_failed_refinement_resumes_and_invalidates_changed_input(tmp_path, provider):
    with patch('google.genai.Client'):
        adapter = (GeminiLLMAdapter(LLMConfig(api_key='fake', chunk_size=500)) if provider == 'gemini'
                   else OllamaLLMAdapter(LLMConfig(provider='ollama', chunk_size=500)))
    call = adapter.client.models.generate_content if provider == 'gemini' else MagicMock()
    if provider == 'ollama':
        adapter.ollama = MagicMock(chat=call)
    result = SimpleNamespace(text='completed first') if provider == 'gemini' else {'message': {'content': 'completed first'}}
    call.side_effect = [result, RuntimeError('500 temporary error')]
    raw = 'first unique phrase. ' * 20 + 'second different phrase. ' * 25
    path = tmp_path / 'checkpoint.json'
    with patch('lecture_auto.llm_adapter._log_llm_usage'):
        with pytest.raises(LLMTransientNetworkError):
            adapter.refine_transcript(raw, checkpoint_path=str(path))
        assert json.loads(path.read_text())['completed'] == ['completed first']
        assert 'fake' not in path.read_text()
        first_call = call.call_args_list[0]
        failed_call = call.call_args_list[1]
        call.reset_mock()
        call.side_effect = None
        call.return_value = result
        text = adapter.refine_transcript(raw, checkpoint_path=str(path))
        assert text.startswith('completed first\n')
        assert call.call_args_list[0] == failed_call
        assert all(c != first_call for c in call.call_args_list)
        call.reset_mock()
        adapter.refine_transcript(raw, checkpoint_path=str(path))
        call.assert_not_called()
        adapter.config.language = 'changed'
        adapter.refine_transcript(raw, checkpoint_path=str(path))
        assert call.called
        call.reset_mock()
        adapter.refine_transcript(raw + ' changed source', checkpoint_path=str(path))
        assert call.called


def test_checkpoint_ignores_invalid_files_and_rejects_empty_results(tmp_path):
    path = tmp_path / 'checkpoint.json'
    for content in ('broken', '[]', '{"fingerprint":"x","completed":[null]}'):
        path.write_text(content)
        cp = RefinementCheckpoint(str(path), 'x', 2)
        assert cp.completed == []
    with pytest.raises(ValueError):
        cp.append('  ')
    cp.append('good')
    assert RefinementCheckpoint(str(path), 'x', 2).completed == ['good']
    assert RefinementCheckpoint(str(path), 'other', 2).completed == []


def test_healthy_rows_omitted_and_late_uncertain_rows_preserved():
    segments = [{'text': f'phrase{i}.', 'start_time': i, 'end_time': i + 1,
                 'avg_logprob': -1.5 if i == 100 else -0.1} for i in range(120)]
    raw = ' '.join(s['text'] for s in segments)
    scoped = chunk_refinement_evidence(raw, [raw], build_refinement_evidence({'segments': segments}))[0]
    assert len(scoped['segments']) == 1
    assert scoped['segments'][0][2] == 100
