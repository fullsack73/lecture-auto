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
from lecture_auto.library_service import LibraryService

app = typer.Typer(help="Lecture automation CLI", invoke_without_command=True)
session_app = typer.Typer(help="Session commands")
capture_app = typer.Typer(help="Capture commands")
transcription_app = typer.Typer(help="Transcription commands")
config_app = typer.Typer(help="Configuration commands")
library_app = typer.Typer(help="Library commands")


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
            run_tui(service, service_factory=_build_service)
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
    config_stt_mode = None
    config_stt_local_model = None
    config_gemini_api_key = None
    config_llm_model_name = None
    config_llm_thinking_level = None
    config_audio_format = None
    config_capture_source = None
    config_google_project_id = None
    config_google_location = None
    config_use_dynaudnorm = False
    config_dynaudnorm_f = None
    config_dynaudnorm_g = None
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
                config_stt_mode = config_data.get("stt_mode")
                config_stt_local_model = config_data.get("stt_local_model")
                config_gemini_api_key = config_data.get("gemini_api_key")
                config_llm_model_name = config_data.get("llm_model_name")
                config_llm_thinking_level = config_data.get("llm_thinking_level")
                config_audio_format = config_data.get("audio_format")
                config_capture_source = config_data.get("capture_source")
                config_google_project_id = config_data.get("google_project_id")
                config_google_location = config_data.get("google_location")
                config_use_dynaudnorm = config_data.get("use_dynaudnorm", False)
                config_dynaudnorm_f = config_data.get("dynaudnorm_f")
                config_dynaudnorm_g = config_data.get("dynaudnorm_g")
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
            model_name = (
                os.environ.get("LLM_MODEL")
                or config_llm_model_name
                or "gemini-3.1-flash-lite-preview"
            )
            thinking_level = (
                os.environ.get("LLM_THINKING_LEVEL")
                or config_llm_thinking_level
                or "medium"
            )
            llm_config = LLMConfig(
                api_key=api_key,
                model_name=model_name.strip(),
                thinking_level=thinking_level.strip().lower(),
                language=config_llm_language,
            )
            llm_config.validate()
            llm_adapter = GeminiLLMAdapter(
                llm_config
            )
        except (LLMConfigError, ValueError):
            llm_adapter = None

    resolved_dynaudnorm_f = None
    if config_dynaudnorm_f is not None:
        try:
            resolved_dynaudnorm_f = int(config_dynaudnorm_f)
        except (TypeError, ValueError):
            pass

    resolved_dynaudnorm_g = None
    if config_dynaudnorm_g is not None:
        try:
            resolved_dynaudnorm_g = int(config_dynaudnorm_g)
        except (TypeError, ValueError):
            pass

    resolved_use_dynaudnorm = bool(os.environ.get("USE_DYNAUDNORM") or config_use_dynaudnorm)

    stt_config = STTConfig(
        mode=cast(Literal["local", "api"], os.environ.get("STT_MODE") or config_stt_mode or "api"),
        api_provider=os.environ.get("STT_API_PROVIDER") or config_stt_api_provider or "openai-compatible",
        api_key=os.environ.get("STT_API_KEY") or config_stt_api_key,
        local_model_name=os.environ.get("STT_LOCAL_MODEL") or config_stt_local_model or "base",
        language=config_stt_language,
        google_project_id=os.environ.get("GOOGLE_PROJECT_ID") or config_google_project_id,
        google_location=os.environ.get("GOOGLE_LOCATION") or config_google_location or "us",
        use_dynaudnorm=resolved_use_dynaudnorm,
        dynaudnorm_f=resolved_dynaudnorm_f,
        dynaudnorm_g=resolved_dynaudnorm_g,
    )

    return SessionService(
        store=store,
        runtime_adapter=FFmpegCaptureRuntimeAdapter(
            capture_source=os.environ.get("LECTURE_AUTO_CAPTURE_SOURCE") or config_capture_source or "microphone"
        ),
        stt_config=stt_config,
        llm_adapter=llm_adapter,
        audio_format=os.environ.get("LECTURE_AUTO_AUDIO_FORMAT") or config_audio_format or "wav",
    )


from typing import Callable, Any, cast, Literal

def _run_or_exit(command: str, as_json: bool, action: Callable[..., Any]) -> None:
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


@session_app.command("update")
def session_update_cmd(
    session_id: str = typer.Argument(..., help="Session id to update"),
    new_id: str | None = typer.Option(None, "--new-id", help="New session ID (rename)"),
    title: str | None = typer.Option(None, "--title", help="New title (empty string to clear)"),
    course: str | None = typer.Option(None, "--course", help="New course (empty string to clear)"),
    date: str | None = typer.Option(None, "--date", help="New date YYYY-MM-DD"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    from lecture_auto.session_service import _UNSET  # type: ignore[attr-defined]

    if new_id is None and title is None and course is None and date is None:
        typer.echo(
            "Error: At least one of --new-id, --title, --course, or --date must be provided."
        )
        raise typer.Exit(code=1)

    service = _build_service()
    kwargs: dict = {}
    if new_id is not None:
        kwargs["new_session_id"] = new_id
    if title is not None:
        kwargs["title"] = title
    if course is not None:
        kwargs["course"] = course
    if date is not None:
        kwargs["date"] = date

    _run_or_exit(
        "session update",
        as_json,
        lambda: service.session_update_metadata(session_id=session_id, **kwargs),
    )


@session_app.command("import-material")
def session_import_material(
    session_id: str = typer.Argument(..., help="Session ID to import material into"),
    material_path: str = typer.Argument(..., help="Path to the PDF material file"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    """Import a PDF lecture material into a session."""
    service = _build_service()
    _run_or_exit(
        "material import",
        as_json,
        lambda: service.import_material(session_id=session_id, material_path=material_path),
    )


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
    stt_api_provider: str | None = typer.Option(None, "--stt-api-provider", help="STT API provider (e.g. deepgram, google-chirp3)"),
    stt_api_key: str | None = typer.Option(None, "--stt-api-key", help="STT API key"),
    stt_mode: str | None = typer.Option(None, "--stt-mode", help="STT mode (api or local)"),
    stt_local_model: str | None = typer.Option(None, "--stt-local-model", help="Local Whisper model name (e.g. base, medium, large-v3)"),
    gemini_api_key: str | None = typer.Option(None, "--gemini-api-key", help="Gemini API key for LLM"),
    llm_model_name: str | None = typer.Option(None, "--llm-model", help="LLM model name (gemini-3.1-flash-lite-preview or gemini-3.1-pro-preview)"),
    llm_thinking_level: str | None = typer.Option(None, "--llm-thinking-level", help="LLM thinking level (minimal, low, medium, high)"),
    audio_format: str | None = typer.Option(None, "--audio-format", help="Default audio format for recordings (wav or mp3)"),
    capture_source: str | None = typer.Option(None, "--capture-source", help="Capture source (microphone or system_audio)"),
    google_project_id: str | None = typer.Option(None, "--google-project-id", help="Google Cloud project ID (required for google-chirp3 STT provider)"),
    use_dynaudnorm: bool | None = typer.Option(None, "--use-dynaudnorm/--no-use-dynaudnorm", help="Apply dynaudnorm audio filter during STT pre-processing."),
    dynaudnorm_f: int | None = typer.Option(None, "--dynaudnorm-f", help="dynaudnorm 'f' parameter (10 to 8000)."),
    dynaudnorm_g: int | None = typer.Option(None, "--dynaudnorm-g", help="dynaudnorm 'g' parameter (odd integer 3 to 301)."),
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

    if stt_mode is not None:
        normalized_mode = stt_mode.strip().lower()
        if normalized_mode not in {"api", "local"}:
            typer.echo("STT mode must be 'api' or 'local'.", err=True)
            raise typer.Exit(code=1)
        config_data["stt_mode"] = normalized_mode
        typer.echo(f"Global STT mode set to: {config_data['stt_mode']}")
        updated = True

    if stt_local_model is not None:
        normalized_model = stt_local_model.strip()
        if normalized_model:
            config_data["stt_local_model"] = normalized_model
            typer.echo(f"Global STT local model set to: {config_data['stt_local_model']}")
            updated = True
        elif "stt_local_model" in config_data:
            del config_data["stt_local_model"]
            typer.echo("Global STT local model cleared.")
            updated = True

    if gemini_api_key is not None:
        config_data["gemini_api_key"] = gemini_api_key
        typer.echo(f"Global Gemini API key configured.")
        updated = True

    if llm_model_name is not None:
        normalized_model = llm_model_name.strip()
        valid_models = {"gemini-3.1-flash-lite-preview", "gemini-3.1-pro-preview"}
        if normalized_model not in valid_models:
            typer.echo(
                f"LLM model must be one of {valid_models}.",
                err=True,
            )
            raise typer.Exit(code=1)
        config_data["llm_model_name"] = normalized_model
        typer.echo(f"Global LLM model set to: {config_data['llm_model_name']}")
        updated = True

    if llm_thinking_level is not None:
        normalized_level = llm_thinking_level.strip().lower()
        valid_levels = {"minimal", "low", "medium", "high"}
        if normalized_level not in valid_levels:
            typer.echo(
                f"LLM thinking level must be one of {valid_levels}.",
                err=True,
            )
            raise typer.Exit(code=1)
        config_data["llm_thinking_level"] = normalized_level
        typer.echo(f"Global LLM thinking level set to: {config_data['llm_thinking_level']}")
        updated = True

    if audio_format is not None:
        if audio_format not in ("wav", "mp3"):
            typer.echo("Audio format must be 'wav' or 'mp3'.", err=True)
            raise typer.Exit(code=1)
        config_data["audio_format"] = audio_format
        typer.echo(f"Global audio format set to: {config_data['audio_format']}")
        updated = True

    if capture_source is not None:
        normalized_source = capture_source.strip().lower()
        if normalized_source not in ("microphone", "system_audio"):
            typer.echo("Capture source must be 'microphone' or 'system_audio'.", err=True)
            raise typer.Exit(code=1)
        config_data["capture_source"] = normalized_source
        typer.echo(f"Global capture source set to: {config_data['capture_source']}")
        updated = True

    if google_project_id is not None:
        config_data["google_project_id"] = google_project_id
        typer.echo(f"Google Cloud project ID set to: {config_data['google_project_id']}")
        updated = True

    if use_dynaudnorm is not None:
        config_data["use_dynaudnorm"] = use_dynaudnorm
        typer.echo(f"Global use_dynaudnorm set to: {config_data['use_dynaudnorm']}")
        updated = True

    if dynaudnorm_f is not None:
        if dynaudnorm_f < 10 or dynaudnorm_f > 8000:
            typer.echo("dynaudnorm_f must be between 10 and 8000.", err=True)
            raise typer.Exit(code=1)
        config_data["dynaudnorm_f"] = dynaudnorm_f
        typer.echo(f"Global dynaudnorm_f set to: {config_data['dynaudnorm_f']}")
        updated = True

    if dynaudnorm_g is not None:
        if dynaudnorm_g < 3 or dynaudnorm_g > 301 or dynaudnorm_g % 2 == 0:
            typer.echo("dynaudnorm_g must be an odd integer between 3 and 301.", err=True)
            raise typer.Exit(code=1)
        config_data["dynaudnorm_g"] = dynaudnorm_g
        typer.echo(f"Global dynaudnorm_g set to: {config_data['dynaudnorm_g']}")
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


@library_app.command("list")
def library_list(
    from_date: str | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    sort: str | None = typer.Option(None, "--sort", help="Sort by 'recent'"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    store = SessionMetadataStore(metadata_file=(Path(os.environ.get("LECTURE_AUTO_WORKSPACE") or Path.home() / ".lecture_auto") / "metadata" / "sessions.json"))
    library_service = LibraryService(store=store, base_dir=Path(os.environ.get("LECTURE_AUTO_WORKSPACE") or Path.home() / ".lecture_auto"))
    _run_or_exit(
        "library list",
        as_json,
        lambda: library_service.library_list(
            from_date=from_date,
            to_date=to_date,
            status_filter=status,
            sort_recent=(sort == "recent"),
        ),
    )


@library_app.command("search")
def library_search(
    query: str = typer.Argument(..., help="Search query"),
    from_date: str | None = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str | None = typer.Option(None, "--to", help="End date (YYYY-MM-DD)"),
    status: str | None = typer.Option(None, "--status", help="Filter by status"),
    sort: str | None = typer.Option(None, "--sort", help="Sort by 'recent'"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    workspace = Path(os.environ.get("LECTURE_AUTO_WORKSPACE") or Path.home() / ".lecture_auto")
    store = SessionMetadataStore(metadata_file=workspace / "metadata" / "sessions.json")
    library_service = LibraryService(store=store, base_dir=workspace)
    _run_or_exit(
        "library search",
        as_json,
        lambda: library_service.library_search(
            query=query,
            from_date=from_date,
            to_date=to_date,
            status_filter=status,
            sort_recent=(sort == "recent"),
        ),
    )


@library_app.command("open")
def library_open(
    session_id: str = typer.Argument(..., help="Session ID"),
    transcript: bool = typer.Option(False, "--transcript", help="Open transcripts folder"),
    recordings: bool = typer.Option(False, "--recordings", help="Open recordings folder"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    workspace = Path(os.environ.get("LECTURE_AUTO_WORKSPACE") or Path.home() / ".lecture_auto")
    store = SessionMetadataStore(metadata_file=workspace / "metadata" / "sessions.json")
    library_service = LibraryService(store=store, base_dir=workspace)
    _run_or_exit(
        "library open",
        as_json,
        lambda: library_service.library_open(
            session_id=session_id,
            open_transcript=transcript,
            open_recordings=recordings,
        ),
    )


app.add_typer(session_app, name="session")
app.add_typer(capture_app, name="capture")
app.add_typer(transcription_app, name="transcription")
app.add_typer(config_app, name="config")
app.add_typer(library_app, name="library")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
