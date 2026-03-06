# Specification: Audio Import, Local Storage, and Job Runner

## Goal
Enable users to attach pre-existing local audio files to an existing lecture session via CLI and run a deterministic local processing job lifecycle. Ensure local file persistence, clear progress output, and bounded retry behavior for failed jobs.

## User Stories
- As a university student, I want to attach an existing audio file to a specific `session_id` so that I can continue lecture automation without live capture.
- As a CLI user, I want clear job progress and final status output so that I can understand what happened and what to do next.
- As a reliability-focused user, I want failed jobs to be retryable up to 3 times so that temporary failures can be recovered safely.

## Core Requirements
### Functional Requirements
- Require users to provide both `session_id` and audio file input for audio attach/import flow.
- Accept supported formats (`.wav`, `.mp3`) and reject unsupported formats with actionable CLI errors.
- Persist attached audio under deterministic, structured local paths and names consistent with session-based conventions.
- Trigger processing via terminal command and track lifecycle states including `queued`, `running`, `succeeded`, `failed`, and `canceled`.
- Allow retry only for failed jobs, with maximum retry count set to 3.
- Reject duplicate audio attachment for the same logical session/audio target.
- Provide CLI progress output containing start time, end time, current stage, final status, and next action guidance.

### Non-Functional Requirements
- Keep command output deterministic and concise so pytest assertions remain stable.
- Fail fast on invalid inputs (missing files, unsupported extension, unknown session, duplicate attachment).
- Keep error messages user-friendly and actionable without exposing unnecessary internals.
- Maintain local-first filesystem behavior and avoid introducing network/STT dependencies in this scope.

## Visual Design
- No visual assets were provided for this CLI feature.
- UX output design must follow the existing terminal formatting style used by current session commands.

## Reusable Components
### Existing Code to Leverage
- Components: `src/lecture_auto/cli_output.py` command/result rendering patterns (`format_command_output`, `format_command_error`).
- Services: `src/lecture_auto/session_service.py` session lookup, transition validation, and error contract patterns (`SessionCommandError`, `CommandResult`, `_require_session`, `_transition_or_raise`).
- Patterns: `src/lecture_auto/session_metadata_store.py` deterministic path conventions and atomic metadata persistence (`build_recording_path`, `_safe_write`, schema validation).

### New Components Required
- Audio import validation/use-case handler for pre-existing file attachment because current flow assumes runtime capture start/stop.
- Job-runner status persistence model for `queued/running/succeeded/failed/canceled` because current metadata schema tracks session capture state but not import job attempts/retries.
- Retry policy coordinator (failed-only, max 3) because current capture flow has no bounded retry tracking.

## Technical Approach
- Database: Keep using local JSON metadata patterns; extend metadata schema/store methods to track import job status, attempts, and duplicate attachment markers.
- API: CLI command surface only (no web API). Extend terminal command flow to accept `session_id` + audio input and optional retry action.
- Frontend: Terminal UX only; extend text and JSON-line output contracts in existing CLI formatter style.
- Testing: Add focused pytest coverage for file-type validation, duplicate rejection, status lifecycle (including canceled), retry cap, and progress output contract.

## Out of Scope
- STT pipeline/provider selection and transcription execution logic.
- Any feature not explicitly included in roadmap item 2.
- Changes to live capture start/stop behavior already delivered in roadmap item 1.

## Success Criteria
- Users can attach a supported pre-existing audio file to an existing `session_id` via CLI and see persisted local metadata and file path.
- Processing jobs can be triggered and observed through lifecycle states with clear progress output and next-step guidance.
- Failed jobs can be retried up to 3 times, duplicates are blocked, and unsupported formats are rejected with actionable errors.
