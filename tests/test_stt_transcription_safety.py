from types import SimpleNamespace
import sys

import numpy as np
import pytest

import lecture_auto.local_ai_worker as worker
from lecture_auto.stt_quality import merge_retry_segments
from lecture_auto.stt_runtime import DiarizedSegment


def test_language_detection_skips_leading_silence_without_decoding_segments(monkeypatch):
    audio = np.zeros(129 * 16000, dtype=np.float32)
    audio[99 * 16000:] = 0.1

    def timestamps(samples):
        assert np.shares_memory(samples, audio)
        assert len(samples) <= 60 * 16000
        nonzero = np.flatnonzero(samples)
        return [{"start": int(nonzero[0]), "end": len(samples)}] if len(nonzero) else []

    monkeypatch.setitem(sys.modules, "faster_whisper.vad", SimpleNamespace(get_speech_timestamps=timestamps))

    def transcribe(samples, **kwargs):
        assert np.all(samples == np.float32(0.1))
        assert len(samples) == 30 * 16000
        assert kwargs == {"vad_filter": False}

        def segments():
            raise AssertionError("Language detection must not run transcription")
            yield

        return segments(), SimpleNamespace(language="en", language_probability=0.97)

    assert worker._detect_whisper_language(SimpleNamespace(transcribe=transcribe), audio) == ("en", 0.97)


def test_uncertain_language_detection_votes_across_speech_samples(monkeypatch):
    audio = np.ones(100 * 16000, dtype=np.float32)
    monkeypatch.setitem(sys.modules, "faster_whisper.vad", SimpleNamespace(
        get_speech_timestamps=lambda samples: [{"start": 0, "end": len(samples)}],
    ))
    results = iter([("cy", 0.55), ("en", 0.65), ("en", 0.70)])
    calls = []

    def transcribe(samples, **_kwargs):
        calls.append(len(samples))
        language, probability = next(results)
        return iter(()), SimpleNamespace(language=language, language_probability=probability)

    assert worker._detect_whisper_language(SimpleNamespace(transcribe=transcribe), audio) == ("en", 0.70)
    assert calls == [30 * 16000] * 3


def test_language_detection_rejects_all_silence(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper.vad", SimpleNamespace(get_speech_timestamps=lambda _audio: []))
    with pytest.raises(ValueError, match="No speech detected"):
        worker._detect_whisper_language(object(), np.zeros(16000, dtype=np.float32))


@pytest.mark.parametrize("probability,retry_language", [(0.55, None), (0.95, "en")])
def test_worker_uses_speech_language_but_does_not_force_uncertain_language_on_retry(
    monkeypatch, probability, retry_language,
):
    audio = np.zeros(160000, dtype=np.float32)
    calls = []
    retries = []

    class Model:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, samples, **kwargs):
            assert samples is audio
            calls.append(kwargs)
            segments = [SimpleNamespace(start=start, end=end, text=text, avg_logprob=logprob)
                        for start, end, text, logprob in [
                            (0, 2, "first sentence", -0.1), (2, 4, "second sentence", -0.1),
                            (4, 6, "third sentence", -0.1), (6, 7, "bad", -1.5),
                        ]]
            return segments, SimpleNamespace(language="en", language_probability=1.0, duration=10.0)

    def retry(_runtime, _request, _windows, **kwargs):
        retries.append(kwargs)
        return []

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=Model))
    monkeypatch.setitem(sys.modules, "ctranslate2", SimpleNamespace(
        get_supported_compute_types=lambda _device: {"int8"}, get_cuda_device_count=lambda: 0,
    ))
    monkeypatch.setattr(worker, "_decode_whisper_audio", lambda _request: audio)
    monkeypatch.setattr(worker, "_detect_whisper_language", lambda _runtime, _audio: ("en", probability))
    monkeypatch.setattr(worker, "_transcribe_retry_windows", retry)
    monkeypatch.setattr(worker, "emit", lambda *_args, **_kwargs: None)
    result = worker.whisper({"model": "medium", "quality_retry_enabled": True})
    assert calls[0]["language"] == "en"
    assert calls[0]["vad_filter"] is False
    assert retries[0]["language"] == retry_language
    assert result["metadata"]["language_probability"] == probability
    assert result["metadata"]["language_detection_source"] == "speech_vad"


def test_retry_crops_audio_and_restores_segment_and_word_times(monkeypatch):
    audio = np.arange(20 * 16000, dtype=np.float32)

    def transcribe(samples, **kwargs):
        np.testing.assert_array_equal(samples, audio[10 * 16000:12 * 16000])
        assert "clip_timestamps" not in kwargs
        assert "language" not in kwargs
        assert kwargs["vad_filter"] is True
        segment = SimpleNamespace(start=0.5, end=1.5, text="speech", words=[
            SimpleNamespace(start=0.5, end=1.5, word="speech", probability=0.9),
        ])
        return [segment], SimpleNamespace(language="en")

    monkeypatch.setattr(worker, "emit", lambda *_args, **_kwargs: None)
    result = worker._transcribe_retry_windows(SimpleNamespace(transcribe=transcribe), {}, [(10, 12)],
                                               audio=audio, language=None)
    assert (result[0]["start_time"], result[0]["end_time"]) == (10.5, 11.5)
    assert (result[0]["words"][0]["start_time"], result[0]["words"][0]["end_time"]) == (10.5, 11.5)


@pytest.mark.parametrize("candidate", [
    [],
    [DiarizedSegment("S", 0, 10, "다른 전사 결과도 신뢰도가 낮은 상태입니다", avg_logprob=-1.5)],
    [DiarizedSegment("S", 0, 10, "원문과 신뢰도가 같은 결과는 원문을 교체하지 않습니다", avg_logprob=-0.5)],
    [DiarizedSegment("S", 0, 10, "무음일 확률이 높은 구간에서 만들어진 문장입니다", avg_logprob=-0.1, no_speech_prob=0.95)],
    [DiarizedSegment("S", 0, 10, "감사합니다", avg_logprob=-0.1)],
    [DiarizedSegment("S", 0, 10, "반복 반복 반복 반복", avg_logprob=-0.1)],
    [DiarizedSegment("S", 0, 30, "범위를 넘어온 전사 결과를 그대로 사용하면 안 됩니다", avg_logprob=-0.1)],
])
def test_retry_preserves_original_when_candidate_is_empty_worse_short_repeated_or_outside_window(candidate):
    primary = [DiarizedSegment("S", 0, 10, "출석 현황을 확인하고 오늘 강의 내용을 설명하겠습니다", avg_logprob=-0.5)]
    assert merge_retry_segments(primary, candidate, [(0, 10)]) == primary


def test_retry_does_not_erase_an_uncovered_primary_segment():
    primary = [
        DiarizedSegment("S", 0, 3, "첫 번째 문장", avg_logprob=-1.2),
        DiarizedSegment("S", 5, 8, "두 번째 문장", avg_logprob=-1.2),
        DiarizedSegment("S", 20, 23, "다른 구간 문장", avg_logprob=-1.2),
    ]
    retry = [
        DiarizedSegment("S", 0, 3, "첫 번째 내용을 길게 바꾼 문장", avg_logprob=-0.1),
        DiarizedSegment("S", 20, 23, "다른 구간 교정", avg_logprob=-0.1),
    ]
    result = merge_retry_segments(primary, retry, [(0, 10), (20, 23)])
    assert [segment.text for segment in result] == ["첫 번째 문장", "두 번째 문장", "다른 구간 교정"]


def test_retry_allows_sample_rounding_at_window_boundary():
    primary = [DiarizedSegment("S", 0.3, 4, "원문 발화", avg_logprob=-1.2)]
    retry = [DiarizedSegment("S", 0.3, 4, "교정 발화", avg_logprob=-0.1)]
    assert merge_retry_segments(primary, retry, [(0.1 + 0.2, 4)]) == retry
