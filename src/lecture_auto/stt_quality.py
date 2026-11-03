from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from lecture_auto.stt_runtime import DiarizedSegment


KOREAN_LECTURE_THRESHOLDS = {
    "avg_logprob": -1.10,
    "compression_ratio": 2.45,
    "no_speech_probability": 0.70,
    "characters_per_second": 13.0,
}


@dataclass(frozen=True)
class SuspectSTTSegment:
    start_time: float
    end_time: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "reasons": list(self.reasons),
        }


def assess_stt_quality(
    segments: Sequence[DiarizedSegment],
    *,
    logprob_threshold: float = KOREAN_LECTURE_THRESHOLDS["avg_logprob"],
    compression_ratio_threshold: float = KOREAN_LECTURE_THRESHOLDS[
        "compression_ratio"
    ],
    no_speech_threshold: float = KOREAN_LECTURE_THRESHOLDS[
        "no_speech_probability"
    ],
    max_characters_per_second: float = KOREAN_LECTURE_THRESHOLDS[
        "characters_per_second"
    ],
) -> dict[str, object]:
    suspects: list[SuspectSTTSegment] = []
    reason_counts: dict[str, int] = {}

    for segment in segments:
        reasons: list[str] = []
        text = segment.text.strip()
        duration = max(0.0, segment.end_time - segment.start_time)
        if segment.avg_logprob is not None and segment.avg_logprob < logprob_threshold:
            reasons.append("low_logprob")
        if (
            segment.compression_ratio is not None
            and segment.compression_ratio > compression_ratio_threshold
        ):
            reasons.append("high_compression_ratio")
        if (
            text
            and segment.no_speech_prob is not None
            and segment.no_speech_prob > no_speech_threshold
        ):
            reasons.append("speech_on_high_no_speech_probability")
        if duration > 0 and len(_normalized_characters(text)) / duration > max_characters_per_second:
            reasons.append("excessive_character_rate")
        if _has_repetition_loop(text):
            reasons.append("repetition_loop")

        if reasons:
            suspect = SuspectSTTSegment(
                start_time=segment.start_time,
                end_time=segment.end_time,
                reasons=tuple(reasons),
            )
            suspects.append(suspect)
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

    suspect_duration = sum(
        max(0.0, suspect.end_time - suspect.start_time) for suspect in suspects
    )
    total_duration = max(
        (segment.end_time for segment in segments),
        default=0.0,
    )
    return {
        "segment_count": len(segments),
        "suspect_segment_count": len(suspects),
        "suspect_duration_seconds": suspect_duration,
        "suspect_duration_ratio": (
            min(1.0, suspect_duration / total_duration) if total_duration else 0.0
        ),
        "reason_counts": reason_counts,
        "suspect_segments": [suspect.to_dict() for suspect in suspects],
        "thresholds": {
            "avg_logprob": logprob_threshold,
            "compression_ratio": compression_ratio_threshold,
            "no_speech_probability": no_speech_threshold,
            "characters_per_second": max_characters_per_second,
        },
        "threshold_profile": "ko-lecture-v1",
    }


def build_retry_windows(
    segments: Sequence[DiarizedSegment],
    quality: dict[str, object],
    *,
    context_seconds: float = 1.5,
    maximum_windows: int = 8,
    maximum_total_seconds: float = 120.0,
) -> list[tuple[float, float]]:
    """Expand and merge suspect ranges while enforcing hard retry caps."""
    if maximum_windows < 1 or maximum_total_seconds <= 0:
        return []
    total_duration = max((segment.end_time for segment in segments), default=0.0)
    raw = quality.get("suspect_segments")
    candidates: list[tuple[float, float]] = []
    if isinstance(raw, list):
        for value in raw:
            if not isinstance(value, dict):
                continue
            start = max(0.0, float(value.get("start_time") or 0) - context_seconds)
            end = min(
                total_duration,
                float(value.get("end_time") or 0) + context_seconds,
            )
            if end > start:
                candidates.append((start, end))

    merged: list[tuple[float, float]] = []
    for start, end in sorted(candidates):
        if merged and start <= merged[-1][1] + 0.25:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    bounded: list[tuple[float, float]] = []
    remaining = maximum_total_seconds
    for start, end in merged[:maximum_windows]:
        duration = min(end - start, remaining)
        if duration <= 0:
            break
        bounded.append((start, start + duration))
        remaining -= duration
    return bounded


def should_recommend_full_retry(
    quality: dict[str, object],
    *,
    suspect_duration_ratio_threshold: float = 0.60,
    suspect_segment_ratio_threshold: float = 0.60,
) -> bool:
    segment_count = int(quality.get("segment_count") or 0)
    suspect_count = int(quality.get("suspect_segment_count") or 0)
    duration_ratio = float(quality.get("suspect_duration_ratio") or 0)
    segment_ratio = suspect_count / segment_count if segment_count else 0.0
    return (
        duration_ratio >= suspect_duration_ratio_threshold
        or segment_ratio >= suspect_segment_ratio_threshold
    )


def merge_retry_segments(
    primary: Sequence[DiarizedSegment],
    retry: Sequence[DiarizedSegment],
    windows: Sequence[tuple[float, float]],
) -> list[DiarizedSegment]:
    """Replace primary segments inside retry windows and keep stable timestamp order."""
    if not retry or not windows:
        return list(primary)

    def in_window(segment: DiarizedSegment, start: float, end: float) -> bool:
        midpoint = (segment.start_time + segment.end_time) / 2
        return start <= midpoint <= end

    replaced: set[int] = set()
    accepted_retry: list[DiarizedSegment] = []
    for start, end in windows:
        indices = [
            index for index, segment in enumerate(primary)
            if in_window(segment, start, end)
        ]
        original = [primary[index] for index in indices]
        candidate = [
            segment for segment in retry
            if in_window(segment, start, end) and segment.text.strip()
        ]
        if not _retry_is_better(original, candidate, start, end):
            continue
        replaced.update(indices)
        accepted_retry.extend(candidate)
    kept = [segment for index, segment in enumerate(primary) if index not in replaced]
    combined = sorted(
        [*kept, *accepted_retry],
        key=lambda segment: (segment.start_time, segment.end_time),
    )
    deduplicated: list[DiarizedSegment] = []
    for segment in combined:
        if (
            deduplicated
            and segment.text.strip() == deduplicated[-1].text.strip()
            and segment.start_time < deduplicated[-1].end_time
        ):
            if _segment_quality_score(segment) > _segment_quality_score(deduplicated[-1]):
                deduplicated[-1] = segment
            continue
        deduplicated.append(segment)
    return deduplicated


def _retry_is_better(
    primary: Sequence[DiarizedSegment],
    retry: Sequence[DiarizedSegment],
    start: float,
    end: float,
) -> bool:
    if not primary or not retry or assess_stt_quality(retry)["suspect_segment_count"]:
        return False
    if any(
        segment.start_time < start - 1 / 16000
        or segment.end_time > end + 1 / 16000
        or segment.end_time <= segment.start_time
        for segment in retry
    ):
        return False
    if any(
        not any(
            candidate.end_time > segment.start_time and candidate.start_time < segment.end_time
            for candidate in retry
        )
        for segment in primary if segment.text.strip()
    ):
        return False
    original_length = sum(len(_normalized_characters(segment.text)) for segment in primary)
    retry_length = sum(len(_normalized_characters(segment.text)) for segment in retry)
    # A confident short hallucination must not erase a much longer passage.
    if retry_length < original_length * 0.5:
        return False

    def score(segments: Sequence[DiarizedSegment]) -> float:
        durations = [max(0.01, segment.end_time - segment.start_time) for segment in segments]
        return sum(
            _segment_quality_score(segment) * duration
            for segment, duration in zip(segments, durations)
        ) / sum(durations)

    return score(retry) > score(primary)


def _segment_quality_score(segment: DiarizedSegment) -> float:
    logprob = segment.avg_logprob if segment.avg_logprob is not None else -2.0
    no_speech = segment.no_speech_prob if segment.no_speech_prob is not None else 0.5
    compression_penalty = max(
        0.0,
        (segment.compression_ratio or 0.0) - KOREAN_LECTURE_THRESHOLDS[
            "compression_ratio"
        ],
    )
    return logprob - no_speech - compression_penalty


def _normalized_characters(text: str) -> str:
    return "".join(re.findall(r"[\w가-힣]", text.lower(), flags=re.UNICODE))


def _has_repetition_loop(text: str) -> bool:
    words = re.findall(r"[\w가-힣]+", text.lower(), flags=re.UNICODE)
    if not words:
        return False

    run = 1
    for previous, current in zip(words, words[1:]):
        if current == previous:
            run += 1
            if run >= 4:
                return True
        else:
            run = 1

    for size in range(2, min(6, len(words) // 2 + 1)):
        for end in range(size * 2, len(words) + 1):
            if words[end - size * 2 : end - size] == words[end - size : end]:
                return True
    return False
