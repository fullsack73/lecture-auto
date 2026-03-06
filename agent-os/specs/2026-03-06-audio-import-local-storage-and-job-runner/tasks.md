# Task Breakdown: Audio Import, Local Storage, and Job Runner

## Overview
Total Tasks: 4 task groups
Assigned roles: database-engineer, api-engineer, ui-designer, testing-engineer

## Task List

### Storage and Metadata Layer

#### Task Group 1: Audio Attachment Metadata and Persistence
**Assigned implementer:** database-engineer
**Dependencies:** None

- [ ] 1.0 Complete storage and metadata updates for audio attachment
  - [ ] 1.1 Write 2-8 focused tests for metadata schema and persistence updates
    - Cover only critical behavior: supported path conventions, job status fields, retry counter persistence, duplicate marker checks
    - Reuse existing test style from `tests/test_session_metadata_store.py`
  - [ ] 1.2 Extend metadata schema for import job lifecycle and retry tracking
    - Add fields for `job_status`, `job_attempts`, `job_timestamps`, `job_error_code` (if needed)
    - Keep deterministic structure and compatibility with existing required fields pattern
  - [ ] 1.3 Add deterministic audio storage naming/path behavior for imported files
    - Follow existing `recordings/{session_id}.*` convention and structured naming policy
    - Ensure collision-safe deterministic naming for imported assets
  - [ ] 1.4 Implement duplicate-audio blocking checks at persistence boundary
    - Define duplicate rule for same session + same logical audio target
    - Persist enough metadata to enforce this rule consistently
  - [ ] 1.5 Ensure storage layer tests pass
    - Run ONLY tests written in 1.1
    - Do NOT run full test suite

**Acceptance Criteria:**
- 2-8 focused tests from 1.1 pass
- Metadata persists lifecycle/retry fields deterministically
- Duplicate audio writes are blocked by storage/business constraints
- Path/naming conventions remain deterministic and testable

### Command and Business Logic Layer

#### Task Group 2: Import Command Flow, Validation, and Retry Rules
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [ ] 2.0 Complete command/business logic for audio import job runner
  - [ ] 2.1 Write 2-8 focused tests for command flow and lifecycle transitions
    - Cover critical paths: session lookup, extension validation, lifecycle transitions, retry-only-on-failed, retry max=3
    - Reuse conventions from `tests/test_session_business_rules.py`
  - [ ] 2.2 Add import command use-case requiring `session_id` + local audio input
    - Scope to pre-existing audio upload only
    - Reuse `SessionService` session resolution and error contract patterns
  - [ ] 2.3 Implement file extension validation for supported types (`.wav`, `.mp3`)
    - Reject unsupported types with actionable errors and guidance
  - [ ] 2.4 Implement job runner state machine and transitions
    - Include `queued`, `running`, `succeeded`, `failed`, `canceled`
    - Enforce invalid transition rejection with actionable guidance
  - [ ] 2.5 Implement retry policy
    - Failed jobs only
    - Max retry count: 3
    - Reject retry request for non-failed jobs or attempts > 3
  - [ ] 2.6 Ensure business logic tests pass
    - Run ONLY tests written in 2.1
    - Do NOT run full test suite

**Acceptance Criteria:**
- 2-8 focused tests from 2.1 pass
- Import command requires `session_id` and audio path
- Unsupported extensions are rejected with clear error guidance
- Lifecycle states and transitions behave as specified including `canceled`
- Retry policy enforces failed-only and max 3 attempts

### CLI Output and UX Contract

#### Task Group 3: Terminal Progress and Result Formatting
**Assigned implementer:** ui-designer
**Dependencies:** Task Group 2

- [ ] 3.0 Complete CLI output contract for import/job commands
  - [ ] 3.1 Write 2-8 focused tests for CLI output formatting
    - Validate text output and JSON-line output for success/failure/progress summaries
    - Reuse formatting style from `tests/test_cli_output_formatting.py`
  - [ ] 3.2 Add progress output sections for import/job lifecycle
    - Include started_at, ended_at, current stage, final status, and next action guidance
    - Reuse existing `cli_output.py` wording and structure patterns
  - [ ] 3.3 Add actionable error output for validation and retry failures
    - Keep message + guidance + exit code contract consistent
  - [ ] 3.4 Ensure CLI output tests pass
    - Run ONLY tests written in 3.1
    - Do NOT run full test suite

**Acceptance Criteria:**
- 2-8 focused tests from 3.1 pass
- Output is deterministic and concise for pytest assertions
- Success/failure/progress messages include required fields and guidance
- Error output remains user-friendly and contract-consistent

### Feature Test Review and Gap Fill

#### Task Group 4: Focused End-to-End Test Coverage Review
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1-3

- [ ] 4.0 Review feature tests and fill only critical gaps
  - [ ] 4.1 Review tests created in Task Groups 1-3
    - Validate that each group kept 2-8 focused tests
    - Validate they test only core feature behavior
  - [ ] 4.2 Identify critical workflow gaps for this spec only
    - Focus on attach->persist->trigger->status->retry flow
    - Exclude full-application coverage analysis
  - [ ] 4.3 Add up to 10 strategic tests maximum if critical gaps exist
    - Prioritize integration of validation + state + output contract
    - Avoid exhaustive edge-case matrix
  - [ ] 4.4 Run only feature-specific tests
    - Run tests from 1.1, 2.1, 3.1 and optional 4.3 additions
    - Expected total around 16-34 tests
    - Do NOT run full suite

**Acceptance Criteria:**
- Feature-specific tests pass
- Additional tests are max 10 and only for critical gaps
- Coverage is focused on core workflows for roadmap item 2
- No exhaustive or full-suite testing requirement introduced

## Execution Order

Recommended implementation sequence:
1. Storage and Metadata Layer (Task Group 1)
2. Command and Business Logic Layer (Task Group 2)
3. CLI Output and UX Contract (Task Group 3)
4. Feature Test Review and Gap Fill (Task Group 4)
