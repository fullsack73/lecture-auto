from __future__ import annotations

import json
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

app = typer.Typer(help="Lecture automation CLI", invoke_without_command=True)
session_app = typer.Typer(help="Session commands")
capture_app = typer.Typer(help="Capture commands")
transcription_app = typer.Typer(help="Transcription commands")
config_app = typer.Typer(help="Configuration commands")


def _get_global_config_path() -> Path:
    return Path.home() / ".lecture_auto" / "config.json"


@app.callback()
def app_callback(
    ctx: typer.Context,
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
    if ctx.invoked_subcommand is None:
        from lecture_auto.tui import run_tui
        service = _build_service()
        try:
            run_tui(service)
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nBye! 👋")
        raise typer.Exit()


def _build_service() -> SessionService:
    workspace_env = os.environ.get("LECTURE_AUTO_WORKSPACE")
    config_workspace = None
    config_stt_language = None
    config_llm_language = None
    config_stt_api_provider = None
    config_stt_api_key = None
    config_gemini_api_key = None
    config_path = _get_global_config_path()
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                config_workspace = config_data.get("workspace")
                config_stt_language = config_data.get("stt_language")
                config_llm_language = config_data.get("llm_language")
                config_stt_api_provider = config_data.get("stt_api_provider")
                config_stt_api_key = config_data.get("stt_api_key")
                config_gemini_api_key = config_data.get("gemini_api_key")
        except Exception:
            pass

    resolved_workspace = workspace_env or config_workspace
    if not workspace_env and resolved_workspace:
        os.environ["LECTURE_AUTO_WORKSPACE"] = resolved_workspace
        
    base_dir = Path(resolved_workspace) if resolved_workspace else Path.home() / ".lecture_auto"
    metadata_file = base_dir / "metadata" / "sessions.json"
    store = SessionMetadataStore(metadata_file=metadata_file)

    llm_adapter = None
    api_key = os.environ.get("GEMINI_API_KEY") or config_gemini_api_key
    if api_key and api_key.strip():
        try:
            llm_adapter = GeminiLLMAdapter(
                LLMConfig(
                    api_key=api_key,
                    model_name=os.environ.get("LLM_MODEL", "gemini-3-flash-preview"),
                    language=config_llm_language,
                )
            )
        except LLMConfigError:
            llm_adapter = None

    stt_config = STTConfig(
        mode=os.environ.get("STT_MODE", "api"),
        api_provider=os.environ.get("STT_API_PROVIDER") or config_stt_api_provider or "openai-compatible",
        api_key=os.environ.get("STT_API_KEY") or config_stt_api_key,
        local_model_name=os.environ.get("STT_LOCAL_MODEL", "base"),
        language=config_stt_language,
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


@session_app.command("delete")
def session_delete_cmd(
    session_id: str = typer.Argument(..., help="Session id to delete"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    _run_or_exit("session delete", as_json, lambda: service.session_delete(session_id=session_id))


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


@config_app.command("set")
def config_set(
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Default workspace directory"),
    stt_language: str | None = typer.Option(None, "--stt-language", "-stt", help="Default language for STT transcription (e.g. korean)"),
    llm_language: str | None = typer.Option(None, "--llm-language", "-llm", help="Default language for summaries and generated notes (e.g. korean)"),
    stt_api_provider: str | None = typer.Option(None, "--stt-api-provider", help="STT API provider (e.g. deepgram)"),
    stt_api_key: str | None = typer.Option(None, "--stt-api-key", help="STT API key"),
    gemini_api_key: str | None = typer.Option(None, "--gemini-api-key", help="Gemini API key for LLM"),
) -> None:
    config_path = _get_global_config_path()
    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            pass
    
    updated = False
    if workspace is not None:
        config_data["workspace"] = str(Path(workspace).expanduser().resolve())
        typer.echo(f"Global workspace set to: {config_data['workspace']}")
        updated = True
        
    if stt_language is not None:
        config_data["stt_language"] = stt_language
        typer.echo(f"Global STT language set to: {config_data['stt_language']}")
        updated = True

    if llm_language is not None:
        config_data["llm_language"] = llm_language
        typer.echo(f"Global LLM language set to: {config_data['llm_language']}")
        updated = True

    if stt_api_provider is not None:
        config_data["stt_api_provider"] = stt_api_provider
        typer.echo(f"Global STT API provider set to: {config_data['stt_api_provider']}")
        updated = True

    if stt_api_key is not None:
        config_data["stt_api_key"] = stt_api_key
        typer.echo(f"Global STT API key configured.")
        updated = True

    if gemini_api_key is not None:
        config_data["gemini_api_key"] = gemini_api_key
        typer.echo(f"Global Gemini API key configured.")
        updated = True

    if not updated:
        typer.echo("No configuration options provided to set.")
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


@config_app.command("show")
def config_show() -> None:
    config_path = _get_global_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            typer.echo(json.dumps(config_data, indent=2))
        except Exception as e:
            typer.echo(f"Error reading config: {e}")
    else:
        typer.echo("No global configuration found.")


app.add_typer(session_app, name="session")
app.add_typer(capture_app, name="capture")
app.add_typer(transcription_app, name="transcription")
app.add_typer(config_app, name="config")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
