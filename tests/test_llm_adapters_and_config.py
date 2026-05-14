"""Focused tests for LLMConfig and GeminiLLMAdapter config-layer changes (Task Group 1)."""
from __future__ import annotations

import pytest
import sys
from unittest.mock import MagicMock, patch

from lecture_auto.llm_config import LLMConfig

# Mock modules to avoid ImportError when llm_adapter is imported
mock_google = MagicMock()
mock_genai = MagicMock()
mock_google.genai = mock_genai
sys.modules['google'] = mock_google
sys.modules['google.genai'] = mock_genai

from lecture_auto.llm_adapter import (
    GeminiLLMAdapter,
    LLMConfigError,
)

def test_llm_config_validation_fails_without_api_key() -> None:
    config = LLMConfig(api_key=None)
    with pytest.raises(ValueError, match="Gemini API key is required"):
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
    sys.modules['google.genai'].reset_mock()
    config = LLMConfig(api_key="valid-key")
    adapter = GeminiLLMAdapter(config)

    sys.modules['google.genai'].Client.assert_called_once_with(api_key="valid-key")


def test_gemini_adapter_missing_api_key_raises_error() -> None:
    config = LLMConfig(api_key="")
    with pytest.raises(LLMConfigError, match="Gemini API key is required"):
        GeminiLLMAdapter(config)


def test_gemini_adapter_refine_transcript_empty_text() -> None:
    config = LLMConfig(api_key="valid-key")
    adapter = GeminiLLMAdapter(config)
    result = adapter.refine_transcript("   ")
    assert result == "   "


def test_refine_transcript_uses_adaptive_chunk_size_for_large_input() -> None:
    sys.modules['google.genai'].reset_mock()

    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Refined"
    mock_client_instance.models.generate_content.return_value = mock_response
    sys.modules['google.genai'].Client.return_value = mock_client_instance

    config = LLMConfig(api_key="valid-key", chunk_size=4000)
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
