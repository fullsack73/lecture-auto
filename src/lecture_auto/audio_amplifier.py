from __future__ import annotations

import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class AudioAmplificationError(RuntimeError):
    """Raised when preparing amplified audio input fails."""


class AudioFilterError(RuntimeError):
    """Raised when audio filtering/noise reduction fails."""


@contextmanager
def deepfilter_audio_input(
    *,
    audio_path: str,
    deepfilter_bin: str = "deepFilter",
    ffmpeg_bin: str = "ffmpeg",
) -> Iterator[str]:
    """Yield a noise-reduced audio path using deepfilternet."""
    original_source = Path(audio_path)
    if not original_source.exists():
        raise AudioFilterError(f"Audio file does not exist: {audio_path}")

    with tempfile.TemporaryDirectory(prefix="lecture_auto_df_") as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        
        source = tmp_dir_path / f"{original_source.stem}_src.wav"
        ffmpeg_cmd = [
            ffmpeg_bin, "-y", "-v", "warning",
            "-i", str(original_source),
            "-c:a", "pcm_s16le",
            str(source),
        ]
        completed = subprocess.run(ffmpeg_cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if completed.returncode != 0:
            raise AudioFilterError(f"Failed to convert {original_source.suffix} to WAV for filtering. Detail: {completed.stderr}")

        output_path = tmp_dir_path / source.name
        
        py_mock_script = (
            "import sys, types\n"
            "try:\n"
            "    import torch\n"
            "    import torchaudio\n"
            "    import soundfile as sf\n"
            "    class AudioMetaData:\n"
            "        def __init__(self, sr, frames, channels):\n"
            "            self.sample_rate = sr\n"
            "            self.num_frames = frames\n"
            "            self.num_channels = channels\n"
            "            self.encoding = 'PCM_S'\n"
            "            self.bits_per_sample = 16\n"
            "    def _mock_info(f, **kwargs):\n"
            "        info = sf.info(f)\n"
            "        return AudioMetaData(info.samplerate, info.frames, info.channels)\n"
            "    def _mock_load(f, frame_offset=0, num_frames=-1, **kwargs):\n"
            "        kw = {'always_2d': True, 'start': frame_offset}\n"
            "        if num_frames > 0: kw['frames'] = num_frames\n"
            "        data, sr = sf.read(f, **kw)\n"
            "        return torch.from_numpy(data.T).float(), sr\n"
            "    def _mock_save(f, src, sr, channels_first=True, **kwargs):\n"
            "        if channels_first: src = src.T\n"
            "        sf.write(f, src.numpy(), sr)\n"
            "    torchaudio.info = _mock_info\n"
            "    torchaudio.load = _mock_load\n"
            "    torchaudio.save = _mock_save\n"
            "except ImportError:\n"
            "    pass\n"
            "sys.modules['torchaudio.backend'] = types.ModuleType('torchaudio.backend')\n"
            "sys.modules['torchaudio.backend.common'] = types.ModuleType('torchaudio.backend.common')\n"
            "sys.modules['torchaudio.backend.common'].AudioMetaData = getattr(sys.modules.get(__name__), 'AudioMetaData', type('AudioMetaData', (), {}))\n"
        )
        
        sitecustomize_path = tmp_dir_path / "sitecustomize.py"
        sitecustomize_path.write_text(py_mock_script)

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{tmp_dir_path}:{env.get('PYTHONPATH', '')}".strip(":")

        command = [
            deepfilter_bin,
            str(source),
            "-o",
            str(tmp_dir_path),
        ]

        try:
            completed = subprocess.run(
                command,
                check=False,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise AudioFilterError(
                "deepFilter is required for noise reduction but was not found on PATH."
            ) from exc
        except OSError as exc:
            raise AudioFilterError(
                "Failed to start deepFilter for noise reduction."
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or "").strip()
            if len(detail) > 500:
                detail = detail[-500:]
            raise AudioFilterError(
                "deepFilter failed while reducing noise."
                + (f" Detail: {detail}" if detail else "")
            )

        if not output_path.exists():
            # Sometimes deepfilternet changes the extension but usually it keeps the same name
            # Let's search the output directory
            files = list(tmp_dir_path.glob("*"))
            if files:
                output_path = files[0]
            else:
                raise AudioFilterError(
                    "deepFilter finished but did not produce a filtered output file."
                )

        yield str(output_path)


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
