from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from lecture_auto.audio_amplifier import AudioAmplificationError, amplified_audio_input


def test_amplified_audio_input_gain_one_is_noop(tmp_path: Path) -> None:
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")

    with patch("lecture_auto.audio_amplifier.subprocess.run") as run_mock:
        with amplified_audio_input(audio_path=str(source), use_dynaudnorm=False) as audio_path:
            assert audio_path == str(source)

    run_mock.assert_not_called()


def test_amplified_audio_input_raises_when_ffmpeg_reports_success_without_output(tmp_path: Path) -> None:
    source = tmp_path / "sample.wav"
    source.write_bytes(b"wav")

    with patch("lecture_auto.audio_amplifier.subprocess.run") as run_mock:
        run_mock.return_value.returncode = 0
        run_mock.return_value.stderr = ""

        try:
            with amplified_audio_input(audio_path=str(source), use_dynaudnorm=True):
                pass
        except AudioAmplificationError as exc:
            assert "did not produce" in str(exc)
        else:
            raise AssertionError("Expected AudioAmplificationError to be raised")
