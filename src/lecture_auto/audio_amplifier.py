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
    use_dynaudnorm: bool = False,
    dynaudnorm_f: int | None = None,
    dynaudnorm_g: int | None = None,
    ffmpeg_bin: str = "ffmpeg",
) -> Iterator[str]:
    """Yield an audio path suitable for STT, amplifying input when needed.

    When use_dynaudnorm is False, this yields the original path with no side effects.
    """
    if not use_dynaudnorm:
        yield audio_path
        return

    source = Path(audio_path)
    if not source.exists():
        raise AudioAmplificationError(f"Audio file does not exist: {audio_path}")

    filter_opts = []
    if dynaudnorm_f is not None:
        filter_opts.append(f"f={dynaudnorm_f}")
    if dynaudnorm_g is not None:
        filter_opts.append(f"g={dynaudnorm_g}")
    
    dynaudnorm_str = "dynaudnorm"
    if filter_opts:
        dynaudnorm_str += "=" + ":".join(filter_opts)

    with tempfile.TemporaryDirectory(prefix="lecture_auto_amp_") as tmp_dir:
        output_path = Path(tmp_dir) / "amplified.wav"
        command = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source),
            "-filter:a",
            dynaudnorm_str,
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
