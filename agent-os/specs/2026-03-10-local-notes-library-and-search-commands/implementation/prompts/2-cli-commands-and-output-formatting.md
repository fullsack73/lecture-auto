We're continuing our implementation of Local Notes Library and Search Commands by implementing task group number 2:

## Implement this task and its sub-tasks:

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

## Understand the context

Read @agent-os/specs/2026-03-10-local-notes-library-and-search-commands/spec.md to understand the context for this spec and where the current task fits into it.

## Perform the implementation

Implement all tasks assigned to you in your task group.

Focus ONLY on implementing the areas that align with **areas of specialization** (your "areas of specialization" are defined above).

Guide your implementation using:
- **The existing patterns** that you've found and analyzed.
- **User Standards & Preferences** which are defined below.

Self-verify and test your work by:
- Running ONLY the tests you've written (if any) and ensuring those tests pass.
- IF your task involves user-facing UI, and IF you have access to browser testing tools, open a browser and use the feature you've implemented as if you are a user to ensure a user can use the feature in the intended way.


## Update tasks.md task status

In the current spec's `tasks.md` find YOUR task group that's been assigned to YOU and update this task group's parent task and sub-task(s) checked statuses to complete for the specific task(s) that you've implemented.

Mark your task group's parent task and sub-task as complete by changing its checkbox to `- [x]`.

DO NOT update task checkboxes for other task groups that were NOT assigned to you for implementation.


## Document your implementation

Using the task number and task title that's been assigned to you, create a file in the current spec's `implementation` folder called `2-cli-commands-and-output-formatting-implementation.md`.


## User Standards & Preferences Compliance

IMPORTANT: Ensure that your implementation is ALIGNED and DOES NOT CONFLICT with the user's preferences and standards as detailed in the following files:

@agent-os/standards/global/coding-style.md
@agent-os/standards/global/commenting.md
@agent-os/standards/global/conventions.md
@agent-os/standards/global/error-handling.md
@agent-os/standards/global/tech-stack.md
@agent-os/standards/global/validation.md
@agent-os/standards/backend/api.md
@agent-os/standards/backend/migrations.md
@agent-os/standards/backend/models.md
@agent-os/standards/backend/queries.md
@agent-os/standards/testing/test-writing.md
