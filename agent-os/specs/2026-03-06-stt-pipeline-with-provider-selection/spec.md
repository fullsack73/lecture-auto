# Specification: STT Pipeline with Provider Selection

## Goal
Enable users to run transcription from session-linked audio using a selectable STT mode (`local` or `api`) with default `api`, fail-fast setup checks, and deterministic raw transcript output. Ensure stage-based CLI progress and actionable error guidance, including bounded API retries.

## User Stories
- As a university student, I want to run transcription for a session that already has recorded/imported audio so that I can get a usable raw transcript without leaving the terminal.
- As a CLI user, I want to choose between local model and API provider modes so that I can balance privacy, cost, and quality.
- As a reliability-focused user, I want transient API failures retried automatically (up to 2 times) with clear error guidance so that recoverable failures are handled safely.

## Core Requirements
### Functional Requirements
- Allow transcription only for existing sessions that already have attached audio artifacts from capture/import flow.
- Exclude direct transcription from arbitrary non-session file paths.
- Support exactly two STT modes in CLI config: `local` and `api`, with default mode set to `api`.
- Run preflight setup checks before transcription starts and fail fast on missing prerequisites (for example invalid provider, missing API key, missing local model/runtime dependency).
- Persist only the latest raw transcript per session under deterministic local path conventions.
- Provide stage-based CLI progress for the transcription lifecycle: preflight checks, mode/provider initialization, transcription run, transcript write complete.
- Classify errors into actionable categories: configuration, provider authentication, network/transient, and audio format/decoding.
- Apply automatic retries only for transient API failures, capped at 2 retries.
- Do not auto-retry local-model failures; return immediate fix guidance.

### Non-Functional Requirements
- Keep output deterministic and concise for stable automated tests.
- Preserve existing local-first architecture and session metadata conventions.
- Use clear user-friendly error messages with explicit next actions.
- Keep command execution predictable with bounded retry behavior and no hidden long-running loops.

## Visual Design
- No visual assets were provided for this CLI feature.
- Terminal output should follow existing command formatting patterns for readability and consistency.

## Reusable Components
### Existing Code to Leverage
- Components: `src/lecture_auto/cli_output.py` output templates and JSON-line contracts (`format_command_output`, `format_command_error`) for stage/progress and actionable errors.
- Services: `src/lecture_auto/session_service.py` session validation, command orchestration, state transitions, and error mapping patterns (`SessionCommandError`, `CommandResult`, `_require_session`).
- Patterns: `src/lecture_auto/session_service.py` import job flow and retry contract (`import_audio`, `retry_import_audio`, `_build_progress_payload`) as a template for STT progress and bounded retries.
- Data persistence: `src/lecture_auto/session_metadata_store.py` schema normalization and deterministic local artifact paths (`METADATA_FIELDS`, `upsert`, path helpers).
- Error taxonomy pattern: `src/lecture_auto/capture_runtime.py` typed runtime exceptions and mapping to user-facing command errors.

### New Components Required
- STT configuration module (mode/provider/local-model settings) because current code has no transcription-mode configuration surface.
- STT runtime adapter abstraction (local model + API provider implementations) because current runtime adapters cover capture only, not transcription.
- Transcript persistence helper for latest-per-session raw transcript replacement because current metadata/file helpers focus on audio artifacts.
- Transcription command/service entry points in CLI/session orchestration because current commands stop at capture/import/session detail.

## Technical Approach
- Database: Continue local JSON metadata storage; extend session metadata fields to track transcript path, transcription status stage, retry counts, and last transcription error category.
- API: No web API; add/extend Typer CLI command flow for transcription trigger, status rendering, and bounded API retry handling.
- Frontend: Terminal-only UX; extend existing CLI output formatters to render transcription stages and final transcript location in text and JSON output.
- Testing: Add focused pytest coverage for session-only scope enforcement, mode selection/default behavior, preflight failures, transient API retry cap (2), local no-retry behavior, latest transcript replacement, and CLI output/error contracts.

## Out of Scope
- Any capability not described in roadmap item 3.
- Transcript editing/review workflows, LLM refinement, and summary-note generation.
- Advanced STT enhancements not requested (for example diarization, translation, or rich segment export).
- Direct transcription from arbitrary non-session file paths.

## Success Criteria
- Users can run transcription from terminal commands for session-linked audio and receive a complete raw transcript saved to deterministic local storage.
- Users can switch between `local` and `api` STT modes with default `api`, and preflight checks prevent invalid runs before execution.
- API transient failures retry automatically up to 2 times, local failures do not auto-retry, and all failure outcomes provide actionable guidance.
- CLI output clearly reports transcription stages and ends with the final transcript file path.
