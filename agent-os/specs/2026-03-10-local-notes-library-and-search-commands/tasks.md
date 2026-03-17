# Task Breakdown: Local Notes Library and Search Commands

## Overview
Total Tasks: 14
Assigned roles: api-engineer, testing-engineer

## Task List

### Service Layer

#### Task Group 1: Library Service
**Assigned implementer:** api-engineer
**Dependencies:** None

- [ ] 1.0 Complete library service layer
  - [ ] 1.1 Write 2-8 focused tests for `LibraryService`
    - Limit to 2-8 highly focused tests maximum
    - Test only critical behaviors: `library_list()` returns all sessions, `library_search()` matches session_id and note content, `library_open()` calls subprocess for existing files
    - Skip exhaustive edge-case coverage
  - [ ] 1.2 Create `src/lecture_auto/library_service.py` with `LibraryService` class
    - `__init__(store: SessionMetadataStore, base_dir: Path)`
    - `library_list(from_date, to_date, status_filter, sort_recent) → CommandResult`
    - `library_search(query, from_date, to_date, status_filter, sort_recent) → CommandResult`
    - `library_open(session_id) → CommandResult`
    - Reuse pattern from: `SessionService` in `session_service.py`
  - [ ] 1.3 Implement filtering and sorting in `LibraryService`
    - Date range: string comparison on `session["date"]` (`YYYY-MM-DD`)
    - Status filter: equality check on `session["status"]`
    - Recent-activity sort: `max()` over ISO-8601 string values in `session["timestamps"]` dict
  - [ ] 1.4 Implement `library_search()` grep-style matching
    - Case-insensitive: `query.lower() in session_id.lower()`
    - Read `notes/{session_id}.md` if it exists; match against content
    - Skip sessions with no notes file for content check; still match on session_id
  - [ ] 1.5 Implement `library_open()` file opener
    - Signature: `library_open(session_id, *, open_transcript=False, open_recordings=False) → CommandResult`
    - Default target: `base_dir / "notes"` folder; `open_transcript=True` → `base_dir / "transcripts"`; `open_recordings=True` → `base_dir / "recordings"`
    - Use `subprocess.run(["open", folder_path])` on macOS (`sys.platform == "darwin"`), `["explorer", folder_path]` on Windows (`sys.platform == "win32"`), `["xdg-open", folder_path]` on Linux
    - Report success with opened path in `CommandResult.payload`; return clear message if folder does not exist
    - Raise `SessionCommandError` if session_id is not found in the store
  - [ ] 1.6 Ensure service layer tests pass
    - Run ONLY the 2-8 tests written in 1.1
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 1.1 pass
- `library_list()` returns all sessions from `store.load_all()`; filter/sort args narrow or reorder results correctly
- `library_search()` returns sessions whose session_id or notes content contains the query
- `library_open()` calls subprocess on the resolved folder path (notes by default, or transcripts/recordings via flags)

---

### CLI Integration Layer

#### Task Group 2: CLI Commands and Output Formatting
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [ ] 2.0 Complete CLI integration
  - [ ] 2.1 Write 2-8 focused tests for CLI commands
    - Limit to 2-8 highly focused tests maximum
    - Test only critical command behaviors: `library list` exits 0, `library search <query>` returns matches, `library open <id>` exits 0 for known session
    - Skip exhaustive option permutation testing
  - [ ] 2.2 Add `library_app` Typer sub-app to `src/lecture_auto/cli.py`
    - `library_app = typer.Typer(help="Library commands")`
    - Register with `app.add_typer(library_app, name="library")`
    - Reuse pattern from: `session_app`, `capture_app` in `cli.py`
  - [ ] 2.3 Implement `library list` command in `cli.py`
    - Options: `--from` (date string), `--to` (date string), `--status` (string), `--sort` (literal `"recent"`), `--json`
    - Calls `LibraryService.library_list()` via `_run_or_exit()` pattern
  - [ ] 2.4 Implement `library search <query>` command in `cli.py`
    - Positional arg: `query: str`
    - Same filter options as list (`--from`, `--to`, `--status`, `--sort`, `--json`)
    - Calls `LibraryService.library_search()` via `_run_or_exit()` pattern
  - [ ] 2.5 Implement `library open <session-id>` command in `cli.py`
    - Positional arg: `session_id: str`
    - Options: `--transcript` (flag, open transcripts folder), `--recordings` (flag, open recordings folder), `--json`
    - Default (no flag): opens `notes/` folder
    - Calls `LibraryService.library_open()` via `_run_or_exit()` pattern
  - [ ] 2.6 Add output formatting branches to `src/lecture_auto/cli_output.py`
    - Branch for `result.command == "library list"`: render session table (session_id, date, status, title)
    - Branch for `result.command == "library search"`: render matched sessions with match context
    - Branch for `result.command == "library open"`: render the opened folder path (or not-found message)
    - Reuse pattern from: `_render_history_text()` and similar helpers in `cli_output.py`
  - [ ] 2.7 Ensure CLI tests pass
    - Run ONLY the 2-8 tests written in 2.1
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 2.1 pass
- `lecture-auto library list` runs without error and displays session rows
- `lecture-auto library search <query>` returns matching sessions
- `lecture-auto library open <session-id>` opens notes folder by default; `--transcript`/`--recordings` flags open respective folders

---

### Testing Layer

#### Task Group 3: Additional Tests
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1 and 2

- [ ] 3.0 Add additional focused tests (maximum 10)
  - [ ] 3.1 Write up to 10 additional tests covering edge cases
    - `library_list()` with all filter combinations applied together
    - `library_search()` with no notes file present (matches only on session_id)
    - `library_search()` with no matching results returns empty payload
    - `library_open()` raises `SessionCommandError` for unknown session_id
    - `library_open()` returns a clear message when the target folder does not exist without raising
    - `library_open(open_transcript=True)` opens transcripts folder; `open_recordings=True` opens recordings folder
    - `--sort recent` ordering correctness when timestamps vary across sessions
  - [ ] 3.2 Ensure all new tests pass
    - Run ONLY the tests written in 3.1
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- All tests written in 3.1 pass
- Edge cases for missing files, unknown sessions, and filter combinations are covered
