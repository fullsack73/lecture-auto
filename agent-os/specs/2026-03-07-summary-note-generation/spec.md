# Specification: Summary Note Generation with Templates

## Goal
Enable users to generate structured lecture notes from a session's transcript via a `summarize` CLI command, using predefined or custom Markdown templates, with preview, save, and regenerate flows.

## User Stories
- As a student, I want to run `lecture-auto summarize` so that lecture notes are automatically generated from the latest transcript.
- As a student, I want to specify a session via `--id` so that I can generate notes for a specific past session.
- As a student, I want to choose a template via `--template` so that the output format matches my study style.
- As a student, I want to preview the generated notes in the terminal so that I can review before saving.
- As a student, I want to re-run summarize to overwrite my existing notes so that I can regenerate with a different template.

## Core Requirements

### Functional Requirements
- `summarize` CLI command that generates lecture notes from a session's transcript
- Default behavior: automatically targets the most recent transcript version (edited if available, otherwise raw)
- `--id <session_id>` flag to target a specific session
- `--template <template_name>` flag to specify which template to use; defaults to the preset default if omitted
- 2–3 predefined `.md` template presets (e.g., `bullet-summary`, `structured-notes`, `qa-review`); one is the default
- Custom user-defined `.md` templates stored in a local `templates/` directory; selectable via `--template`
- `--preview` flag: display generated notes in terminal before saving, without persisting
- Save flow: persist generated notes as `.md` file under `notes/` directory within the session folder structure
- Regenerate flow: re-running summarize overwrites the existing note file (no versioning)
- Uses existing provider-agnostic LLM adapter (`llm_adapter.py`) for generation

### Non-Functional Requirements
- Follows existing Typer CLI command patterns established in `session_service.py`
- No additional external dependencies beyond those already used by `llm_adapter.py`
- Error messages follow existing `SessionCommandError` pattern with code, message, guidance, and exit_code
- Generated note filenames follow a predictable convention tied to `session_id`

## Visual Design
No visual assets provided. CLI-only feature.

## Reusable Components

### Existing Code to Leverage
- `llm_adapter.py` — reuse `LLMProviderAdapter` protocol and `GeminiLLMAdapter` for note generation
- `llm_config.py` — reuse `LLMConfig` dataclass for LLM configuration
- `session_service.py` — reuse `SessionService` class structure, `SessionCommandError`, `CommandResult`, and transcript file lookup patterns (`transcript_refine` method as direct model)
- `cli_output.py` — reuse `format_command_output` dispatch pattern for displaying summarize results and preview output
- `session_metadata_store.py` — reuse `SessionMetadataStore` for session lookup and path building

### New Components Required
- `summarize_service.py` (or method on `SessionService`) — orchestrates session lookup, transcript reading, template loading, LLM call, and file write; no existing equivalent
- Template preset files (e.g., `config/templates/bullet-summary.md`, `structured-notes.md`, `qa-review.md`) — first-time introduction of template storage; no existing pattern
- `notes/` path builder on `SessionMetadataStore` — analogous to `build_raw_transcript_path` but for notes

## Technical Approach
- **Storage**: Notes stored at `notes/{session_id}.md` within the session data directory; single file per session (overwrite on regenerate)
- **Templates**: Predefined templates stored under `src/lecture_auto/templates/`; user custom templates stored in a configurable local directory (e.g., `~/.lecture_auto/templates/`); `--template` accepts a name resolved against both locations
- **CLI**: New `summarize` Typer command registered in the CLI entry point; flags: `--id`, `--template`, `--preview`
- **LLM**: Extend `LLMProviderAdapter` protocol with a `generate_notes(transcript: str, template: str, context_topic: str | None) -> str` method; implement in `GeminiLLMAdapter`
- **Testing**: pytest; mock LLM adapter and filesystem; focus on critical paths (session lookup, template resolution, file write, preview vs. save flow)

## Out of Scope
- Multi-session summary merging
- PDF export
- Versioning of generated notes
- Any functionality not explicitly described in roadmap item #6

## Success Criteria
- `lecture-auto summarize` generates and saves a `.md` note from the most recent transcript
- `lecture-auto summarize --id <id>` targets the specified session
- `lecture-auto summarize --template <name>` uses the specified template (predefined or custom)
- `lecture-auto summarize --preview` displays notes in terminal without saving
- Re-running summarize overwrites the existing note file
- All core pytest tests pass
