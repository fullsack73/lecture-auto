"""Strategic gap-filling tests for STT feature (Task Group 3)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService
from lecture_auto.stt_config import STTConfig
from lecture_auto.stt_runtime import (
    DiarizedSegment,
    STTConfigError,
    STTProviderAuthError,
    STTResult,
    STTTransientNetworkError,
)


class FakeDiarizedAdapter:
    """Adapter that returns diarized segments for integration testing."""

    def transcribe(self, *, audio_path: str) -> STTResult:
        return STTResult(
            transcript_text="Hello. Hi there.",
            provider="fake-diarized",
            mode="api",
            language="en",
            segments=[
                DiarizedSegment(speaker="Speaker 1", start_time=0.0, end_time=3.0, text="Hello."),
                DiarizedSegment(speaker="Speaker 2", start_time=3.5, end_time=6.0, text="Hi there."),
            ],
        )


def _service(tmp_path: Path, *, config: STTConfig, api_adapter=None, local_adapter=None) -> SessionService:
    store = SessionMetadataStore(tmp_path / "config" / "sessions.json")
    return SessionService(
        store=store,
        stt_config=config,
        api_stt_adapter=api_adapter,
        local_stt_adapter=local_adapter,
    )


def test_diarized_transcript_written_as_markdown(tmp_path: Path) -> None:
    """Verify that diarized segments produce formatted markdown in the transcript file."""
    service = _service(
        tmp_path,
        config=STTConfig(mode="api", api_provider="deepgram", api_key="k", diarization=True),
        api_adapter=FakeDiarizedAdapter(),
    )
    service.session_create("session-gap-01", "2026-03-07")
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")
    service.import_audio("session-gap-01", str(source))

    service.transcribe_session("session-gap-01")

    transcript = tmp_path / "transcripts" / "session-gap-01-raw.md"
    assert transcript.exists()
    content = transcript.read_text(encoding="utf-8")
    assert "**Speaker 1**" in content
    assert "**Speaker 2**" in content


def test_config_validation_rejects_whitespace_only_api_key() -> None:
    """API key with only spaces should fail validation."""
    config = STTConfig(mode="api", api_provider="deepgram", api_key="   ")
    with pytest.raises(ValueError, match="API key is required"):
        config.validate()


def test_config_validation_rejects_whitespace_only_local_model() -> None:
    """Local model name with only spaces should fail validation."""
    config = STTConfig(mode="local", local_model_name="   ")
    with pytest.raises(ValueError, match="Local model name is required"):
        config.validate()


def test_stt_result_diarized_markdown_returns_plain_text_when_no_segments() -> None:
    """to_diarized_markdown falls back to transcript_text when segments are empty."""
    result = STTResult(transcript_text="just text", provider="test", mode="api")
    assert result.to_diarized_markdown() == "just text"


def test_deepgram_adapter_network_error_maps_to_transient() -> None:
    """Timeout/connection errors should map to STTTransientNetworkError."""
    from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter
    from unittest.mock import MagicMock

    config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key")
    adapter = DeepgramSTTRuntimeAdapter(config=config)

    mock_deepgram = MagicMock()
    mock_client = MagicMock()
    mock_deepgram.DeepgramClient.return_value = mock_client
    mock_deepgram.PrerecordedOptions = MagicMock
    mock_deepgram.FileSource = dict
    mock_client.listen.rest.v.return_value.transcribe_file.side_effect = (
        Exception("Connection timeout error")
    )

    with patch.dict("sys.modules", {"deepgram": mock_deepgram}):
        with patch("builtins.open", MagicMock()):
            with pytest.raises(STTTransientNetworkError):
                adapter.transcribe(audio_path="/tmp/test.wav")


def test_service_builds_deepgram_adapter_when_provider_is_deepgram(tmp_path: Path) -> None:
    """SessionService dispatches to DeepgramSTTRuntimeAdapter when provider == deepgram."""
    config = STTConfig(mode="api", api_provider="deepgram", api_key="test-key")
    service = _service(tmp_path, config=config)

    with patch("lecture_auto.deepgram_adapter.DeepgramSTTRuntimeAdapter") as MockAdapter:
        MockAdapter.return_value = FakeDiarizedAdapter()
        adapter = service._build_stt_adapter()
        MockAdapter.assert_called_once_with(config=config)


def test_service_builds_whisper_adapter_when_mode_is_local(tmp_path: Path) -> None:
    """SessionService dispatches to FasterWhisperSTTRuntimeAdapter in local mode."""
    config = STTConfig(mode="local", local_model_name="large-v3")
    service = _service(tmp_path, config=config)

    with patch("lecture_auto.whisper_adapter.FasterWhisperSTTRuntimeAdapter") as MockAdapter:
        MockAdapter.return_value = FakeDiarizedAdapter()
        adapter = service._build_stt_adapter()
        MockAdapter.assert_called_once_with(config=config)


def test_diarized_segment_speaker_continuity_in_markdown() -> None:
    """Same speaker in consecutive segments should not repeat the speaker header."""
    segments = [
        DiarizedSegment(speaker="Speaker 1", start_time=0.0, end_time=5.0, text="First."),
        DiarizedSegment(speaker="Speaker 1", start_time=5.0, end_time=10.0, text="Second."),
        DiarizedSegment(speaker="Speaker 2", start_time=10.0, end_time=15.0, text="Response."),
    ]
    result = STTResult(
        transcript_text="fallback",
        provider="test",
        mode="api",
        segments=segments,
    )
    md = result.to_diarized_markdown()
    assert md.count("**Speaker 1**") == 1
    assert md.count("**Speaker 2**") == 1


def test_config_language_none_means_autodetect() -> None:
    """When language is None, auto-detection is implied — no validation error."""
    config = STTConfig(mode="api", api_provider="deepgram", api_key="key", language=None)
    config.validate()
    assert config.language is None
