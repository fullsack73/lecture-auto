from __future__ import annotations

import os
from pathlib import Path

import typer

from lecture_auto.capture_runtime import FFmpegCaptureRuntimeAdapter
from lecture_auto.cli_output import format_command_error, format_command_output
from lecture_auto.llm_adapter import GeminiLLMAdapter, LLMConfigError
from lecture_auto.llm_config import LLMConfig
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService
from lecture_auto.stt_config import STTConfig

app = typer.Typer(help="Lecture automation CLI")
session_app = typer.Typer(help="Session commands")
capture_app = typer.Typer(help="Capture commands")
transcription_app = typer.Typer(help="Transcription commands")


@app.callback()
def app_callback(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Custom workspace directory (default: ~/.lecture_auto)",
        envvar="LECTURE_AUTO_WORKSPACE",
    ),
) -> None:
    if workspace:
        os.environ["LECTURE_AUTO_WORKSPACE"] = str(Path(workspace).expanduser().resolve())


def _build_service() -> SessionService:
    workspace_env = os.environ.get("LECTURE_AUTO_WORKSPACE")
    base_dir = Path(workspace_env) if workspace_env else Path.home() / ".lecture_auto"
    metadata_file = base_dir / "metadata" / "sessions.json"
    store = SessionMetadataStore(metadata_file=metadata_file)

    llm_adapter = None
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key.strip():
        try:
            llm_adapter = GeminiLLMAdapter(
                LLMConfig(
                    api_key=api_key,
                    model_name=os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
                )
            )
        except LLMConfigError:
            llm_adapter = None

    stt_config = STTConfig(
        mode=os.environ.get("STT_MODE", "api"),
        api_provider=os.environ.get("STT_API_PROVIDER", "openai-compatible"),
        api_key=os.environ.get("STT_API_KEY"),
        local_model_name=os.environ.get("STT_LOCAL_MODEL", "base"),
    )

    return SessionService(
        store=store,
        runtime_adapter=FFmpegCaptureRuntimeAdapter(),
        stt_config=stt_config,
        llm_adapter=llm_adapter,
    )


def _run_or_exit(command: str, as_json: bool, action: callable) -> None:
    try:
        result = action()
    except SessionCommandError as exc:
        typer.echo(format_command_error(command, exc, as_json=as_json))
        raise typer.Exit(code=exc.exit_code)
    typer.echo(format_command_output(result, as_json=as_json))


@session_app.command("create")
def session_create(
    session_id: str = typer.Option(..., "--session-id", help="Session id"),
    date: str = typer.Option(..., "--date", help="Session date YYYY-MM-DD"),
    title: str | None = typer.Option(None, "--title", help="Session title"),
    course: str | None = typer.Option(None, "--course", help="Course name"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit(
        "session create",
        as_json,
        lambda: service.session_create(
            session_id=session_id,
            date=date,
            title=title,
            course=course,
        ),
    )


@session_app.command("history")
def session_history(
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit("session history", as_json, service.session_history)


@session_app.command("detail")
def session_detail(
    session_id: str = typer.Argument(..., help="Session id"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit("session detail", as_json, lambda: service.session_detail(session_id=session_id))


@capture_app.command("start")
def capture_start(
    session_id: str = typer.Argument(..., help="Session id"),
    audio_file_path: str | None = typer.Option(
        None,
        "--audio-file-path",
        help="Optional output path",
    ),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit(
        "capture start",
        as_json,
        lambda: service.capture_start(session_id=session_id, audio_file_path=audio_file_path),
    )


@capture_app.command("stop")
def capture_stop(
    session_id: str = typer.Argument(..., help="Session id"),
    failed: bool = typer.Option(False, "--failed", help="Mark capture as failed"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit(
        "capture stop",
        as_json,
        lambda: service.capture_stop(session_id=session_id, success=not failed),
    )


@transcription_app.command("run")
def transcription_run(
    session_id: str = typer.Argument(..., help="Session id"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit(
        "transcription run",
        as_json,
        lambda: service.transcribe_session(session_id=session_id),
    )


@app.command("summarize")
def summarize(
    session_id: str | None = typer.Option(None, "--id", help="Target session id"),
    template: str | None = typer.Option(None, "--template", help="Template name"),
    preview: bool = typer.Option(False, "--preview", help="Preview notes without saving"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    session_reference = session_id or ""
    _run_or_exit(
        "summarize",
        as_json,
        lambda: service.summarize_session(
            session_reference=session_reference,
            template_name=template,
            preview=preview,
        ),
    )


app.add_typer(session_app, name="session")
app.add_typer(capture_app, name="capture")
app.add_typer(transcription_app, name="transcription")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
