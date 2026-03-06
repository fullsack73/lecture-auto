# Manual Real-Device Validation Procedure

## Scope
Manual validation for Roadmap item 1 residual capture flow with real local audio device.

## Prerequisites
- macOS with audio capture permission available for terminal and Python process
- `ffmpeg` installed and available on `PATH`
- Python environment initialized for project execution
- Writable local folders: `recordings/`, `config/`

## Validation Steps

1. Create a new session
- Command: `session create --session-id session-manual-001 --date 2026-03-06`
- Expected:
  - Status `idle`
  - Metadata persisted to local JSON

2. Start capture on real device
- Command: `capture start session-manual-001`
- Expected:
  - Command succeeds with non-error status
  - Metadata status transitions to `recording`
  - `audio_file_path` follows `recordings/session-manual-001.*`

3. Record for 10-20 seconds
- Action: Play system audio while capture is active
- Expected:
  - Capture process remains active

4. Stop capture
- Command: `capture stop session-manual-001`
- Expected:
  - Status transitions to `completed`
  - Audio artifact exists at persisted path

5. Verify history/detail
- Commands:
  - `session history`
  - `session detail session-manual-001`
- Expected:
  - Session appears in history with final status
  - Detail includes path, status, and lifecycle timestamps

## Failure Validation

1. Dependency failure
- Trigger: Temporarily hide `ffmpeg` from `PATH`
- Command: `capture start session-manual-001`
- Expected:
  - Non-zero exit
  - Actionable dependency guidance

2. Device/permission failure
- Trigger: Revoke microphone/system-audio permissions
- Command: `capture start session-manual-001`
- Expected:
  - Non-zero exit
  - Actionable device/permission guidance

3. Interrupted capture
- Trigger: Force-terminate capture process externally while running
- Command: `capture stop session-manual-001`
- Expected:
  - Failure is surfaced clearly
  - Metadata remains internally consistent (no corrupted JSON)

## Troubleshooting
- If `ffmpeg` is missing: reinstall and verify via `ffmpeg -version`
- If permission is denied: re-enable terminal/app permissions in macOS privacy settings
- If no device is detected: verify audio input/output routing and retry
- If metadata write fails: check disk space and file permissions under project folder
