"""Focused tests for STTConfig and STTResult config-layer changes (Task Group 1)."""
from __future__ import annotations

import pytest

from lecture_auto.stt_config import STTConfig, SUPPORTED_API_PROVIDERS
from lecture_auto.stt_runtime import DiarizedSegment, STTResult


def test_stt_config_language_defaults_to_none() -> None:
    config = STTConfig()
    assert config.language is None


def test_stt_config_language_can_be_set() -> None:
    config = STTConfig(language="english")
    assert config.language == "english"


def test_stt_config_diarization_defaults_to_false() -> None:
    config = STTConfig()
    assert config.diarization is False


def test_stt_config_diarization_enabled() -> None:
    config = STTConfig(diarization=True)
    assert config.diarization is True


def test_stt_config_deepgram_provider_is_supported() -> None:
    assert "deepgram" in SUPPORTED_API_PROVIDERS


def test_stt_config_validation_passes_with_deepgram_provider() -> None:
    config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key-123")
    config.validate()


def test_stt_config_google_chirp3_provider_is_supported() -> None:
    assert "google-chirp3" in SUPPORTED_API_PROVIDERS


def test_stt_config_google_chirp3_validation_passes_with_project_id() -> None:
    config = STTConfig(
        mode="api",
        api_provider="google-chirp3",
        api_key="AIzaTest",
        google_project_id="my-project",
    )
    config.validate()


def test_stt_config_google_chirp3_validation_passes_without_api_key() -> None:
    config = STTConfig(
        mode="api",
        api_provider="google-chirp3",
        api_key=None,
        google_project_id="my-project",
    )
    config.validate()


def test_stt_config_google_chirp3_validation_requires_project_id() -> None:
    config = STTConfig(
        mode="api",
        api_provider="google-chirp3",
        api_key="AIzaTest",
        google_project_id=None,
    )
    with pytest.raises(ValueError, match="google_project_id is required"):
        config.validate()


def test_stt_config_google_chirp3_validation_rejects_blank_project_id() -> None:
    config = STTConfig(
        mode="api",
        api_provider="google-chirp3",
        api_key="AIzaTest",
        google_project_id="   ",
    )
    with pytest.raises(ValueError, match="google_project_id is required"):
        config.validate()


def test_stt_result_segments_default_empty() -> None:
    result = STTResult(transcript_text="hello", provider="test", mode="api")
    assert result.segments == []
    assert result.language is None


def test_stt_result_diarized_markdown_formatting() -> None:
    segments = [
        DiarizedSegment(speaker="Speaker 1", start_time=0.0, end_time=5.0, text="Hello there."),
        DiarizedSegment(speaker="Speaker 2", start_time=5.5, end_time=10.0, text="Hi back!"),
        DiarizedSegment(speaker="Speaker 1", start_time=10.5, end_time=15.0, text="How are you?"),
    ]
    result = STTResult(
        transcript_text="plaintext fallback",
        provider="test",
        mode="api",
        language="en",
        segments=segments,
    )
    markdown = result.to_diarized_markdown()
    assert "**Speaker 1**" in markdown
    assert "**Speaker 2**" in markdown
    assert "[00:00 - 00:05] Hello there." in markdown
    assert "[00:05 - 00:10] Hi back!" in markdown
    assert "[00:10 - 00:15] How are you?" in markdown
