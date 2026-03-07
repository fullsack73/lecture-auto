from __future__ import annotations

import os
from pathlib import Path

import typer

from lecture_auto.cli_output import format_command_error, format_command_output
from lecture_auto.llm_adapter import GeminiLLMAdapter, LLMConfigError
from lecture_auto.llm_config import LLMConfig
from lecture_auto.session_metadata_store import SessionMetadataStore
from lecture_auto.session_service import SessionCommandError, SessionService

app = typer.Typer(help="Lecture automation CLI")


def _build_service() -> SessionService:
    metadata_file = Path.home() / ".lecture_auto" / "metadata" / "sessions.json"
    store = SessionMetadataStore(metadata_file=metadata_file)

    llm_adapter = None
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key.strip():
        try:
            llm_adapter = GeminiLLMAdapter(LLMConfig(api_key=api_key))
        except LLMConfigError:
            llm_adapter = None

    return SessionService(store=store, llm_adapter=llm_adapter)


@app.command("summarize")
def summarize(
    session_id: str | None = typer.Option(None, "--id", help="Target session id"),
    template: str | None = typer.Option(None, "--template", help="Template name"),
    preview: bool = typer.Option(False, "--preview", help="Preview notes without saving"),
    as_json: bool = typer.Option(False, "--json", help="Render output as JSON"),
) -> None:
    service = _build_service()
    session_reference = session_id or ""

    try:
        result = service.summarize_session(
            session_reference=session_reference,
            template_name=template,
            preview=preview,
        )
    except SessionCommandError as exc:
        typer.echo(format_command_error("summarize", exc, as_json=as_json))
        raise typer.Exit(code=exc.exit_code)

    typer.echo(format_command_output(result, as_json=as_json))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
