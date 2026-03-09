"""
Interactive TUI for lecture-auto.

Launched automatically when `lecture-auto` is run with no subcommand.
Uses questionary for arrow-key / enter navigation.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import questionary
import typer

from lecture_auto.cli_output import format_command_error, format_command_output
from lecture_auto.session_service import SessionCommandError

# ── Styling ────────────────────────────────────────────────────────────────────
STYLE = questionary.Style(
    [
        ("qmark", "fg:#00bcd4 bold"),
        ("question", "bold"),
        ("answer", "fg:#00bcd4 bold"),
        ("pointer", "fg:#00bcd4 bold"),
        ("highlighted", "fg:#00bcd4 bold"),
        ("selected", "fg:#00bcd4"),
        ("separator", "fg:#6c757d"),
        ("instruction", "fg:#6c757d"),
        ("text", ""),
        ("disabled", "fg:#6c757d italic"),
    ]
)

SEPARATOR = questionary.Separator("─" * 40)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _echo_result(result) -> None:
    typer.echo(format_command_output(result, as_json=False))


def _echo_error(command: str, exc: SessionCommandError) -> None:
    typer.echo(format_command_error(command, exc, as_json=False))


def _ask(message: str, default: str = "") -> str | None:
    """Single-line text prompt. Returns None if user cancels (Ctrl+C)."""
    return questionary.text(message, default=default, style=STYLE).ask()


def _select(message: str, choices: list) -> str | None:
    """Arrow-key selection. Returns None if user cancels."""
    return questionary.select(message, choices=choices, style=STYLE).ask()


def _select_session(service, prompt: str = "Select a session") -> str | None:
    """Show session list and let user pick one by title / id."""
    try:
        result = service.session_history()
    except SessionCommandError as exc:
        _echo_error("session history", exc)
        return None

    sessions = result.payload.get("sessions", [])
    if not sessions:
        typer.echo("No sessions found. Create a session first.")
        return None

    choices = []
    for s in sessions:
        label = f"[{s['date']}] {s['title'] or '(no title)'} ({s['session_id']}) — {s['status']}"
        choices.append(questionary.Choice(title=label, value=s["session_id"]))
    choices.append(questionary.Separator())
    choices.append(questionary.Choice(title="← Back", value="__back__"))

    choice = questionary.select(prompt, choices=choices, style=STYLE).ask()
    if choice in (None, "__back__"):
        return None
    return choice


# ── Config helpers (mirrors cli.py logic without typer context) ─────────────

def _get_global_config_path() -> Path:
    return Path.home() / ".lecture_auto" / "config.json"


def _load_config() -> dict:
    path = _get_global_config_path()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(data: dict) -> None:
    path = _get_global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ── Sub-menus ──────────────────────────────────────────────────────────────────

def _menu_session(service) -> None:
    while True:
        choice = _select(
            "Session",
            [
                questionary.Choice("✚  Create new session", "create"),
                questionary.Choice("📋  View history", "history"),
                questionary.Choice("🔍  View session detail", "detail"),
                SEPARATOR,
                questionary.Choice("← Back", "__back__"),
            ],
        )

        if choice in (None, "__back__"):
            return

        if choice == "history":
            try:
                result = service.session_history()
                _echo_result(result)
            except SessionCommandError as exc:
                _echo_error("session history", exc)

        elif choice == "detail":
            session_id = _select_session(service, "Select session to view")
            if session_id is None:
                continue
            try:
                result = service.session_detail(session_id=session_id)
                _echo_result(result)
            except SessionCommandError as exc:
                _echo_error("session detail", exc)

        elif choice == "create":
            session_id = _ask("Session ID (e.g. cs101-2026-03-09)")
            if not session_id:
                continue
            date = _ask("Date (YYYY-MM-DD)", default="2026-03-09")
            if not date:
                continue
            title = _ask("Title (optional)")
            course = _ask("Course (optional)")
            try:
                result = service.session_create(
                    session_id=session_id,
                    date=date,
                    title=title or None,
                    course=course or None,
                )
                _echo_result(result)
            except SessionCommandError as exc:
                _echo_error("session create", exc)

        typer.echo()  # breathing room after each action


def _menu_capture(service) -> None:
    while True:
        choice = _select(
            "Capture",
            [
                questionary.Choice("▶  Start capture", "start"),
                questionary.Choice("■  Stop capture", "stop"),
                SEPARATOR,
                questionary.Choice("← Back", "__back__"),
            ],
        )

        if choice in (None, "__back__"):
            return

        if choice == "start":
            session_id = _select_session(service, "Select session to record")
            if session_id is None:
                continue
            try:
                result = service.capture_start(session_id=session_id)
                _echo_result(result)
            except SessionCommandError as exc:
                _echo_error("capture start", exc)

        elif choice == "stop":
            session_id = _select_session(service, "Select session to stop")
            if session_id is None:
                continue
            try:
                result = service.capture_stop(session_id=session_id, success=True)
                _echo_result(result)
            except SessionCommandError as exc:
                _echo_error("capture stop", exc)

        typer.echo()


def _menu_transcription(service) -> None:
    while True:
        choice = _select(
            "Transcription",
            [
                questionary.Choice("📝  Run transcription", "run"),
                SEPARATOR,
                questionary.Choice("← Back", "__back__"),
            ],
        )

        if choice in (None, "__back__"):
            return

        if choice == "run":
            session_id = _select_session(service, "Select session to transcribe")
            if session_id is None:
                continue
            typer.echo("Running transcription… (this may take a while)")
            try:
                result = service.transcribe_session(session_id=session_id)
                _echo_result(result)
            except SessionCommandError as exc:
                _echo_error("transcription run", exc)

        typer.echo()


def _menu_summarize(service) -> None:
    session_id = _select_session(service, "Select session to summarize")
    if session_id is None:
        return

    template = _ask("Template name (leave blank for default)")
    preview_choice = _select(
        "Save or preview?",
        [
            questionary.Choice("Save to file", False),
            questionary.Choice("Preview only (no save)", True),
        ],
    )
    if preview_choice is None:
        return

    typer.echo("Generating summary…")
    try:
        result = service.summarize_session(
            session_reference=session_id,
            template_name=template or None,
            preview=preview_choice,
        )
        _echo_result(result)
    except SessionCommandError as exc:
        _echo_error("summarize", exc)
    typer.echo()


def _menu_config() -> None:
    while True:
        choice = _select(
            "Config",
            [
                questionary.Choice("👁  Show current config", "show"),
                questionary.Choice("✏  Set values", "set"),
                SEPARATOR,
                questionary.Choice("← Back", "__back__"),
            ],
        )

        if choice in (None, "__back__"):
            return

        if choice == "show":
            data = _load_config()
            if data:
                typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                typer.echo("No global configuration found.")

        elif choice == "set":
            data = _load_config()
            updated = False

            fields = [
                ("workspace", "Workspace directory (leave blank to skip)"),
                ("stt_language", "STT language (e.g. korean, leave blank to skip)"),
                ("llm_language", "LLM language (e.g. korean, leave blank to skip)"),
                ("stt_api_provider", "STT API provider (e.g. deepgram, leave blank to skip)"),
                ("stt_api_key", "STT API key (leave blank to skip)"),
                ("gemini_api_key", "Gemini API key (leave blank to skip)"),
            ]
            for key, prompt in fields:
                value = _ask(prompt, default=data.get(key, ""))
                if value is None:  # Ctrl+C
                    break
                if value.strip():
                    data[key] = value.strip() if key != "workspace" else str(
                        Path(value.strip()).expanduser().resolve()
                    )
                    updated = True

            if updated:
                _save_config(data)
                typer.echo("✓ Config saved.")
            else:
                typer.echo("No changes made.")

        typer.echo()


# ── Entry Point ────────────────────────────────────────────────────────────────

def run_tui(service) -> None:
    """Launch the interactive TUI main loop."""
    typer.echo("\n🎓  lecture-auto  — interactive mode  (Ctrl+C to exit)\n")

    while True:
        choice = _select(
            "What would you like to do?",
            [
                questionary.Choice("📁  Session", "session"),
                questionary.Choice("🎙  Capture", "capture"),
                questionary.Choice("📝  Transcription", "transcription"),
                questionary.Choice("✨  Summarize", "summarize"),
                questionary.Choice("⚙   Config", "config"),
                SEPARATOR,
                questionary.Choice("🚪  Exit", "exit"),
            ],
        )

        if choice in (None, "exit"):
            typer.echo("Bye! 👋")
            break

        typer.echo()

        try:
            if choice == "session":
                _menu_session(service)
            elif choice == "capture":
                _menu_capture(service)
            elif choice == "transcription":
                _menu_transcription(service)
            elif choice == "summarize":
                _menu_summarize(service)
            elif choice == "config":
                _menu_config()
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nReturning to main menu…\n")
            continue
