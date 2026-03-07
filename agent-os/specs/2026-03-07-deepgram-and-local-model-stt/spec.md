# Specification: Deepgram and Local Model STT

## Goal
Implement Deepgram API and local Whisper STT capabilities with speaker diarization and CLI configuration, allowing dynamic switching between API and local execution modes.

## User Stories
- As a user, I want to use Deepgram API with speaker diarization so that I get accurate transcripts with speaker separation.
- As a user, I want to run a local Whisper STT model (large-v3 or higher via faster-whisper) so that I can transcribe audio locally without external API dependencies.
- As a user, I want to configure the STT language via CLI `lecture config set stt-language` so that I can override auto-detection when needed.
- As a user, I want to configure the STT API key via CLI `lecture config set stt-api-key [key]` so that credentials are securely stored locally.

## Core Requirements
### Functional Requirements
- Integrate `deepgram-sdk` for Deepgram API mode with speaker diarization support.
- Integrate `faster-whisper` for local STT mode, using large-v3 scale models and multi-language support.
- Extend `STTConfig` to add language setting, API provider configuration (e.g. Deepgram), and speaker diarization toggle.
- Add CLI commands to set the language (e.g., `lecture config set stt-language english`) and api-key.
- Update `STTResult` to include speaker diarization information and output as formatted Markdown.

### Non-Functional Requirements
- Maintain stability and robust error handling (`STTRuntimeError`, and subclasses) for network/provider errors using the Deepgram SDK and Faster-Whisper.
- Efficient memory and performance using `faster-whisper` over standard `whisper`.

## Visual Design
- N/A (CLI and backend logic)

## Reusable Components
### Existing Code to Leverage
- Components: `STTConfig`, `STTResult`
- Services: `STTRuntimeAdapter`, `APISTTRuntimeAdapter`, `LocalSTTRuntimeAdapter`
- Patterns: Error mapping semantics and validation flows from existing config/runtime modules.

### New Components Required
- Deepgram adapter implementation built on top of `STTRuntimeAdapter` integrating the `deepgram-sdk`.
- Faster-Whisper adapter implementation for local models.
- Markdown formatting logic for generating transcript files with speaker diarization timestamps.
- CLI subcommands for language and dictation.

## Technical Approach
- Database: N/A - configuration persists via local file.
- API: Use `deepgram-sdk` for cloud transcription, handling callbacks and standardizing network error classes (`STTTransientNetworkError`, `STTProviderAuthError`).
- Frontend: CLI interface to input parameters mapped to `STTConfig`.
- Testing: Mock Deepgram SDK responses and local Whisper transcription results. Test configuration behaviors and STT provider fallbacks.

## Out of Scope
- GPU/CUDA container setup or automated environment troubleshooting.
- Installer scripts for external OS-level driver dependencies.
- Deepgram API or Whisper model caching beyond standard libraries.

## Success Criteria
- Accurately runs transcriptions via the Deepgram API SDK, producing Markdown with speaker diarization.
- Accurately runs transcriptions locally via `faster-whisper`.
- CLI commands successfully alter in-memory/disk configuration and redirect STT strategies transparently.
