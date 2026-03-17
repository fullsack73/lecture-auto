# Specification: Local Notes Library and Search Commands

## Goal
Add a `library` subcommand group to the existing Typer CLI so students can list lecture sessions, search session IDs and summary content, filter results, and open related files in Finder—reducing exam-prep friction.

## User Stories
- As a student, I want to run `lecture-auto library list` to see all lecture sessions so I can quickly review everything I've captured.
- As a student, I want to filter the list by date range, session status, or recent activity so I can focus on relevant sessions.
- As a student, I want to run `lecture-auto library search <query>` to find sessions matching a keyword so I can locate relevant lectures fast.
- As a student, I want to run `lecture-auto library open <session-id>` so that the related audio, transcript, and summary files open in Finder without manual navigation.

## Core Requirements

### Functional Requirements
- **`lecture-auto library list`**: Reads all sessions from `SessionMetadataStore.load_all()` and displays them; shows all statuses (not filtered to completed only).
- **`lecture-auto library search <query>`**: Case-insensitive grep-style string match against the session's `session_id` and the content of its summary `.md` file (`notes/{session_id}.md`). Sessions with no notes file are matched on `session_id` only.
- **`--filter` options (list & search)**: Both commands accept `--from <YYYY-MM-DD>`, `--to <YYYY-MM-DD>`, `--status <status>`, and `--sort recent`; `--sort recent` orders by the most recent timestamp value found in the session's existing `timestamps` dict.
- **`lecture-auto library open <session-id>`**: Opens the session's notes folder by default in the OS file manager (`open` on macOS, `xdg-open` on Linux, `explorer` on Windows) via `subprocess`. Pass `--transcript` to open the transcripts folder instead, or `--recordings` to open the recordings folder instead. Only one target is opened per invocation; silently falls back with a clear message if the target path does not exist.
- **Recent-activity sort**: Derived at runtime by finding the max ISO-8601 timestamp string among the session's `timestamps` dict values; no metadata schema changes required.
- **`--json` flag**: All three commands support `--json` for machine-readable output, consistent with existing commands.

### Non-Functional Requirements
- All errors use the existing `SessionCommandError` + `format_command_error()` pattern.
- All successful output uses `CommandResult` + `format_command_output()` pattern.

## Visual Design
No visual assets provided.

## Reusable Components

### Existing Code to Leverage
- **`SessionMetadataStore`** (`session_metadata_store.py`): `load_all()`, `get_by_session_id()`, `build_note_path()`, `build_recording_path()`, `build_raw_transcript_path()`
- **`CommandResult`, `SessionCommandError`** (`session_service.py`): reused as return/error types unchanged
- **`format_command_output()`, `format_command_error()`** (`cli_output.py`): extended with `library list`, `library search`, `library open` branches
- **Typer subcommand pattern, `_run_or_exit()`, `_build_service()`** (`cli.py`): add `library_app` following the existing `session_app`/`capture_app` pattern

### New Components Required
- **`library_service.py`**: New `LibraryService` class with `library_list()`, `library_search()`, `library_open()` methods; no existing service handles cross-session note file scanning or OS file-open operations.

## Technical Approach
- **CLI**: Add `library_app = typer.Typer(help="Library commands")` to `cli.py`; register via `app.add_typer(library_app, name="library")`.
- **Service**: `LibraryService.__init__(store: SessionMetadataStore, base_dir: Path)` holds workspace root; methods return `CommandResult`.
- **Search**: Pure Python `query.lower() in text.lower()` against session_id string and note file text; no external dependencies.
- **File open**: `subprocess.run(["open", path])` on macOS (`sys.platform == "darwin"`); `["explorer", path]` on Windows (`sys.platform == "win32"`); `["xdg-open", path]` on Linux. Default target is the `notes/` folder; `--transcript` targets the `transcripts/` folder; `--recordings` targets the `recordings/` folder. The folder path is derived from `base_dir` without requiring a file to exist at a specific path.
- **Filtering**: Pure in-memory filtering on the list returned by `store.load_all()`; date comparisons use string ordering on `YYYY-MM-DD` format; status is a string equality check; recent-activity sort uses `max()` over `timestamps` dict string values.
- **Output formatting**: Extend `cli_output.py` with display branches for library commands.

## Out of Scope
- Cloud sync or remote file access
- Multi-user support
- AI/semantic/vector-based search
- Tag or subject-based filtering beyond status and date range
- Any features not implied by roadmap item 7
- Unnecessary modification of existing files

## Success Criteria
- `lecture-auto library list` displays all sessions from the metadata store
- `lecture-auto library list --from/--to/--status/--sort` correctly filters and orders results
- `lecture-auto library search <query>` returns sessions whose session_id or notes content contains the query
- `lecture-auto library search <query> --filter` options narrow results as specified
- `lecture-auto library open <session-id>` opens the notes folder in Finder by default; `--transcript` and `--recordings` flags open their respective folders
