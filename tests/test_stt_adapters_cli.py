"""Focused tests for STT adapters and CLI config interactions (Task Group 2)."""
from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

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

        config = STTConfig(mode="api", api_provider="deepgram", api_key="", language="en")
        with pytest.raises(STTConfigError, match="API key is required"):
            DeepgramSTTRuntimeAdapter(config=config)

    def test_deepgram_adapter_rejects_empty_audio_path(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key", language="en")
        adapter = DeepgramSTTRuntimeAdapter(config=config)
        with pytest.raises(STTConfigError, match="Audio path is required"):
            adapter.transcribe(audio_path="   ")

    def test_deepgram_adapter_missing_httpx_raises_config_error(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key", language="en")
        adapter = DeepgramSTTRuntimeAdapter(config=config)

        with patch.dict("sys.modules", {"httpx": None}):
            with pytest.raises(STTConfigError, match="httpx is not installed"):
                adapter.transcribe(audio_path="/tmp/test.wav")

    def test_deepgram_adapter_maps_auth_error_to_provider_auth(self) -> None:
        from lecture_auto.deepgram_adapter import DeepgramSTTRuntimeAdapter

        config = STTConfig(mode="api", api_provider="deepgram", api_key="bad-key", language="en")
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

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key", language="en")
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

        config = STTConfig(mode="api", api_provider="deepgram", api_key="dg-key", language="en")
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


        with patch.dict("sys.modules", {"faster_whisper": None}):
            with pytest.raises(STTConfigError, match="faster-whisper is not installed"):
                adapter.transcribe(audio_path="/tmp/test.wav")


class TestGoogleChirp3Adapter:
    """Tests for GoogleChirp3STTRuntimeAdapter using mocked httpx."""

    _BASE_CONFIG = dict(
        mode="api",
        api_provider="google-chirp3",
        api_key="AIzaFakeKey",
        language="en",
        google_project_id="my-project",
    )

    def _make_config(self, **overrides) -> STTConfig:
        return STTConfig(**{**self._BASE_CONFIG, **overrides})

    # ------------------------------------------------------------------
    # Constructor validation
    # ------------------------------------------------------------------

    def test_rejects_when_no_api_key_and_no_access_token(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(STTConfigError, match="authentication is required"):
                GoogleChirp3STTRuntimeAdapter(config=self._make_config(api_key=""))

    def test_rejects_missing_project_id(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        with pytest.raises(STTConfigError, match="project ID is required"):
            GoogleChirp3STTRuntimeAdapter(config=self._make_config(google_project_id=None))

    def test_rejects_blank_project_id(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        with pytest.raises(STTConfigError, match="project ID is required"):
            GoogleChirp3STTRuntimeAdapter(config=self._make_config(google_project_id="  "))

    def test_normalizes_short_language_code_for_chirp3(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config(language="ko"))
        config_payload = adapter._build_recognition_config()
        assert config_payload["languageCodes"] == ["ko-KR"]

    def test_rejects_empty_audio_path(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())
        with pytest.raises(STTConfigError, match="Audio path is required"):
            adapter.transcribe(audio_path="   ")

    def test_missing_httpx_raises_config_error(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())
        with patch.dict("sys.modules", {"httpx": None}):
            with pytest.raises(STTConfigError, match="httpx is not installed"):
                adapter.transcribe(audio_path="/tmp/test.wav")

    # ------------------------------------------------------------------
    # HTTP error mapping
    # ------------------------------------------------------------------

    def test_maps_401_to_provider_auth_error(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())
        mock_recognizer_url = "https://us-speech.googleapis.com/v2/projects/p/locations/us/recognizers/_"

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": {"code": 401, "message": "API key not valid."}}'

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            with patch.object(adapter, "_resolve_recognizer_url", return_value=mock_recognizer_url):
                with patch("builtins.open", mock_open(read_data=b"fake audio")):
                    with pytest.raises(STTProviderAuthError):
                        adapter.transcribe(audio_path="/tmp/test.wav")

    def test_maps_403_to_provider_auth_error(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())
        mock_recognizer_url = "https://us-speech.googleapis.com/v2/projects/p/locations/us/recognizers/_"

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            with patch.object(adapter, "_resolve_recognizer_url", return_value=mock_recognizer_url):
                with patch("builtins.open", mock_open(read_data=b"fake audio")):
                    with pytest.raises(STTProviderAuthError):
                        adapter.transcribe(audio_path="/tmp/test.wav")

    def test_maps_timeout_to_transient_error(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter
        import httpx

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())
        mock_recognizer_url = "https://us-speech.googleapis.com/v2/projects/p/locations/us/recognizers/_"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("request timed out")

        with patch("httpx.Client", return_value=mock_client):
            with patch.object(adapter, "_resolve_recognizer_url", return_value=mock_recognizer_url):
                with patch("builtins.open", mock_open(read_data=b"fake audio")):
                    with pytest.raises(STTTransientNetworkError, match="timed out"):
                        adapter.transcribe(audio_path="/tmp/test.wav")

    # ------------------------------------------------------------------
    # Sync transcription (small file)
    # ------------------------------------------------------------------

    def test_sync_transcription_returns_result(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"alternatives": [{"transcript": "Hello world."}]}
            ]
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("httpx.Client", return_value=mock_client):
            with patch.object(adapter, "_resolve_recognizer_url", return_value="https://us-speech.googleapis.com/v2/projects/p/locations/us/recognizers/_"):
                with patch("builtins.open", mock_open(read_data=b"fake audio")):
                    result = adapter.transcribe(audio_path="/tmp/test.wav")

        assert result.transcript_text == "Hello world."
        assert result.provider == "google-chirp3"
        assert result.mode == "api"
        assert result.language == "en-US"
        assert result.segments == []

    def test_sync_transcription_uses_chirp3_model(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"alternatives": [{"transcript": "ok"}]}]}

        captured_body: dict = {}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        def _post(*args, **kwargs):
            captured_body.update(kwargs.get("json") or {})
            return mock_response

        mock_client.post.side_effect = _post

        with patch("httpx.Client", return_value=mock_client):
            with patch.object(adapter, "_resolve_recognizer_url", return_value="https://us-speech.googleapis.com/v2/projects/p/locations/us/recognizers/_"):
                with patch("builtins.open", mock_open(read_data=b"fake audio")):
                    adapter.transcribe(audio_path="/tmp/test.wav")

        assert captured_body["config"]["model"] == "chirp_3"

    # ------------------------------------------------------------------
    # Async / batch transcription (large file)
    # ------------------------------------------------------------------

    def test_batch_transcription_with_gcs_uri_polls_and_returns_result(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())

        batch_response = MagicMock()
        batch_response.status_code = 200
        batch_response.json.return_value = {"name": "projects/my-project/locations/global/operations/op123"}

        not_done_poll = MagicMock()
        not_done_poll.status_code = 200
        not_done_poll.json.return_value = {"done": False}

        done_poll = MagicMock()
        done_poll.status_code = 200
        done_poll.json.return_value = {
            "done": True,
            "response": {
                "results": {
                    "0": {
                        "inlineResult": {
                            "transcript": {
                                "results": [{"alternatives": [{"transcript": "Long lecture text."}]}]
                            }
                        }
                    }
                }
            },
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = batch_response
        mock_client.get.side_effect = [not_done_poll, done_poll]

        with patch("httpx.Client", return_value=mock_client):
            with patch("time.sleep"):
                result = adapter.transcribe(audio_path="gs://bucket/large.wav")

        assert result.transcript_text == "Long lecture text."
        assert result.provider == "google-chirp3"

    def test_local_large_audio_uses_chunked_sync_transcription(self) -> None:
        from lecture_auto.google_chirp3_adapter import (
            GoogleChirp3STTRuntimeAdapter,
            _SYNC_SIZE_THRESHOLD_BYTES,
        )

        adapter = GoogleChirp3STTRuntimeAdapter(config=self._make_config())
        large_audio = b"x" * (_SYNC_SIZE_THRESHOLD_BYTES + 1)
        chunked_result = STTResult(
            transcript_text="chunk-1 chunk-2",
            provider="google-chirp3",
            mode="api",
            language="en",
        )

        with patch("httpx.Client", return_value=MagicMock()):
            with patch("builtins.open", mock_open(read_data=large_audio)):
                with patch.object(
                    adapter,
                    "_transcribe_large_local_file",
                    return_value=chunked_result,
                ) as mocked_chunked:
                    with patch.object(adapter, "_resolve_recognizer_url", return_value="https://us-speech.googleapis.com/v2/projects/p/locations/us/recognizers/_"):
                        result = adapter.transcribe(audio_path="/tmp/large.wav")

        assert mocked_chunked.called
        assert result.transcript_text == "chunk-1 chunk-2"

    # ------------------------------------------------------------------
    # Diarization segment extraction
    # ------------------------------------------------------------------

    def test_diarization_extracts_segments_from_batch_inline_transcript(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        config = self._make_config(diarization=True)
        adapter = GoogleChirp3STTRuntimeAdapter(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "projects/my-project/locations/global/operations/op456"
        }

        done_poll = MagicMock()
        done_poll.status_code = 200
        done_poll.json.return_value = {
            "done": True,
            "response": {
                "results": {
                    "gs://bucket/diarize.wav": {
                        "inlineResult": {
                            "transcript": {
                                "results": [
                                    {
                                        "alternatives": [
                                            {
                                                "transcript": "Hello world okay great",
                                                "words": [
                                                    {"word": "Hello", "startOffset": "0.0s", "endOffset": "0.5s", "speakerLabel": "1"},
                                                    {"word": "world", "startOffset": "0.6s", "endOffset": "1.0s", "speakerLabel": "1"},
                                                    {"word": "okay", "startOffset": "1.5s", "endOffset": "2.0s", "speakerLabel": "2"},
                                                    {"word": "great", "startOffset": "2.1s", "endOffset": "2.5s", "speakerLabel": "2"},
                                                ],
                                            }
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        }

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client.get.return_value = done_poll

        with patch("httpx.Client", return_value=mock_client):
            result = adapter.transcribe(audio_path="gs://bucket/diarize.wav")

        assert len(result.segments) == 2
        assert result.segments[0].speaker == "1"
        assert "Hello" in result.segments[0].text
        assert result.segments[1].speaker == "2"
        assert "okay" in result.segments[1].text

    def test_diarization_with_local_file_requires_gcs_uri(self) -> None:
        from lecture_auto.google_chirp3_adapter import GoogleChirp3STTRuntimeAdapter

        config = self._make_config(diarization=True)
        adapter = GoogleChirp3STTRuntimeAdapter(config=config)

        with patch("httpx.Client", return_value=MagicMock()):
            with pytest.raises(STTConfigError, match="Cloud Storage URI"):
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
