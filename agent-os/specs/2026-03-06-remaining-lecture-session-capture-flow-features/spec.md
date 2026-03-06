# Specification: Remaining Lecture Session Capture Flow Features

## Goal
Complete the unimplemented portions of Roadmap item 1 by wiring real device-backed audio recording into the existing terminal session flow. Keep existing CLI output/error contracts stable while making capture start/stop produce real audio artifacts.

## User Stories
- As a university student, I want `capture start` and `capture stop` to run real recording so I can reliably save lecture audio.
- As a student, I want recording failures to return clear guidance so I can recover quickly during class.
- As a developer, I want deterministic metadata/history/detail behavior preserved so tests remain stable while real capture is added.

## Core Requirements
### Functional Requirements
- Implement real audio capture execution for `capture start` and `capture stop` using the product audio stack (FFmpeg + PyAudio/SoundCard integration path).
- Keep command scope limited to Roadmap item 1 flow: `session create -> capture start -> capture stop -> session history -> session detail`.
- Persist recording files under `recordings/` with file naming based on session ID only.
- Preserve existing metadata schema and lifecycle transitions while integrating runtime capture state.
- Preserve existing plain-text and one-line JSON output contracts.
- Preserve existing error contract style: explicit error codes, non-zero exits, and actionable next-step guidance.

### Non-Functional Requirements
- Reliability: interrupted or failed recording must not corrupt session metadata or leave ambiguous final state.
- Testability: keep automated tests deterministic with mocks; add manual real-device verification steps for hardware capture behavior.
- Performance: start/stop command latency should remain responsive for terminal use.
- Privacy/Security: all recordings and metadata remain local by default.

## Visual Design
- No visual mockups provided.
- Interface remains terminal-only with existing output formatting patterns.

## Reusable Components
### Existing Code to Leverage
- Components: `src/lecture_auto/session_metadata_store.py` for schema and atomic local JSON persistence.
- Services: `src/lecture_auto/session_service.py` for lifecycle transitions, command contracts, and failure mapping boundaries.
- Patterns: `src/lecture_auto/cli_output.py` and `tests/test_cli_output_formatting.py` for stable text/JSON output contracts.

### New Components Required
- Audio capture runtime adapter/module to manage real recording process lifecycle.
- Capture process state coordination (PID/process handle or equivalent) aligned with existing service transitions.
- Manual real-device validation checklist for supported local environments.

## Technical Approach
- Database: Continue local JSON metadata store; add only minimal fields/timestamps required to represent runtime capture execution safely.
- API: No HTTP API; command boundary remains terminal command handlers.
- Frontend: Terminal output templates remain unchanged unless strictly required for runtime clarity.
- Testing: Extend with mock-based integration tests for capture adapter wiring and add documented manual device verification steps.

## Out of Scope
- Any roadmap feature outside item 1.
- STT transcription pipeline and provider selection.
- Transcript review/edit, transcript refinement, summary note generation, notes search library, export/share packaging.
- Broad refactor/rewrite of already implemented previous-spec components beyond minimal integration changes.

## Success Criteria
- `capture start` begins real recording and writes audio to `recordings/{session_id}.*` (or configured extension) in local storage.
- `capture stop` finalizes recording and persists consistent metadata/history/detail state.
- Existing CLI text and one-line JSON output contracts remain valid.
- Failure modes (dependency, permission, device, interruption, write failure) return actionable errors with non-zero exits.
- Automated mock-based tests pass and manual real-device verification checklist is executable and successful on target environment.
