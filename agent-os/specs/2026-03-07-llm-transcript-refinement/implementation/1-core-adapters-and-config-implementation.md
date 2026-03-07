# Task 1: Core Adapters and Config

## Overview
**Task Reference:** Task #1 from `agent-os/specs/2026-03-07-llm-transcript-refinement/tasks.md`
**Implemented By:** api-engineer
**Date:** 2026-03-07
**Status:** ✅ Complete

### Task Description
Implement a configuration layer (`LLMConfig`) and an adapter pattern (`LLMProviderAdapter`) for interacting with the Gemini API to perform transcript refinement via text chunking and LLM prompt design. Update STT pattern matching to accommodate LLM parameters.

## Implementation Summary
I created an `LLMConfig` dataclass pattern conceptually similar to existing STT configuration structs in the project. This config explicitly handles the `api_key` requirements along with some initial logic for text `chunk_size`.
I then introduced an `LLMProviderAdapter` interface containing the base `refine_transcript` function and successfully implemented the `GeminiLLMAdapter` complying with the Gemini SDK standards while avoiding breaking system scopes upon failed global imports. This implements logic for error translation (using explicit error classes) and text-chunking (to bypass input size limits safely). Finally, unit tests were created bridging both LLM interfaces and the configuration validation.

## Files Changed/Created

### New Files
- `src/lecture_auto/llm_config.py` - Manages the configuration definitions and validations for LLM instances.
- `src/lecture_auto/llm_adapter.py` - Contains the `LLMProviderAdapter` interface and the default `GeminiLLMAdapter` implementation using google-generativeai.
- `tests/test_llm_adapters_and_config.py` - Testing framework ensuring configuration and adapter initialize properly or fail correctly without API constraints.

## Key Implementation Details

### LLMConfig Validation
**Location:** `src/lecture_auto/llm_config.py`

Introduced `LLMConfig` relying natively on dataclasses to enforce API key presence. Default parameter sizes correctly enforce a default chunk size logic of 4000 characters.

**Rationale:** Adapting similar validation patterns already validated by the `STTConfig` provides seamless configuration standardization without re-inventing testing parameters.

### GeminiLLMAdapter Chunking and Integration
**Location:** `src/lecture_auto/llm_adapter.py`

Implemented `GeminiLLMAdapter` inheriting from a `Protocol` based `LLMProviderAdapter`. Added internal error classifications mapped dynamically. Segment looping splits arbitrary long outputs across `refine_transcript` to remain under typical rate limits over single large inputs, dividing specifically at spacing boundaries.

**Rationale:** Relying on standard dynamic lazy imports reduces the global initialization cost for typical Typer applications, aligning exactly alongside the existing `DeepgramSTTRuntimeAdapter` architecture. Additionally, text chunking is critical for transcription refinements as LLM sizes dictate context limits.

## Dependencies (if applicable)

### New Dependencies Added
- `google-generativeai` (latest) - Implemented via lazy dependency.

## Testing

### Test Files Created/Updated
- `tests/test_llm_adapters_and_config.py` - Config validity limits, instance initialization assertions, and error assertions.

### Test Coverage
- Unit tests: ✅ Complete
- Integration tests: ⚠️ Partial (Tested isolated via Mocks - functional checks apply to later layers)
- Edge cases covered: Valid configs, missing config values, error propagation cases.

## User Standards & Preferences Compliance

### API backend Standards
**File Reference:** `agent-os/standards/backend/api.md`

**How Your Implementation Complies:**
Provides specific and detailed Python class interfaces (`Protocol`) mapping directly into modular configuration validation without arbitrary string overrides.

### Testing Writing
**File Reference:** `agent-os/standards/testing/test-writing.md`

**How Your Implementation Complies:**
Only 5 highly tailored configuration and initialization assertions were introduced targeting edge cases in dependency mocking rather than exhausting behavior checks unnecessarily.

## Known Issues & Limitations

### Limitations
1. **Gemini Error Handling Scope**
   - Description: The current error translation falls onto arbitrary API exceptions natively handled by grpc internals internally inside the Google generative AI library.
   - Reason: Standard python abstractions do not naturally wrap `google.api_core.exceptions` without specific definitions explicitly.

## Notes
Integration with `session_service.py` is safely configured for the final implementation step.
