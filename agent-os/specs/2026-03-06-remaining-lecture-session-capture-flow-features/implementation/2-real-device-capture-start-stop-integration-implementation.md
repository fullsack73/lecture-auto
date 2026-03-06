# Task 2: Real Device Capture Start/Stop Integration

## Overview
**Task Reference:** Task #2 from `agent-os/specs/2026-03-06-remaining-lecture-session-capture-flow-features/tasks.md`
**Implemented By:** api-engineer
**Date:** 2026-03-06
**Status:** ✅ Complete

### Task Description
Implement a runtime adapter boundary for real capture start/stop orchestration and wire it into session command logic while preserving existing output and error contracts.

## Implementation Summary
Introduced a dedicated runtime adapter module to isolate capture process control from session business logic. The new boundary supports both a deterministic default adapter for non-device environments and an FFmpeg-backed real adapter for device-based recording execution paths.

`SessionService` now delegates capture lifecycle operations to the runtime adapter, preserving status transitions and metadata persistence while mapping runtime failures into the existing actionable command error contract. Capture metadata now includes runtime process information (`capture_process_id`, `capture_backend`) for traceability.

## Files Changed/Created

### New Files
- `src/lecture_auto/capture_runtime.py` - Runtime adapter protocol, error types, deterministic adapter, and FFmpeg-based capture adapter.
- `tests/test_capture_runtime_orchestration.py` - Focused Task 2 tests for start/stop orchestration, lifecycle handoff, failure mapping, and status persistence.

### Modified Files
- `src/lecture_auto/session_service.py` - Wired runtime adapter into `capture_start` and `capture_stop`, added default path generation and runtime metadata persistence.
- `agent-os/specs/2026-03-06-remaining-lecture-session-capture-flow-features/tasks.md` - Marked Task Group 2 parent/subtasks complete.

### Deleted Files
- None.

## Key Implementation Details

### Runtime Adapter Boundary
**Location:** `src/lecture_auto/capture_runtime.py`

Added `CaptureRuntimeAdapter` protocol plus typed runtime error classes. Implemented `FFmpegCaptureRuntimeAdapter` (real capture path via `ffmpeg`) and `NoopCaptureRuntimeAdapter` for deterministic non-device execution and testability.

**Rationale:** Decouples process/hardware behavior from command orchestration and keeps business logic testable.

### SessionService Runtime Wiring
**Location:** `src/lecture_auto/session_service.py`

`SessionService` now accepts an optional runtime adapter, resolves default recording paths via metadata store, starts/stops capture through adapter calls, and maps runtime exceptions into existing error contracts. Output message shapes and JSON contracts remain unchanged.

**Rationale:** Satisfies real-capture integration requirement while preserving existing command/output behavior.

## Database Changes (if applicable)

### Migrations
- None.

### Schema Impact
No schema field additions; runtime details are stored in existing `timestamps` object to preserve compatibility.

## Dependencies (if applicable)

### New Dependencies Added
- None.

### Configuration Changes
- None.

## Testing

### Test Files Created/Updated
- `tests/test_capture_runtime_orchestration.py` - Verifies adapter handoff, start/stop orchestration, failure mapping, and persisted runtime metadata.

### Test Coverage
- Unit tests: ✅ Complete
- Integration tests: ⚠️ Partial
- Edge cases covered: dependency failure mapping, permission failure mapping, interruption mapping, default session-id path generation

### Manual Testing Performed
Executed only Task Group 2 focused tests:
- `pytest tests/test_capture_runtime_orchestration.py -q`
- Result: `5 passed`

## User Standards & Preferences Compliance

### Coding Style Best Practices
**File Reference:** `agent-os/standards/global/coding-style.md`

**How Your Implementation Complies:**
Split runtime concerns into a dedicated module and kept service methods focused on orchestration and error mapping.

**Deviations (if any):**
None.

### Error Handling Best Practices
**File Reference:** `agent-os/standards/global/error-handling.md`

**How Your Implementation Complies:**
Runtime failures are converted to existing user-facing error contracts with actionable guidance and stable exit codes.

**Deviations (if any):**
None.

### Tech Stack Standards
**File Reference:** `agent-os/standards/global/tech-stack.md`

**How Your Implementation Complies:**
Runtime integration follows terminal-first Python approach and includes FFmpeg-based capture path.

**Deviations (if any):**
None.

### Backend API/Query Standards
**File References:**
- `agent-os/standards/backend/api.md`
- `agent-os/standards/backend/queries.md`

**How Your Implementation Complies:**
Command-boundary contracts remain consistent for both success and failure responses while preserving deterministic query/persistence flow.

**Deviations (if any):**
None.

### Test Writing Best Practices
**File Reference:** `agent-os/standards/testing/test-writing.md`

**How Your Implementation Complies:**
Added 5 focused tests (within 2-8 limit) for critical behaviors only.

**Deviations (if any):**
None.

## Integration Points (if applicable)

### APIs/Endpoints
- None (CLI/service scope only).

### External Services
- FFmpeg process integration via local system executable.

### Internal Dependencies
- Depends on `SessionMetadataStore` for persistence and recording-path convention helper.

## Known Issues & Limitations

### Issues
1. **FFmpeg Device Arguments Are macOS-Oriented**
   - Description: Real adapter currently uses `avfoundation` input defaults.
   - Impact: Cross-platform capture settings may require adapter extension.
   - Workaround: Override/extend adapter command construction per platform.
   - Tracking: None.

### Limitations
1. **Default Runtime Is Deterministic Noop Adapter**
   - Description: Service defaults to deterministic adapter for stable tests.
   - Reason: Avoid hard dependency on local capture hardware in automated runs.
   - Future Consideration: Add configuration-driven runtime selection in CLI wiring.

## Performance Considerations
Runtime process management is lightweight; start/stop flows only add adapter call overhead and timestamp persistence updates.

## Security Considerations
Capture remains local-process based; no external network service is introduced.

## Dependencies for Other Tasks
- Task Group 3 relies on preserved output contract behavior after runtime integration.
- Task Group 4 relies on adapter/test structure for gap analysis and manual device verification.

## Notes
Implementation intentionally keeps output contract stable while adding runtime orchestration boundary and FFmpeg execution path.
