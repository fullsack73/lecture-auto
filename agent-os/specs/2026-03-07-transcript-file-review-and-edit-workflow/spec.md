# Specification: Transcript File Review and Edit Workflow

## Goal
The goal is to provide a command-driven workflow that allows users to search for transcripts by title and open them in their system's default text editor. Once edited and closed, the CLI automatically detects and saves the modified transcript locally as a new "edited" version, preserving the original "raw" transcript.

## User Stories
- As a student, I want to search for transcripts by session title so that I can easily find the lecture I want to review without knowing its ID or path.
- As a student, I want to open a transcript from the terminal so that it automatically opens in my preferred system text editor.
- As a student, I want the system to automatically save my modifications when I close the text editor so that I don't need to run a separate save or import command.

## Core Requirements
### Functional Requirements
- Command to search transcripts by session ID or title.
- Command to open/edit a transcript in the user's default system text editor.
- Automatic saving of edited transcripts as a new version (`edited` state) when the editor closes, without requiring an explicit save command.
- Overwriting the existing `edited` state if the user modifies an already edited transcript.
- The CLI must pause/wait while the external editor is open and detect file modifications upon closure.

### Non-Functional Requirements
- Must launch the text editor seamlessly in a cross-platform manner.
- Searching by title should be fast.
- The original `raw` transcript must remain unaltered.

## Visual Design
- Visual assets: None provided.

## Reusable Components
### Existing Code to Leverage
- Components: `session_metadata_store.py` for retrieving session IDs and paths.
- Services: `session_service.py` for handling session business logic.
- Commands: `cli_output.py` for Typer-based search/listing terminal output.

### New Components Required
- A new command handler (e.g., `transcript_runtime.py` or added to a related module) for Typer commands `open` and `search`.
- A mechanism to observe file changes (e.g., hash comparison or modification timestamp check) before and after launching the external editor.

## Technical Approach
- Database: Enhance `session_metadata_store.py` if needed to track `raw` vs `edited` transcript paths, although relying on filesystem artifacts (e.g., `raw.md` and `edited.md` in the session folder) is the preferred approach.
- API: Implement Typer commands `lecture search <title>` and `lecture open --session <id|title>`.
- Frontend: Launching standard OS text editor using `typer.launch(filepath, wait=True)`. Typer CLI output to provide status updates to the user (e.g., searching, opening).
- Testing: Integration tests covering the opening flow, verifying `raw` vs `edited` state mutations on disk using `pytest` fixtures, and testing the title search functionality.

## Out of Scope
- Searching through the content/text of transcript files (due to performance concerns).
- Multi-version history (e.g., `edited_v1`, `edited_v2`), just a single `edited` state.
- Diff output or change summary in the terminal.
- In-terminal interactive text editor.

## Success Criteria
- User can successfully run a search command and find transcripts by title.
- User can open the transcript in their default text editor from the CLI.
- Upon saving and closing the text editor, an `edited.md` file is generated or updated without further user input.
- End-to-end tests verify the creation of the `edited.md` file while leaving `raw.md` unmodified.
