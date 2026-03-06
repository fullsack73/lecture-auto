# Task Breakdown: Transcript File Review and Edit Workflow

## Overview
Total Tasks: 2 main task groups
Assigned roles: api-engineer, testing-engineer

## Task List

### CLI and Business Logic Layer

#### Task Group 1: CLI Commands and File Observer Logic
**Assigned implementer:** api-engineer
**Dependencies:** None

- [x] 1.0 Complete CLI commands and execution logic
  - [x] 1.1 Write 2-8 focused tests for the CLI and logic
    - Include a test for title-based search finding the correct session.
    - Include a test for launching the editor and capturing a file modification, creating `edited.md`.
    - Mock external dependencies like `typer.launch()`.
  - [x] 1.2 Implement the `lecture search <title>` command
    - Query `session_metadata_store` for matching session titles.
    - Format terminal output showing matched sessions (ID, Title, Date).
  - [x] 1.3 Implement the `lecture open --session <id|title>` command
    - Resolve the session ID or Title into a directory path.
    - Locate the active transcript (`edited.md` if exists, otherwise `raw.md`).
    - Capture the file's current modification timestamp or hash.
  - [x] 1.4 Implement the editor blocking and save logic
    - Use `typer.launch(filepath, wait=True)` to block until the user is done.
    - Compare post-edit file hash/timestamp with pre-edit values.
    - If modified (and the original was `raw.md`), save the changes as `edited.md` in the session folder, leaving `raw.md` unmodified. 
    - Output success message.
  - [x] 1.5 Ensure CLI layer tests pass
    - Run ONLY the 2-8 tests written in 1.1
    - Verify search and open/save behaviors work via mocked `typer` and temporary files.

**Acceptance Criteria:**
- The 2-8 tests written in 1.1 pass.
- `lecture search "title"` correctly outputs matching sessions.
- `lecture open --session ID` successfully launches the file.
- The system correctly generates `edited.md` after the file is altered and closed, leaving `raw.md` intact.

### Testing

#### Task Group 2: Test Review & Gap Analysis
**Assigned implementer:** testing-engineer
**Dependencies:** Task Group 1

- [x] 2.0 Review existing tests and fill critical gaps only
  - [x] 2.1 Review tests from Task Group 1
    - Review the 2-8 tests written by api-engineer (Task 1.1).
  - [x] 2.2 Analyze test coverage gaps for THIS feature only
    - Focus ONLY on gaps related to this spec's feature requirements (e.g. edge cases where user opening an already `edited.md` transcript and saving over it).
  - [x] 2.3 Write up to 10 additional strategic tests maximum
    - Add maximum of 10 new tests to fill identified critical gaps.
    - Example: Test searching with no results, or saving without structural modifications.
  - [x] 2.4 Run feature-specific tests only
    - Run ONLY tests related to this spec's feature (tests from 1.1 and 2.3).
    - Verify critical workflows pass.

**Acceptance Criteria:**
- All feature-specific tests pass.
- Critical user workflows for this feature are covered.
- No more than 10 additional tests added by testing-engineer.

## Execution Order

Recommended implementation sequence:
1. CLI Commands and File Observer Logic (Task Group 1)
2. Test Review & Gap Analysis (Task Group 2)
