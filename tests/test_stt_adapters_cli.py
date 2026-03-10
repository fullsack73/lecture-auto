"""Focused tests for STT adapters and CLI config interactions (Task Group 2)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lecture_auto.stt_config import STTConfig
from lecture_auto.stt_runtime import (
    DiarizedSegment,
    STTConfigError,
    STTProviderAuthError,
    STTResult,
    STTTransientNetworkError,
)


class TestDeepgramAdapter:
    """Tests for DeepgramSTTRuntimeAdapter using mocked SDK."""

    def test_deepgram_adapter_rejects_empty_api_key(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="")
        with pytest.raises(STTConfigError, match="API key is required"):
            DeepgramSTTRuntimeAdapter(config=config)

    def test_deepgram_adapter_rejects_empty_audio_path(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key")
        adapter = DeepgramSTTRuntimeAdapter(config=config)
        with pytest.raises(STTConfigError, match="Audio path is required"):
            adapter.transcribe(audio_path="   ")

    def test_deepgram_adapter_missing_httpx_raises_config_error(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key")
        adapter = DeepgramSTTRuntimeAdapter(config=config)

        with patch.dict("sys.modules", {"httpx": None}):
            with pytest.raises(STTConfigError, match="httpx is not installed"):
                adapter.transcribe(audio_path="/tmp/test.wav")

    def test_deepgram_adapter_maps_auth_error_to_provider_auth(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="bad-key")
        adapter = DeepgramSTTRuntimeAdapter(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"err_code":"INVALID_AUTH","err_msg":"Invalid credentials."}'

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            with patch("builtins.open", MagicMock()):
                with pytest.raises(STTProviderAuthError):
                    adapter.transcribe(audio_path="/tmp/test.wav")

    def test_deepgram_adapter_uses_mp3_content_type(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key")
        adapter = DeepgramSTTRuntimeAdapter(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": {
                "channels": [{"alternatives": [{"transcript": "ok"}]}],
            }
        }

        captured_headers: dict[str, str] = {}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        def _post(*args, **kwargs):
            headers = kwargs.get("headers") or {}
            captured_headers.update(headers)
            return mock_response

        mock_client.post.side_effect = _post

        with patch("httpx.Client", return_value=mock_client):
            with patch("builtins.open", MagicMock()):
                result = adapter.transcribe(audio_path="/tmp/test.mp3")

        assert result.transcript_text == "ok"
        assert captured_headers["Content-Type"] == "audio/mp3"

    def test_deepgram_adapter_maps_httpx_timeout_to_transient_error(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter
        import httpx

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key")
        adapter = DeepgramSTTRuntimeAdapter(config=config)

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("request timed out")

        with patch("httpx.Client", return_value=mock_client):
            with patch("builtins.open", MagicMock()):
                with pytest.raises(STTTransientNetworkError, match="timed out"):
                    adapter.transcribe(audio_path="/tmp/test.mp3")


class TestFasterWhisperAdapter:
    """Tests for FasterWhisperSTTRuntimeAdapter using mocked model."""

    def test_whisper_adapter_rejects_empty_audio_path(self) -> None:
        from lecture_auto.whisper_adapter import FasterWhisperSTTRuntimeAdapter

        config = STTConfig(mode="local", local_model_name="large-v3")
        adapter = FasterWhisperSTTRuntimeAdapter(config=config)
        with pytest.raises(STTConfigError, match="Audio path is required"):
            adapter.transcribe(audio_path="   ")

    def test_whisper_adapter_missing_package_raises_config_error(self) -> None:
        from lecture_auto.whisper_adapter import FasterWhisperSTTRuntimeAdapter

        config = STTConfig(mode="local", local_model_name="large-v3")
        adapter = FasterWhisperSTTRuntimeAdapter(config=config)

        with patch.dict("sys.modules", {"faster_whisper": None}):
            with pytest.raises(STTConfigError, match="faster-whisper is not installed"):
                adapter.transcribe(audio_path="/tmp/test.wav")


class TestSTTConfigCLIBehaviors:
    """Tests for CLI config set behaviors on STTConfig."""

    def test_config_set_stt_language(self) -> None:
        config = STTConfig(mode="local", local_model_name="large-v3")
        assert config.language is None
        config.language = "english"
        assert config.language == "english"
        config.validate()

    def test_config_set_stt_api_key_for_deepgram(self) -> None:
        config = STTConfig(mode="api", api_provider="deepgram")
        config.api_key = "new-deepgram-key"
        config.validate()
        assert config.api_key == "new-deepgram-key"
