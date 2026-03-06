# Task Breakdown: Lecture Session Capture Flow

## Overview
Total Tasks: 4
Assigned roles: database-engineer, api-engineer, ui-designer, testing-engineer

## Task List

### Data and Persistence Layer

#### Task Group 1: Session Metadata JSON Store
**Assigned implementer:** database-engineer
**Dependencies:** None

- [ ] 1.0 Complete metadata persistence layer
  - [ ] 1.1 Write 2-8 focused tests for session metadata store
    - Limit to 2-8 highly focused tests maximum
    - Test only critical behaviors: schema validation, required fields, deterministic ID/date persistence, atomic write/read
    - Skip exhaustive edge-case coverage
  - [ ] 1.2 Define standardized JSON schema for session metadata
    - Fields: `session_id`, `date`, `title`, `course`, `status`, `audio_file_path`, `timestamps`, `naming_pending`
    - Ensure deterministic serialization order and stable typing for test assertions
  - [ ] 1.3 Implement metadata read/write utilities
    - Use local filesystem path aligned with product structure (`config/` or equivalent app data path)
    - Include safe write strategy to avoid partial/corrupted files on interruption
  - [ ] 1.4 Add query helpers for history/detail access
    - List sessions in recent-first order
    - Fetch one session by `session_id`
  - [ ] 1.5 Ensure metadata layer tests pass
    - Run ONLY the 2-8 tests written in 1.1
    - Verify deterministic JSON output and load behavior
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 1.1 pass
- Session metadata is persisted in a standardized local JSON structure
- History/detail lookup helpers return correct data
- Persistence remains consistent after interrupted/failed writes

### Domain and Command Logic Layer

#### Task Group 2: Capture Lifecycle and Session Business Rules
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [ ] 2.0 Complete session/capture business logic
  - [ ] 2.1 Write 2-8 focused tests for lifecycle logic
    - Limit to 2-8 highly focused tests maximum
    - Test only critical behaviors: valid transitions, invalid transition rejection, failure mapping, status persistence
    - Skip exhaustive testing of all non-critical branches
  - [ ] 2.2 Implement capture state machine
    - States: `idle`, `recording`, `stopping`, `completed`, `failed`
    - Reject invalid transitions with clear, actionable messages
  - [ ] 2.3 Implement session create/start/stop/history/detail handlers
    - Commands covered: `session create`, `capture start`, `capture stop`, `session history`, `session detail <session_id>`
    - Integrate with metadata store from Task Group 1
  - [ ] 2.4 Implement output contract and error handling
    - Plain text as default output
    - `--json` produces one-line JSON output
    - Map dependency/device/runtime failures to non-zero exit codes and user-friendly guidance
  - [ ] 2.5 Implement naming fallback contract for downstream pipeline
    - Support optional `title`/`course` inputs
    - If missing, mark metadata for later transcript-based LLM naming in downstream specs
  - [ ] 2.6 Ensure business logic tests pass
    - Run ONLY the 2-8 tests written in 2.1
    - Verify lifecycle transitions and output/error contract
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 2.1 pass
- Lifecycle rules enforce valid transitions and reject invalid ones
- All required commands execute with consistent status persistence
- Plain text and one-line JSON output modes both work as specified

### CLI Interaction and UX Layer

#### Task Group 3: Terminal Command UX and Output Formatting
**Assigned implementer:** ui-designer
**Dependencies:** Task Group 2

- [ ] 3.0 Complete terminal interaction design for commands
  - [ ] 3.1 Write 2-8 focused tests for CLI UX formatting
    - Limit to 2-8 highly focused tests maximum
    - Test only critical CLI behavior: readable success text, actionable failure text, one-line JSON formatting
    - Skip exhaustive variations and non-critical cosmetic checks
  - [ ] 3.2 Define plain-text output templates per command
    - Success templates for create/start/stop/history/detail
    - Failure templates with next-action guidance
  - [ ] 3.3 Standardize one-line JSON output shape
    - Ensure per-command payload consistency for machine parsing
    - Ensure no multiline JSON output when `--json` is enabled
  - [ ] 3.4 Improve history/detail readability for terminal users
    - Provide concise session summaries in history output
    - Provide complete per-session facts in detail output by `session_id`
  - [ ] 3.5 Ensure CLI UX tests pass
    - Run ONLY the 2-8 tests written in 3.1
    - Verify text and JSON output format consistency
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 3.1 pass
- Terminal outputs are clear and actionable for core workflows
- `--json` always returns one-line, parseable output
- History/detail views are scannable and consistent

### Testing and Verification

#### Task Group 4: Feature Test Review and Critical Gap Fill
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1-3

- [ ] 4.0 Review feature tests and fill only critical gaps
  - [ ] 4.1 Review tests from Task Groups 1-3
    - Review the 2-8 tests written by database-engineer (Task 1.1)
    - Review the 2-8 tests written by api-engineer (Task 2.1)
    - Review the 2-8 tests written by ui-designer (Task 3.1)
    - Total existing tests: approximately 6-24 tests
  - [ ] 4.2 Identify critical coverage gaps for this spec only
    - Focus on create -> start -> stop -> history -> detail user workflow
    - Include critical failure paths listed in the spec
    - Do NOT assess unrelated product areas
  - [ ] 4.3 Add up to 10 additional strategic tests maximum
    - Add only if needed for missing critical workflow coverage
    - Prioritize integration between metadata persistence, lifecycle logic, and CLI output contract
    - Do NOT add exhaustive edge/performance test suites
  - [ ] 4.4 Run feature-specific tests only
    - Run ONLY tests from 1.1, 2.1, 3.1, and 4.3
    - Expected total: approximately 16-34 tests maximum
    - Do NOT run the entire application test suite

**Acceptance Criteria:**
- All feature-specific tests pass (approximately 16-34 tests total)
- Critical workflow and failure behaviors for this spec are covered
- No more than 10 additional tests are added in 4.3
- Validation remains limited to this spec's scope

## Execution Order

Recommended implementation sequence:
1. Data and Persistence Layer (Task Group 1)
2. Domain and Command Logic Layer (Task Group 2)
3. CLI Interaction and UX Layer (Task Group 3)
4. Testing and Verification (Task Group 4)
