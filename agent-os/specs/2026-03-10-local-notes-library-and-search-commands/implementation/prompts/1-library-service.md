We're continuing our implementation of Local Notes Library and Search Commands by implementing task group number 1:

## Implement this task and its sub-tasks:

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

Using the task number and task title that's been assigned to you, create a file in the current spec's `implementation` folder called `1-library-service-implementation.md`.


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
