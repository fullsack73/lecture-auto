# Task Breakdown: LLM-Based Transcript Refinement

## Overview
Total Tasks: 3 Task Groups
Assigned roles: api-engineer, testing-engineer

## Task List

### Configuration and LLM Adapter Layer

#### Task Group 1: Core Adapters and Config
**Assigned implementer:** api-engineer
**Dependencies:** None

- [ ] 1.0 Complete Configuration and LLM Adapter
  - [ ] 1.1 Write 2-8 focused tests for Config/Adapter
    - Test Gemini LLM integration interface and configuration validation
    - Limit to core tests (e.g., config error on missing keys, adapter method signature)
  - [ ] 1.2 Update Config Structure
    - Create/modify config dataclass (e.g., `LLMConfig`) accommodating a Gemini API key.
    - Add validation similar to `STTConfig`.
  - [ ] 1.3 Create `LLMProviderAdapter` Interface
    - Define methods for transcript refinement.
    - Incorporate topic context parameters and multi-language support info.
  - [ ] 1.4 Create `GeminiLLMAdapter` Implementation
    - Integrate with the Gemini API to handle prompt execution.
    - Implement the chunking logic to pass topic context effectively across segments.
    - Handle API failures (timeouts, auth) gracefully following current exception patterns.
  - [ ] 1.5 Ensure Adapter tests pass
    - Run ONLY the newly created config/adapter tests.

**Acceptance Criteria:**
- The 2-8 module tests pass.
- `LLMConfig` validates properly.
- `GeminiLLMAdapter` connects and properly processes mocked input.

### Business Logic and CLI Layer

#### Task Group 2: Refinement Service and Commands
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [ ] 2.0 Complete CLI and Domain Service logic
  - [ ] 2.1 Write 2-8 focused tests for Refinement Service / CLI command
    - Test the `refine` command fallback behavior (edited vs raw missing).
    - Test that proper overwrite behavior occurs.
  - [ ] 2.2 Update `SessionService` (or domain logic)
    - Add methods to locate target file (default latest edited, fallback/flags for raw).
    - Implement file overwrite logic (save as `{session_id}-edited.md`).
    - Connect the LLM Adapter for processing the transcript.
  - [ ] 2.3 Create `refine` CLI Command
    - Add a Typer command `refine` accepting `<session-id>` and `--raw` flag.
    - Format output using the `CommandResult` pattern structure from existing codebase.
    - Ensure appropriate messaging and error handling via `SessionCommandError`.
  - [ ] 2.4 Ensure Service and CLI tests pass
    - Run ONLY the newly created 2-8 tests for this group.

**Acceptance Criteria:**
- The 2-8 logic tests pass.
- CLI command runs cleanly.
- Outputs are saved properly according to file path strategies.

### Testing and Validation

#### Task Group 3: Test Review & Gap Analysis
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1-2

- [ ] 3.0 Review existing tests and fill critical gaps only
  - [ ] 3.1 Review tests from Task Groups 1-2
    - Evaluate adapter tests and domain service tests.
    - Total existing tests expected approximately 4-16.
  - [ ] 3.2 Analyze test coverage gaps for THIS feature only
    - Focus on finding missed edge cases like: missing transcript scenarios, large transcript chunking limits.
  - [ ] 3.3 Write up to 10 additional strategic tests maximum
    - Focus on end-to-end simulation of a `refine` command.
    - Test complete CLI-to-Storage refinement chain.
  - [ ] 3.4 Run feature-specific tests only
    - Run ONLY tests related to the transcript refinement spec.
    - Verify critical workflows pass.

**Acceptance Criteria:**
- All feature-specific tests pass.
- Critical user workflows (end-to-end refinement) are completely covered.
- No more than 10 tests added independently by testing-engineer.

## Execution Order

Recommended implementation sequence:
1. Configuration and LLM Adapter Layer (Task Group 1)
2. Business Logic and CLI Layer (Task Group 2)
3. Testing and Validation (Task Group 3)
