# Task Breakdown: STT Pipeline with Provider Selection

## Overview
Total Tasks: 4
Assigned roles: database-engineer, api-engineer, ui-designer, testing-engineer

## Task List

### Data and Persistence Layer

#### Task Group 1: Transcript Metadata and Local Artifact Persistence
**Assigned implementer:** database-engineer
**Dependencies:** None

- [x] 1.0 Complete transcript metadata and persistence foundation
  - [x] 1.1 Write 2-8 focused tests for transcript metadata schema and latest-artifact persistence
    - Cover required fields, deterministic transcript path convention, and latest-only replacement behavior
    - Skip exhaustive edge-case matrix beyond critical path
  - [x] 1.2 Extend session metadata schema for transcription tracking
    - Add fields for transcript path, transcription status/stage, retry count, and error category
    - Reuse normalization/type validation pattern from `session_metadata_store.py`
  - [x] 1.3 Add transcript path helper(s) with session-scoped deterministic naming
    - Keep naming compatible with existing `recordings/{session_id}...` style conventions
  - [x] 1.4 Implement latest raw transcript replacement semantics
    - Ensure new transcription for same session replaces prior raw transcript metadata/artifact target
  - [x] 1.5 Ensure persistence layer tests pass
    - Run ONLY tests written in 1.1
    - Do NOT run full test suite

**Acceptance Criteria:**
- The 2-8 tests written in 1.1 pass
- Metadata validation accepts valid transcript fields and rejects invalid types
- Transcript path generation is deterministic and session-scoped
- Latest raw transcript behavior is enforced per session

### Service and Command Orchestration

#### Task Group 2: STT Mode Selection, Preflight, and Retry-Orchestrated Transcription
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [x] 2.0 Complete transcription orchestration flow
  - [x] 2.1 Write 2-8 focused tests for mode selection, preflight checks, retry policy, and session-scope enforcement
    - Cover default mode `api`, local/api mode branching, fail-fast checks, and transient API retry cap (2)
    - Include assertion that non-session file-path transcription is rejected
  - [x] 2.2 Add STT configuration contract
    - Support `local` and `api` modes only
    - Set default mode to `api`
    - Validate provider/model prerequisites before run
  - [x] 2.3 Implement transcription runtime adapter contract and orchestrator
    - Add local-model and API-provider adapter interfaces/implementations
    - Reuse error mapping contract style from `SessionCommandError` patterns
  - [x] 2.4 Add bounded retry behavior for API transient failures only
    - Max 2 automatic retries with explicit retry-stage reporting
    - Local mode failures return immediate actionable guidance without auto-retry
  - [x] 2.5 Integrate session service command flow for transcription
    - Require existing session with attached audio
    - Persist transcription result path and status updates
  - [x] 2.6 Ensure orchestration tests pass
    - Run ONLY tests written in 2.1
    - Do NOT run full test suite

**Acceptance Criteria:**
- The 2-8 tests written in 2.1 pass
- Transcription runs only against session-linked audio
- Mode selection supports only `local`/`api` and defaults to `api`
- Preflight checks fail fast with actionable errors
- API transient retry behavior is capped at 2; local mode has no auto-retry

### CLI Experience Layer

#### Task Group 3: Transcription Stage Output and Actionable Error UX
**Assigned implementer:** ui-designer
**Dependencies:** Task Group 2

- [x] 3.0 Complete terminal UX for transcription flow
  - [x] 3.1 Write 2-8 focused tests for CLI text/json output of transcription stage progress and error guidance
    - Cover stage rendering and final transcript path in both human-readable and JSON-line output
    - Keep tests focused on critical formatting contracts only
  - [x] 3.2 Add transcription success output formatter entries
    - Reuse existing formatting style from `cli_output.py`
    - Include ordered stage markers: preflight, mode/provider init, transcribing, write complete
  - [x] 3.3 Add transcription error output mapping for required categories
    - Configuration, provider auth, network/transient, audio format/decoding
    - Provide explicit next-action guidance per category
  - [x] 3.4 Ensure progress payload structure remains deterministic and stable for tests
    - Include attempt/retry information for API mode runs
  - [x] 3.5 Ensure CLI UX tests pass
    - Run ONLY tests written in 3.1
    - Do NOT run full test suite

**Acceptance Criteria:**
- The 2-8 tests written in 3.1 pass
- CLI output presents clear transcription stages and final output path
- Error outputs are actionable and category-consistent
- JSON output remains single-line and parseable

### Testing

#### Task Group 4: Feature-Focused Test Review and Gap Fill
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1-3

- [x] 4.0 Review feature tests and fill only critical gaps
  - [x] 4.1 Review tests added in 1.1, 2.1, and 3.1
    - Confirm critical workflow coverage across persistence, orchestration, and CLI output
  - [x] 4.2 Identify missing critical workflow assertions for roadmap item 3 only
    - Focus on session-only enforcement, retry cap behavior, and latest transcript replacement
  - [x] 4.3 Add up to 10 additional strategic tests maximum
    - Prioritize integration points and end-to-end command workflow for this feature
    - Do NOT add exhaustive edge-case suites
  - [x] 4.4 Run feature-specific tests only
    - Run tests from 1.1, 2.1, 3.1, and 4.3
    - Do NOT run full test suite

**Acceptance Criteria:**
- All feature-specific tests pass
- Additional tests by testing-engineer are 10 or fewer
- Coverage addresses critical roadmap item 3 workflows only
- No broad non-feature test expansion is introduced

## Execution Order

Recommended implementation sequence:
1. Data and Persistence Layer (Task Group 1)
2. Service and Command Orchestration (Task Group 2)
3. CLI Experience Layer (Task Group 3)
4. Testing (Task Group 4)
