# Task Breakdown: Remaining Lecture Session Capture Flow Features

## Overview
Total Tasks: 4
Assigned roles: database-engineer, api-engineer, ui-designer, testing-engineer

## Task List

### Persistence and Recording Artifacts

#### Task Group 1: Recording Artifact Persistence and Metadata Consistency
**Assigned implementer:** database-engineer
**Dependencies:** None

- [x] 1.0 Complete recording artifact persistence updates
  - [x] 1.1 Write 2-8 focused tests for recording metadata persistence
    - Limit to 2-8 highly focused tests maximum
    - Test only critical behaviors: session-id based file naming, metadata consistency after capture start/stop, interrupted-write safety
    - Skip exhaustive edge-case and non-critical schema tests already covered in previous spec
  - [x] 1.2 Validate recording path conventions
    - Ensure persisted audio path follows `recordings/{session_id}.*`
    - Keep compatibility with existing metadata schema and deterministic serialization
  - [x] 1.3 Add persistence safeguards for runtime capture integration
    - Keep atomic metadata writes during active capture lifecycle updates
    - Ensure failed capture finalization does not leave ambiguous metadata
  - [x] 1.4 Ensure Task Group 1 tests pass
    - Run ONLY the tests written in 1.1
    - Verify deterministic load/history/detail persistence behavior
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 1.1 pass
- Audio file path persistence follows session-id-only naming rules
- Metadata remains consistent after successful and failed capture transitions
- Persistence remains safe against partial writes

### Capture Runtime and Command Logic

#### Task Group 2: Real Device Capture Start/Stop Integration
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [x] 2.0 Complete real capture runtime integration
  - [x] 2.1 Write 2-8 focused tests for capture runtime orchestration
    - Limit to 2-8 highly focused tests maximum
    - Test only critical behaviors: start/stop orchestration, process lifecycle handoff, failure mapping contract, status persistence
    - Skip exhaustive testing of every runtime branch
  - [x] 2.2 Implement capture runtime adapter boundary
    - Integrate FFmpeg + PyAudio/SoundCard execution path for real device recording
    - Isolate runtime interactions behind a testable adapter interface
  - [x] 2.3 Wire adapter into `capture start` / `capture stop`
    - Start real recording and persist active capture context
    - Stop/finalize recording and persist completed/failed state deterministically
  - [x] 2.4 Preserve command output/error contracts
    - Keep existing plain text output shape
    - Keep one-line JSON `--json` contract
    - Keep actionable error mapping with explicit non-zero exit codes
  - [x] 2.5 Ensure Task Group 2 tests pass
    - Run ONLY the tests written in 2.1
    - Verify runtime integration and failure-path behavior
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 2.1 pass
- `capture start` and `capture stop` execute real recording lifecycle integration
- Existing output and error contracts remain stable
- Failure scenarios (dependency, device, permission, interruption, write failures) remain actionable

### Terminal UX Contract Stability

#### Task Group 3: CLI Output Stability for Real Capture Flow
**Assigned implementer:** ui-designer
**Dependencies:** Task Group 2

- [x] 3.0 Confirm terminal UX contract stability
  - [x] 3.1 Write 2-8 focused tests for CLI output stability
    - Limit to 2-8 highly focused tests maximum
    - Test only critical CLI behavior: unchanged success/failure templates and one-line JSON in real-capture flows
    - Skip exhaustive cosmetic or formatting permutations
  - [x] 3.2 Verify plain-text templates remain consistent
    - Ensure create/start/stop/history/detail outputs stay readable and actionable
    - Avoid unnecessary wording drift unless required by new runtime behavior
  - [x] 3.3 Verify one-line JSON output remains parseable
    - Ensure no multiline JSON output when `--json` is enabled
    - Ensure command payload shape consistency after runtime integration
  - [x] 3.4 Ensure Task Group 3 tests pass
    - Run ONLY the tests written in 3.1
    - Verify text/JSON contract consistency
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2-8 tests written in 3.1 pass
- Terminal output contract remains stable and readable
- JSON output remains one-line and parseable for all required commands

### Testing and Real Device Validation

#### Task Group 4: Feature Test Review and Manual Device Validation Guide
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1-3

- [x] 4.0 Review tests and fill critical gaps for this spec only
  - [x] 4.1 Review tests from Task Groups 1-3
    - Review the 2-8 tests written by database-engineer (Task 1.1)
    - Review the 2-8 tests written by api-engineer (Task 2.1)
    - Review the 2-8 tests written by ui-designer (Task 3.1)
    - Total existing tests: approximately 6-24 tests
  - [x] 4.2 Identify critical coverage gaps for Roadmap item 1 residual scope
    - Focus only on `session create -> capture start -> capture stop -> history -> detail`
    - Include critical runtime failure behavior in spec scope only
    - Do NOT assess unrelated roadmap features
  - [x] 4.3 Add up to 10 additional strategic tests maximum
    - Add only if needed for missing critical integration behaviors
    - Prioritize metadata + runtime + CLI contract integration points
    - Keep deterministic automated tests mock-based
  - [x] 4.4 Add manual real-device verification procedure
    - Document commands, prerequisites, and expected outcomes for local hardware verification
    - Include troubleshooting steps for dependency/device/permission failures
  - [x] 4.5 Run feature-specific tests only
    - Run ONLY tests from 1.1, 2.1, 3.1, and 4.3
    - Expected total: approximately 16-34 tests maximum
    - Do NOT run the entire application test suite

**Acceptance Criteria:**
- All feature-specific tests pass (approximately 16-34 tests total)
- No more than 10 additional tests are added in 4.3
- Manual real-device verification steps are documented and executable
- Validation remains limited to this spec's scope

## Execution Order

Recommended implementation sequence:
1. Recording Artifact Persistence and Metadata Consistency (Task Group 1)
2. Real Device Capture Start/Stop Integration (Task Group 2)
3. CLI Output Stability for Real Capture Flow (Task Group 3)
4. Feature Test Review and Manual Device Validation Guide (Task Group 4)
