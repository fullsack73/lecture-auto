# Task 3: Terminal Command UX and Output Formatting

## Overview
**Task Reference:** Task #3 from `agent-os/specs/2026-03-06-lecture-session-capture-flow/tasks.md`
**Implemented By:** ui-designer
**Date:** 2026-03-06
**Status:** ✅ Complete

### Task Description
Define and implement terminal-facing output templates for success/failure flows, enforce standardized one-line JSON output for `--json`, and improve readability for session history/detail outputs.

## Implementation Summary
Implemented a dedicated formatter module (`cli_output.py`) that converts service-layer command results and errors into either readable plain text or standardized one-line JSON. The formatter provides explicit templates per command path (`session create`, `capture start`, `capture stop`, `session history`, `session detail`) and includes next-action guidance where applicable.

History and detail rendering were optimized for terminal scanning: history uses concise single-line summaries per session, while detail output enumerates complete per-session fields including timestamps and naming status. JSON output shape was normalized to include top-level `ok`, `command`, and either `payload`/`message` or structured `error` data.

## Files Changed/Created

### New Files
- `src/lecture_auto/cli_output.py` - Plain-text and JSON output templates for command success and error rendering.
- `tests/test_cli_output_formatting.py` - Focused tests validating readability, actionable failures, one-line JSON contract, and history/detail rendering.

### Modified Files
- `agent-os/specs/2026-03-06-lecture-session-capture-flow/tasks.md` - Marked Task Group 3 and all sub-tasks complete.

### Deleted Files
- None.

## Key Implementation Details

### Command-Specific Text Templates
**Location:** `src/lecture_auto/cli_output.py`

Added explicit plain-text templates for create/start/stop/history/detail command outputs. Templates include concise labels and next-step guidance to reduce CLI ambiguity.

**Rationale:** Per-command formatting keeps terminal output predictable and user-friendly for the primary student workflow.

### One-Line JSON Output Contract
**Location:** `src/lecture_auto/cli_output.py`

Implemented `_json_line` serializer with compact separators and no multiline output. Success and error outputs share a normalized top-level shape (`ok`, `command`, payload/message or error object).

**Rationale:** A stable machine-parseable envelope supports deterministic tests and future automation.

## Database Changes (if applicable)

### Migrations
- None.

### Schema Impact
No metadata schema changes; this task focuses only on presentation formatting.

## Dependencies (if applicable)

### New Dependencies Added
- None.

### Configuration Changes
- None.

## Testing

### Test Files Created/Updated
- `tests/test_cli_output_formatting.py` - Validates readable success text, actionable failure text, one-line JSON, concise history rows, and complete detail rendering.

### Test Coverage
- Unit tests: ✅ Complete
- Integration tests: ⚠️ Partial
- Edge cases covered: empty/new session guidance in templates, one-line JSON enforcement, standardized success/error envelope keys

### Manual Testing Performed
Executed only Task 3 focused test file:
- `pytest tests/test_cli_output_formatting.py -q`
- Result: `5 passed`

## User Standards & Preferences Compliance

### Coding Style Best Practices
**File Reference:** `agent-os/standards/global/coding-style.md`

**How Your Implementation Complies:**
Formatting logic is split into clear functions (`format_command_output`, `format_command_error`, `_render_history_text`, `_render_detail_text`) with descriptive naming and limited responsibilities.

**Deviations (if any):**
None.

### Code Commenting Best Practices
**File Reference:** `agent-os/standards/global/commenting.md`

**How Your Implementation Complies:**
The implementation uses self-explanatory function names and minimal comments, with no temporary or change-log style comments.

**Deviations (if any):**
None.

### Error Handling Best Practices
**File Reference:** `agent-os/standards/global/error-handling.md`

**How Your Implementation Complies:**
Failure formatting includes explicit next-action guidance and exit codes to support actionable CLI recovery.

**Deviations (if any):**
None.

### Frontend Accessibility/Components/CSS/Responsive Standards
**File References:**
- `agent-os/standards/frontend/accessibility.md`
- `agent-os/standards/frontend/components.md`
- `agent-os/standards/frontend/css.md`
- `agent-os/standards/frontend/responsive.md`

**How Your Implementation Complies:**
Task scope is terminal-only CLI output with no web UI/component/CSS layer, so these standards are not directly applicable.

**Deviations (if any):**
None.

### Test Writing Best Practices
**File Reference:** `agent-os/standards/testing/test-writing.md`

**How Your Implementation Complies:**
Added five focused tests for critical CLI behavior and avoided exhaustive non-critical presentation permutations.

**Deviations (if any):**
None.

## Integration Points (if applicable)

### APIs/Endpoints
- None.

### External Services
- None.

### Internal Dependencies
- Uses `CommandResult` and `SessionCommandError` from `src/lecture_auto/session_service.py`.

## Known Issues & Limitations

### Issues
1. **Text Templates Are English-Only**
   - Description: Output strings are currently single-language.
   - Impact: Non-English users may need localization support.
   - Workaround: None in current scope.
   - Tracking: None.

### Limitations
1. **No Colorized Terminal Rendering**
   - Description: Formatting is plain text only.
   - Reason: Deterministic testability and minimal scope.
   - Future Consideration: Add optional ANSI styling behind a flag.

## Performance Considerations
Formatting is lightweight string composition and compact JSON serialization with negligible runtime cost.

## Security Considerations
No new security surfaces introduced; formatter only renders in-memory command data.

## Dependencies for Other Tasks
- Provides stable output contracts for Task Group 4 cross-feature test review and gap fill.

## Notes
Implementation remains strictly terminal-first and does not introduce any web UI behavior.
