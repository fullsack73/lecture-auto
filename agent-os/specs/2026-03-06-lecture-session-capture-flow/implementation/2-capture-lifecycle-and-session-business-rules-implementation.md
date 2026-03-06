# Task 2: Capture Lifecycle and Session Business Rules

## Overview
**Task Reference:** Task #2 from `agent-os/specs/2026-03-06-lecture-session-capture-flow/tasks.md`
**Implemented By:** api-engineer
**Date:** 2026-03-06
**Status:** ✅ Complete

### Task Description
Implement lifecycle business rules and command handlers for session creation, capture start/stop, session history/detail, plus output/error contracts with deterministic behavior.

## Implementation Summary
Implemented `SessionService` to coordinate lifecycle transitions and persistence on top of Task 1 metadata store. The service enforces a strict transition graph for `idle`, `recording`, `stopping`, `completed`, and `failed`, and raises explicit command errors when invalid transitions or missing sessions are encountered.

All required handlers were added (`session create`, `capture start`, `capture stop`, `session history`, `session detail`) with deterministic payload structures. Output contract support is provided through `CommandResult`, which returns plain text by default and one-line JSON for machine parsing.

Failure mapping was implemented for dependency/device/runtime cases with specific error codes, guidance, and non-zero exit codes. Naming fallback logic marks `naming_pending=true` when `title` or `course` is missing.

## Files Changed/Created

### New Files
- `src/lecture_auto/session_service.py` - Lifecycle state machine, command handlers, output contract, and failure mapping.
- `tests/test_session_business_rules.py` - Focused lifecycle and business-rule tests (valid/invalid transitions, failure mapping, persistence, naming fallback, output mode).

### Modified Files
- `agent-os/specs/2026-03-06-lecture-session-capture-flow/tasks.md` - Marked Task Group 2 and all sub-tasks complete.

### Deleted Files
- None.

## Key Implementation Details

### Capture State Machine + Validation
**Location:** `src/lecture_auto/session_service.py`

Defined allowed transitions with `ALLOWED_TRANSITIONS` and validated all state changes through `_transition_or_raise`. Invalid transitions raise `SessionCommandError` with consistent `code`, actionable `guidance`, and `exit_code`.

**Rationale:** Centralizing transition checks keeps business rules explicit, testable, and consistent across all command handlers.

### Session Command Handlers + Output Contract
**Location:** `src/lecture_auto/session_service.py`

Implemented handlers for create/start/stop/history/detail and persisted all changes through `SessionMetadataStore`. Added `CommandResult.as_text()` for plain text and `CommandResult.as_json_line()` for one-line JSON output.

**Rationale:** Provides stable output behavior for both human CLI usage and deterministic automated assertions.

## Database Changes (if applicable)

### Migrations
- None.

### Schema Impact
No new schema fields were added beyond Task 1; handlers now populate/advance status and lifecycle timestamps under existing schema.

## Dependencies (if applicable)

### New Dependencies Added
- None.

### Configuration Changes
- None.

## Testing

### Test Files Created/Updated
- `tests/test_session_business_rules.py` - Covers valid transitions, invalid transition rejection, failure mapping contract, status persistence/detail lookup, naming fallback, and output mode.

### Test Coverage
- Unit tests: ✅ Complete
- Integration tests: ⚠️ Partial
- Edge cases covered: invalid transition rejection, error-code mapping with non-zero exits, one-line JSON output, naming fallback when metadata is incomplete

### Manual Testing Performed
Executed only Task 2 focused test file:
- `pytest tests/test_session_business_rules.py -q`
- Result: `8 passed`

## User Standards & Preferences Compliance

### Coding Style Best Practices
**File Reference:** `agent-os/standards/global/coding-style.md`

**How Your Implementation Complies:**
Business logic is split into focused methods (`session_create`, `capture_start`, `_transition_or_raise`, `map_capture_failure`) with descriptive names and clear intent.

**Deviations (if any):**
None.

### Code Commenting Best Practices
**File Reference:** `agent-os/standards/global/commenting.md`

**How Your Implementation Complies:**
Code is primarily self-documenting via naming and structure; only minimal comments are used in tests where intent is non-obvious.

**Deviations (if any):**
None.

### Error Handling Best Practices
**File Reference:** `agent-os/standards/global/error-handling.md`

**How Your Implementation Complies:**
Errors are explicit and user-oriented through `SessionCommandError` with specific code/message/guidance and non-zero exit codes suitable for CLI boundaries.

**Deviations (if any):**
None.

### Validation Best Practices
**File Reference:** `agent-os/standards/global/validation.md`

**How Your Implementation Complies:**
Session existence and transition preconditions are validated before state changes, failing early with actionable feedback.

**Deviations (if any):**
None.

### Test Writing Best Practices
**File Reference:** `agent-os/standards/testing/test-writing.md`

**How Your Implementation Complies:**
Added only focused tests for critical lifecycle/business behaviors and avoided exhaustive non-critical branch testing.

**Deviations (if any):**
None.

## Integration Points (if applicable)

### APIs/Endpoints
- None (service-layer implementation for CLI commands).

### External Services
- None.

### Internal Dependencies
- `SessionMetadataStore` from `src/lecture_auto/session_metadata_store.py`.

## Known Issues & Limitations

### Issues
1. **Lifecycle Timestamps Use Current UTC Clock**
   - Description: Runtime timestamps are generated at execution time.
   - Impact: Exact timestamp values vary across runs.
   - Workaround: Inject a clock provider in future if strict timestamp determinism is required.
   - Tracking: None.

### Limitations
1. **Handlers Are Service-Level, Not Yet CLI-Wired**
   - Description: Logic is implemented in service layer; Typer command wiring is deferred.
   - Reason: Current task scope focused on business rules and handler behavior.
   - Future Consideration: Wire into CLI command module in Task Group 3.

## Performance Considerations
The service performs local file-backed metadata operations suitable for student-scale usage; command handlers operate with minimal processing overhead.

## Security Considerations
No external calls are introduced; all operations remain local and avoid exposing low-level exception details in command error contracts.

## Dependencies for Other Tasks
- Provides core lifecycle/handler contracts needed for Task Group 3 CLI UX and formatting work.

## Notes
Implementation remains intentionally scoped to Task Group 2 requirements and test validation boundaries.
