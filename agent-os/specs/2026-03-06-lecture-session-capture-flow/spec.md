# Specification: Lecture Session Capture Flow

## Goal
Provide a terminal-first lecture session recording flow that lets students create sessions, record system audio reliably, and review session history/details from CLI. Persist standardized local JSON metadata and recording artifacts so transcription/refinement/note generation can be run later.

## User Stories
- As a university student, I want to create a lecture session and start/stop recording from terminal commands so I can focus on class.
- As a student reviewing later at home, I want saved audio and session history/details so I can generate notes after class instead of immediately.
- As a user, I want clear success/failure CLI output so I can quickly recover from recording issues.
- As a developer, I want deterministic outputs (text and optional JSON) so I can verify behavior in tests.

## Core Requirements
### Functional Requirements
- Provide CLI commands for `session create`, `capture start`, `capture stop`, `session history`, and `session detail <session_id>`.
- Store session metadata in a standardized local JSON structure under the local filesystem app data layout.
- Use a single session `date` field (instead of separate `started_at`/`ended_at`) plus recording lifecycle timestamps where needed for traceability.
- Accept optional user input for `title` and `course`; system must still work when omitted.
- When `title` or `course` is missing, define metadata placeholders/flags so later transcript-based LLM naming can fill values in downstream specs.
- Enforce capture state transitions (`idle`, `recording`, `stopping`, `completed`, `failed`) and block invalid transitions.
- Preserve recorded audio files and expose their status in history/detail views.
- Default CLI output to plain text; when `--json` is provided, return one-line JSON output for each command.
- Handle failure cases with actionable error messages and non-zero exit codes: unavailable audio device, missing FFmpeg/PyAudio, permission denied, interrupted capture, and write failures.

### Non-Functional Requirements
- Reliability: command execution should leave session state consistent even on interruption/failure.
- Testability: command outputs and JSON metadata schema must be deterministic for pytest assertions.
- Performance: history/detail should load from local JSON quickly for typical student-scale session counts.
- Security/Privacy: keep all artifacts local by default; no mandatory external calls in this spec.
- Usability: error messages must be user-friendly and include next-action guidance.

## Visual Design
- No visual mockups provided for this spec.
- Interface is terminal output only (no web UI).

## Reusable Components
### Existing Code to Leverage
- Components: No existing UI components identified (CLI-only workspace currently has planning/docs artifacts).
- Services: No existing recording/session service implementations found in current workspace.
- Patterns: Reuse established product patterns from `agent-os/product/tech-stack.md` (Typer CLI, local filesystem storage, FFmpeg+PyAudio/SoundCard integration).

### New Components Required
- Session metadata store module for standardized JSON read/write and schema validation.
- Capture state machine module to enforce valid lifecycle transitions.
- CLI command handlers for create/start/stop/history/detail with dual output mode (text or one-line JSON).
- Failure mapping layer to normalize dependency/device/runtime errors into actionable CLI messages.
- These are required because no implementation code exists yet in the current repository to extend.

## Technical Approach
- Database: No external DB; use local JSON metadata file(s) with stable schema, IDs, status, date, paths, and audit timestamps.
- API: No HTTP API in this spec; command interface is Typer CLI with structured output contract.
- Frontend: Terminal output formatting only; plain text default and `--json` one-line mode.
- Testing: Add focused pytest coverage for core flows only: session lifecycle success path, invalid transition blocking, history/detail retrieval, and key failure scenarios.

## Out of Scope
- Running actual transcription, transcript refinement, and note generation in this spec.
- Advanced filtering/search/export and collaboration workflows.
- Any web frontend, account/authentication system, or cloud sync behavior.

## Success Criteria
- Users can complete create -> start -> stop -> history -> detail from terminal without manual file edits.
- Session metadata and audio artifact references are persisted in standardized JSON and can be reloaded consistently.
- Invalid state transitions are rejected with clear errors and non-zero exit codes.
- Each command supports readable text output and one-line JSON via `--json`, both verifiable in tests.
