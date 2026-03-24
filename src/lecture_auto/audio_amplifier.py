from __future__ import annotations

import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class AudioAmplificationError(RuntimeError):
    """Raised when preparing amplified audio input fails."""


@contextmanager
def amplified_audio_input(
    *,
    audio_path: str,
    gain_multiplier: float,
    ffmpeg_bin: str = "ffmpeg",
) -> Iterator[str]:
    """Yield an audio path suitable for STT, amplifying input when needed.

    When gain is 1.0, this yields the original path with no side effects.
    """
    if gain_multiplier <= 1.0:
        yield audio_path
        return

    source = Path(audio_path)
    if not source.exists():
        raise AudioAmplificationError(f"Audio file does not exist: {audio_path}")

    with tempfile.TemporaryDirectory(prefix="lecture_auto_amp_") as tmp_dir:
        output_path = Path(tmp_dir) / "amplified.wav"
        command = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source),
            "-filter:a",
            f"volume={gain_multiplier}",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]

        try:
            completed = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise AudioAmplificationError(
                "FFmpeg is required for audio amplification but was not found on PATH."
            ) from exc
        except OSError as exc:
            raise AudioAmplificationError(
                "Failed to start FFmpeg for audio amplification."
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or "").strip()
            if len(detail) > 500:
                detail = detail[-500:]
            raise AudioAmplificationError(
                "FFmpeg failed while amplifying audio input."
                + (f" Detail: {detail}" if detail else "")
            )

        if not output_path.exists():
            raise AudioAmplificationError(
                "FFmpeg finished but did not produce an amplified output file."
            )

        yield str(output_path)
