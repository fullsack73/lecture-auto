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
