from __future__ import annotations

import json
from typing import Any

from lecture_auto.session_service import CommandResult, SessionCommandError


def format_command_output(result: CommandResult, *, as_json: bool = False) -> str:
    if as_json:
        return _json_line(
            {
                "ok": True,
                "command": result.command,
                "payload": result.payload,
                "message": result.message,
            }
        )

    if result.command == "session create":
        return (
            f"Session Created\n"
            f"- Session ID: {result.payload['session_id']}\n"
            f"- Date: {result.payload['date']}\n"
            f"- Status: {result.payload['status']}\n"
            f"- Next: Run 'capture start {result.payload['session_id']}'"
        )

    if result.command == "capture start":
        return (
            f"Capture Started\n"
            f"- Session ID: {result.payload['session_id']}\n"
            f"- Audio Path: {result.payload['audio_file_path']}\n"
            "- Next: Run 'capture stop <session_id>' when class ends"
        )

    if result.command == "capture stop":
        return (
            f"Capture Stopped\n"
            f"- Session ID: {result.payload['session_id']}\n"
            f"- Final Status: {result.payload['status']}\n"
            "- Next: Run 'session detail <session_id>' to review metadata"
        )

    if result.command in {"audio import", "audio import retry", "audio import cancel"}:
        return _render_import_text(result.command, result.payload)

    if result.command == "session history":
        return _render_history_text(result.payload)

    if result.command == "session detail":
        return _render_detail_text(result.payload)

    return result.message


def format_command_error(
    command: str,
    error: SessionCommandError,
    *,
    as_json: bool = False,
) -> str:
    if as_json:
        return _json_line(
            {
                "ok": False,
                "command": command,
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "guidance": error.guidance,
                    "exit_code": error.exit_code,
                },
            }
        )

    return (
        f"Command Failed\n"
        f"- Command: {command}\n"
        f"- Error: {error.message}\n"
        f"- Next Action: {error.guidance}\n"
        f"- Exit Code: {error.exit_code}"
    )


def _render_history_text(payload: dict[str, Any]) -> str:
    sessions = payload.get("sessions", [])
    lines = [f"Session History ({payload.get('count', 0)} total)"]
    if not sessions:
        lines.append("- No sessions found.")
        lines.append("- Next: Run 'session create' to create your first session")
        return "\n".join(lines)

    for row in sessions:
        title = row.get("title") or "(pending title)"
        course = row.get("course") or "(pending course)"
        lines.append(
            f"- {row['date']} | {row['session_id']} | {row['status']} | {course} | {title}"
        )
    lines.append("- Next: Run 'session detail <session_id>' for full details")
    return "\n".join(lines)


def _render_detail_text(payload: dict[str, Any]) -> str:
    lines = ["Session Detail"]
    lines.append(f"- Session ID: {payload['session_id']}")
    lines.append(f"- Date: {payload['date']}")
    lines.append(f"- Title: {payload.get('title')}")
    lines.append(f"- Course: {payload.get('course')}")
    lines.append(f"- Status: {payload['status']}")
    lines.append(f"- Audio Path: {payload.get('audio_file_path')}")
    lines.append(f"- Naming Pending: {payload['naming_pending']}")
    lines.append(f"- Timestamps: {payload['timestamps']}")
    return "\n".join(lines)


def _render_import_text(command: str, payload: dict[str, Any]) -> str:
    progress = payload.get("progress") or {}
    header = {
        "audio import": "Audio Import Completed",
        "audio import retry": "Audio Import Retry Completed",
        "audio import cancel": "Audio Import Canceled",
    }.get(command, "Audio Import")

    lines = [header]
    lines.append(f"- Session ID: {payload['session_id']}")
    lines.append(f"- Audio Path: {payload.get('audio_file_path')}")
    lines.append(f"- Current Stage: {progress.get('current_stage')}")
    lines.append(f"- Final Status: {progress.get('final_status')}")
    lines.append(f"- Started At: {progress.get('started_at')}")
    lines.append(f"- Ended At: {progress.get('ended_at')}")
    lines.append(
        f"- Attempt: {progress.get('attempt')}/{progress.get('retry_limit')}"
    )
    lines.append("- Next: Run 'session detail <session_id>' to review import metadata")
    return "\n".join(lines)


def _json_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
