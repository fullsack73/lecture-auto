# Task 3: Transcription Stage Output and Actionable Error UX

## Overview
**Task Reference:** Task #3 from `agent-os/specs/2026-03-06-stt-pipeline-with-provider-selection/tasks.md`
**Implemented By:** ui-designer
**Date:** 2026-03-06
**Status:** ✅ Complete

### Task Description
Provide clear terminal output for transcription lifecycle stages and ensure actionable user-facing error messaging remains consistent for the new STT flow.

## Implementation Summary
CLI output formatting was extended to render a dedicated transcription result view for text mode while preserving the existing JSON-line output contract. The rendering includes ordered stages, current/final state, attempt/retry values, and final transcript path.

Additional tests verify text readability, JSON stability, and actionability of error messages for transcription categories. This keeps the terminal UX consistent with existing command output conventions.

## Files Changed/Created

### New Files
- `tests/test_transcription_cli_output.py` - Focused CLI output tests for transcription text and JSON contracts.

### Modified Files
- `src/lecture_auto/cli_output.py` - Added `transcription run` output handler and stage-based renderer.

### Deleted Files
- None.

## Key Implementation Details

### Transcription Output Renderer
**Location:** `src/lecture_auto/cli_output.py`

Added `_render_transcription_text()` and routing for `result.command == "transcription run"`.

**Rationale:** Keeps the command-specific rendering strategy already used by capture/import flows.

### Stage and Path Visibility
**Location:** `src/lecture_auto/cli_output.py`

Output includes ordered stage list, attempt/retry values, and transcript path to improve user scanability.

**Rationale:** Directly addresses requirement for clear progress stages and actionable completion output.

## Database Changes (if applicable)

### Migrations
- Not applicable.

### Schema Impact
No direct schema changes in this task group.

## Dependencies (if applicable)

### New Dependencies Added
- None.

### Configuration Changes
- None.

## Testing

### Test Files Created/Updated
- `tests/test_transcription_cli_output.py` - Asserts text readability, one-line JSON output, and actionable error phrasing.

### Test Coverage
- Unit tests: ✅ Complete
- Integration tests: ⚠️ Partial
- Edge cases covered: missing/newline-sensitive JSON contract and category-specific error rendering.

### Manual Testing Performed
- No browser testing needed; feature is terminal-only output.

## User Standards & Preferences Compliance

### Frontend Components
**File Reference:** `agent-os/standards/frontend/components.md`

**How Your Implementation Complies:**
Terminal output uses consistent component-like sections (header, key facts, next step) to keep UX predictable across commands.

**Deviations (if any):**
None.

### Frontend Accessibility
**File Reference:** `agent-os/standards/frontend/accessibility.md`

**How Your Implementation Complies:**
Output prioritizes plain-text readability with explicit labels and scan-friendly line structure.

**Deviations (if any):**
None.

### Testing
**File Reference:** `agent-os/standards/testing/test-writing.md`

**How Your Implementation Complies:**
Added only focused formatting contract tests for critical user-facing output behavior.

**Deviations (if any):**
None.

## Integration Points (if applicable)

### Internal Dependencies
- Consumes `transcription_progress` payload produced by `SessionService.transcribe_session()`.

## Known Issues & Limitations

### Issues
1. **No issues identified**
   - Description: None.
   - Impact: None.
   - Workaround: Not needed.
   - Tracking: N/A

### Limitations
1. **Terminal-only rendering**
   - Description: Formatting targets CLI text and JSON-line output only.
   - Reason: Product is terminal-first with no web UI.
   - Future Consideration: N/A for current roadmap scope.

## Performance Considerations
String formatting is lightweight and deterministic.

## Security Considerations
Error output avoids exposing secrets while preserving actionable guidance.

## Dependencies for Other Tasks
- Task Group 4 validates end-to-end output behavior and stability.

## Notes
Renderer naming and structure follow existing command formatting conventions to reduce maintenance overhead.
