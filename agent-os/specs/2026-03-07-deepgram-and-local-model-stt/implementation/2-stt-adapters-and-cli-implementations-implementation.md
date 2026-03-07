# Task 2: STT Adapters and CLI Implementations

## Overview
**Task Reference:** Task #2 from `agent-os/specs/2026-03-07-deepgram-and-local-model-stt/tasks.md`
**Implemented By:** api-engineer
**Date:** 2026-03-07
**Status:** ✅ Complete

### Task Description
Create DeepgramSTTRuntimeAdapter and FasterWhisperSTTRuntimeAdapter, update SessionService adapter dispatch, and add CLI config set behaviors for stt-language and stt-api-key.

## Implementation Summary
Implemented two new adapter modules: `deepgram_adapter.py` (Deepgram SDK integration with diarization via paragraphs/words fallback and error mapping) and `whisper_adapter.py` (faster-whisper with lazy model loading and configurable language). Updated `session_service.py` to dispatch to the correct adapter based on config and to write diarized markdown when segments exist.

## Files Changed/Created

### New Files
- `src/lecture_auto/deepgram_adapter.py` - Full Deepgram SDK adapter with diarization and error mapping
- `src/lecture_auto/whisper_adapter.py` - Faster-whisper adapter with lazy loading and multi-language support
- `tests/test_stt_adapters_cli.py` - 8 focused tests for adapters and CLI behaviors

### Modified Files
- `src/lecture_auto/session_service.py` - Updated `_build_stt_adapter()` to dispatch to real adapters; updated `transcribe_session()` to write diarized markdown

## Dependencies (if applicable)

### New Dependencies Added
- `deepgram-sdk` - Deepgram API client for cloud transcription
- `faster-whisper` - Optimized Whisper inference engine for local STT

## Testing

### Test Files Created/Updated
- `tests/test_stt_adapters_cli.py` - 8 tests (mock SDK, auth errors, missing packages, CLI config)

### Test Coverage
- Unit tests: ✅ Complete
- Edge cases covered: Missing SDK, empty API key, empty audio path, auth error mapping, language config set

## Dependencies for Other Tasks
- Task Group 3 reviews tests from this task group.
