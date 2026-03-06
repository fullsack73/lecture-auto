# Task 2: Import Command Flow, Validation, and Retry Rules

## Overview
**Task Reference:** Task #2 from `agent-os/specs/2026-03-06-audio-import-local-storage-and-job-runner/tasks.md`
**Implemented By:** api-engineer
**Date:** 2026-03-06
**Status:** ✅ Complete

### Task Description
Implement pre-existing audio import flow with `session_id` + source file input, format validation, duplicate blocking, job lifecycle states, and failed-only retry (max 3).

## Implementation Summary
`SessionService` was extended with `import_audio`, `retry_import_audio`, and `cancel_import_audio` use cases. The flow validates source input, enforces `.wav`/`.mp3` support, blocks duplicate imports per session/source, and persists lifecycle progress (`queued`, `running`, `succeeded`, `failed`, `canceled`).

Retry logic was implemented with strict policy checks: retry is allowed only when the previous import status is `failed`, and attempts are capped at 3. On copy failures, errors are mapped into user-facing result payloads and persisted with job error code and timestamps.

## Files Changed/Created

### New Files
- None.

### Modified Files
- `src/lecture_auto/session_service.py` - Added import/retry/cancel command logic, lifecycle transitions, validation, and file-copy orchestration.
- `tests/test_session_business_rules.py` - Added focused business-rule tests for import lifecycle, extension validation, duplicate handling, and retry limits.

### Deleted Files
- None.

## Key Implementation Details

### Import Lifecycle State Machine
**Location:** `src/lecture_auto/session_service.py`

Added a separate import-job state machine and transition validation to avoid conflicting with existing capture lifecycle states.

**Rationale:** Preserves backward compatibility with existing capture flow while enabling roadmap item 2 lifecycle requirements.

### Failed-Only Retry with Cap
**Location:** `src/lecture_auto/session_service.py`

Implemented retry checks for status and attempts with dedicated error codes (`IMPORT_RETRY_NOT_ALLOWED`, `IMPORT_RETRY_LIMIT_EXCEEDED`).

**Rationale:** Enforces explicit business rules and prevents unbounded retries.

## Database Changes (if applicable)
Not applicable (local JSON metadata storage only).

## Dependencies (if applicable)
No new dependencies were added.

## Testing

### Test Files Created/Updated
- `tests/test_session_business_rules.py` - Tests import success path, unsupported extension rejection, duplicate rejection, retry success, and retry cap rejection.

### Test Coverage
- Unit tests: ✅ Complete
- Integration tests: ⚠️ Partial
- Edge cases covered: unsupported extension, duplicate source, retry on non-failed state, retry limit exceeded.

### Manual Testing Performed
- Verified import command behavior by creating temporary files and checking persisted status payloads.

## User Standards & Preferences Compliance

### Error Handling
**File Reference:** `agent-os/standards/global/error-handling.md`

**How Your Implementation Complies:**
All validation failures return actionable `SessionCommandError` codes/messages/guidance and fail fast before invalid state persists.

**Deviations (if any):**
None.

### Validation
**File Reference:** `agent-os/standards/global/validation.md`

**How Your Implementation Complies:**
Input path presence and extension allowlist checks are enforced early in service methods.

**Deviations (if any):**
None.

### Backend API/Logic Standards
**File Reference:** `agent-os/standards/backend/api.md`

**How Your Implementation Complies:**
Command service contract remains consistent (`CommandResult` on success, typed error contract on failure) for predictable CLI adaptation.

**Deviations (if any):**
None.

## Integration Points (if applicable)
- Interacts with `SessionMetadataStore` for schema persistence and deterministic target path selection.

## Known Issues & Limitations
- `cancel_import_audio` is implemented for lifecycle completeness but no dedicated CLI wrapper command exists yet.

## Performance Considerations
Import copy operation is local filesystem I/O and runs synchronously.

## Security Considerations
Extension allowlist and explicit source-path validation reduce accidental unsupported input handling.

## Dependencies for Other Tasks
- Task 3 consumes import payload progress fields for CLI output formatting.

## Notes
Implementation intentionally excludes STT/provider workflow per out-of-scope rules.
