# Task Breakdown: Deepgram and Local Model STT

## Overview
Total Tasks: 3
Assigned roles: database-engineer, api-engineer, testing-engineer

## Task List

### Data Modeling & Configuration Layer

#### Task Group 1: Config Models Modification
**Assigned implementer:** database-engineer
**Dependencies:** None

- [x] 1.0 Complete configuration layer updates
  - [x] 1.1 Write 2-8 focused tests for `STTConfig` and `STTResult` changes
    - Test validation logic for new mode properties (e.g. language, diarization, deepgram provider)
  - [x] 1.2 Update `STTConfig` in `src/lecture_auto/stt_config.py`
    - Add `language` field
    - Add `diarization` bool field
    - Expand provider validations (e.g. deepgram API)
  - [x] 1.3 Update `STTResult` in `src/lecture_auto/stt_runtime.py`
    - Add fields to support storing speaker diarization mapping timestamps
  - [x] 1.4 Ensure config layer tests pass
    - Run ONLY the 2-8 tests written in 1.1

**Acceptance Criteria:**
- The 2-8 config validation tests pass.
- `STTConfig` handles newly required properties.
- `STTResult` can accept diarized markdown format properties.

### API & Business Logic Layer

#### Task Group 2: STT Adapters and CLI Implementations
**Assigned implementer:** api-engineer
**Dependencies:** Task Group 1

- [x] 2.0 Complete STT business logic
  - [x] 2.1 Write 2-8 focused tests for STT Adapters and CLI interactions
    - Test that `lecture config set stt-language` works.
    - Mock Deepgram SDK test for error handling.
    - Mock faster-whisper local adapter initialization test.
  - [x] 2.2 Create `DeepgramSTTRuntimeAdapter`
    - Implement `transcribe` built on top of `deepgram-sdk`
    - Output `STTResult` with Speaker Diarization into markdown format
    - Map network exceptions to `STTTransientNetworkError` and `STTProviderAuthError`
  - [x] 2.3 Create `FasterWhisperSTTRuntimeAdapter`
    - Implement `transcribe` locally via `faster-whisper` package
    - Handle multi-language large-v3 loading conditionally based on config
  - [x] 2.4 Update CLI Commands
    - Register commands for setting `stt-language` and `stt-api-key`
  - [x] 2.5 Ensure API/Logic layer tests pass
    - Run ONLY the 2-8 tests written in 2.1

**Acceptance Criteria:**
- The 2-8 logic tests pass.
- Deepgram adapter outputs correctly formatted diarization markdown.
- CLI properly persists `STTConfig` changes.

### Testing Layer

#### Task Group 3: Test Review & Gap Analysis
**Assigned implementer:** testing-engineer
**Dependencies:** Task Groups 1-2

- [x] 3.0 Review existing tests and fill critical gaps only
  - [x] 3.1 Review tests from Task Groups 1-2
    - Review the 2-8 tests written by database-engineer (Task 1.1)
    - Review the 2-8 tests written by api-engineer (Task 2.1)
  - [x] 3.2 Analyze test coverage gaps for STT feature only
    - Focus on edge-case error mapping (e.g. invalid auth formats, malformed SDK responses)
    - Focus on fallback mechanics if supported
  - [x] 3.3 Write up to 10 additional strategic tests maximum
    - Implement tests filling identified coverage gaps in STT flow only
  - [x] 3.4 Run STT-specific tests only
    - Run ONLY tests related to this spec's feature (tests from 1.1, 2.1, 3.3)

**Acceptance Criteria:**
- All STT-specific tests pass.
- Critical STT runtime workflows are adequately covered.
- No more than 10 additional tests added.
