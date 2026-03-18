from __future__ import annotations

import subprocess
import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class CaptureRuntimeError(RuntimeError):
    """Base class for runtime capture errors."""


class CaptureDependencyError(CaptureRuntimeError):
    """Raised when runtime dependencies are missing."""


class CapturePermissionError(CaptureRuntimeError):
    """Raised when OS denies audio capture permission."""


class CaptureDeviceError(CaptureRuntimeError):
    """Raised when an audio device is unavailable."""


class CaptureInterruptedError(CaptureRuntimeError):
    """Raised when capture session is interrupted."""


@dataclass
class CaptureHandle:
    session_id: str
    output_path: str
    process_id: int
    backend: str


class CaptureRuntimeAdapter(Protocol):
    def start_capture(self, session_id: str, output_path: str) -> CaptureHandle:
        ...

    def stop_capture(
        self,
        session_id: str,
        *,
        interrupted: bool = False,
        process_id: int | None = None,
    ) -> None:
        ...


class NoopCaptureRuntimeAdapter:
    """Deterministic runtime adapter used by default for non-device environments."""

    def __init__(self) -> None:
        self._next_pid = 1000
        self._active: dict[str, CaptureHandle] = {}

    def start_capture(self, session_id: str, output_path: str) -> CaptureHandle:
        if session_id in self._active:
            raise CaptureRuntimeError(f"Session '{session_id}' is already capturing")

        self._next_pid += 1
        handle = CaptureHandle(
            session_id=session_id,
            output_path=output_path,
            process_id=self._next_pid,
            backend="noop",
        )
        self._active[session_id] = handle
        return handle

    def stop_capture(
        self,
        session_id: str,
        *,
        interrupted: bool = False,
        process_id: int | None = None,
    ) -> None:
        if session_id not in self._active:
            raise CaptureRuntimeError(f"No active capture for session '{session_id}'")

        self._active.pop(session_id)


class FFmpegCaptureRuntimeAdapter:
    """Real runtime adapter that starts/stops FFmpeg-based audio capture."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", capture_source: str = "microphone") -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.capture_source = capture_source
        self._processes: dict[str, subprocess.Popen[bytes]] = {}

    def _resolve_device_index(self) -> str:
        """Runs ffmpeg to list AVFoundation devices and returns the appropriate device index."""
        # Note: on Linux/Windows, this approach will differ. For macOS:
        try:
            result = subprocess.run(
                [self.ffmpeg_bin, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            output = result.stderr  # FFmpeg prints device list to stderr
        except FileNotFoundError as exc:
            raise CaptureDependencyError("FFmpeg is not installed or not on PATH") from exc

        # Extract only the audio devices section
        audio_section = False
        devices = []
        for line in output.splitlines():
            if "AVFoundation audio devices:" in line:
                audio_section = True
                continue
            if "AVFoundation video devices:" in line:
                audio_section = False
                continue
            
            if audio_section and "[" in line and "]" in line:
                try:
                    # Format is typically: [AVFoundation input device @ 0x...] [0] Built-in Microphone
                    idx_start = line.rfind("[") + 1
                    idx_end = line.rfind("]")
                    if idx_start > 0 and idx_end > idx_start:
                        idx_str = line[idx_start:idx_end].strip()
                        name = line[idx_end + 1:].strip()
                        devices.append((idx_str, name.lower()))
                except Exception:
                    continue

        if self.capture_source == "system_audio":
            keywords = ["blackhole", "steam streaming speakers", "soundflower", "loopback", "swb"]
            for idx, name in devices:
                if any(kw in name for kw in keywords):
                    return idx
            raise CaptureDeviceError(
                "No system audio loopback device found. Please install a virtual audio driver like BlackHole."
            )
        else:
            # Default to microphone
            keywords = ["microphone", "built-in", "mic"]
            for idx, name in devices:
                if any(kw in name for kw in keywords):
                    return idx
            # Fallback to the first available audio device
            if devices:
                return devices[0][0]
            
            return "0"  # Absolute fallback if we couldn't parse any devices

    def start_capture(self, session_id: str, output_path: str) -> CaptureHandle:
        if session_id in self._processes:
            raise CaptureRuntimeError(f"Session '{session_id}' is already capturing")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        device_idx = self._resolve_device_index()

        command = [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "avfoundation",
            "-i",
            f":{device_idx}",
            output_path,
        ]

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except PermissionError as exc:
            raise CapturePermissionError("OS permissions denied capture startup") from exc
        except OSError as exc:
            raise CaptureDeviceError("Unable to open system audio device") from exc

        self._processes[session_id] = process
        return CaptureHandle(
            session_id=session_id,
            output_path=output_path,
            process_id=process.pid,
            backend="ffmpeg",
        )

    def stop_capture(
        self,
        session_id: str,
        *,
        interrupted: bool = False,
        process_id: int | None = None,
    ) -> None:
        process = self._processes.pop(session_id, None)
        if process is None and process_id is not None:
            self._stop_by_pid(process_id=process_id, interrupted=interrupted)
            return
        if process is None:
            raise CaptureRuntimeError(f"No active capture for session '{session_id}'")

        if interrupted:
            process.kill()
            return

        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            raise CaptureRuntimeError("Capture process did not stop gracefully")

    def _stop_by_pid(self, *, process_id: int, interrupted: bool) -> None:
        try:
            sig = signal.SIGKILL if interrupted else signal.SIGTERM
            os.kill(process_id, sig)
        except ProcessLookupError:
            return
        except PermissionError as exc:
            raise CapturePermissionError("OS permissions denied capture shutdown") from exc
        except OSError as exc:
            raise CaptureRuntimeError("Capture process stop failed") from exc

        if interrupted:
            return

        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                os.kill(process_id, 0)
            except ProcessLookupError:
                return
            except OSError:
                return
            time.sleep(0.1)

        try:
            os.kill(process_id, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError as exc:
            raise CaptureRuntimeError("Capture process did not stop gracefully") from exc
