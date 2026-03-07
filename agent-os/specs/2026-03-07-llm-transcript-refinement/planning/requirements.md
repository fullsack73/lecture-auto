# Spec Requirements: LLM-Based Transcript Refinement

## Initial Description
LLM-Based Transcript Refinement — Add optional transcript cleanup that improves spacing, wording, and typo correction while preserving lecture meaning. Save before/after transcript outputs as separate local files so users can compare and choose the final input for summarization.

## Requirements Discussion

### First Round Questions

**Q1:** I assume the refinement will be triggered via a Typer CLI command like `lecture-auto refine <session-id>`. Is that correct, or should it be integrated into an existing pipeline command (e.g., automatically chaining after transcription)?
**Answer:** Yes, it must be triggered explicitly via a `refine` command. It should not auto-chain after transcription.

**Q2:** I'm thinking the LLM provider should follow the existing provider-agnostic adapter pattern (similar to `deepgram_adapter.py` / `whisper_adapter.py` for STT) where users configure an OpenAI-compatible API endpoint and key. Should we also support local LLM models (e.g., via Ollama), or is API-only sufficient for the initial version?
**Answer:** For the initial version, only Gemini API should be supported. No local LLM support needed yet.

**Q3:** I assume the refinement process should work on the "raw" transcript output file from the STT pipeline. Should users also be able to refine an "edited" transcript (from roadmap item #4's edit workflow)?
**Answer:** The refine operation should target the latest edited transcript by default. Raw transcript should only be refined when: (a) the `--raw` flag is provided, or (b) no edited transcript exists.

**Q4:** For the "before/after" comparison: I assume we save the original transcript as-is and create a new `*_refined.md` file alongside it. Is that correct, or do you prefer a different naming/folder convention?
**Answer:** No separate refined file needed. The refined output should overwrite the existing edited transcript. If refining a raw transcript (no edited version exists), the refined result becomes the new edited version (saved as `{session_id}-edited.md`).

**Q5:** I assume the LLM prompt should focus on: (a) fixing typos/spelling, (b) improving spacing and punctuation, (c) correcting awkward wording, and (d) preserving the original meaning/terminology. Should we also consider paragraph/section structuring, or keep it strictly at the sentence level?
**Answer:** Sentence-level refinement only. Paragraph/section-level structural changes are out of scope for now.

**Q6:** For long transcripts, should we implement chunking (splitting the transcript into segments for LLM processing and then reassembling)? Is there a maximum lecture duration we should plan for?
**Answer:** Yes, chunking is required. No maximum length limit — should handle any length. Important: the lecture topic/context (what the lecture is about) should be stored and passed as context to each chunk's LLM call so refinement stays semantically consistent across chunks.

**Q7:** Should there be a `--dry-run` or preview mode where users can see a sample of refinements before committing to the full processing?
**Answer:** No. Not needed for now.

**Q8:** Is there anything specific you'd like to exclude from this feature's scope?
**Answer:** Multi-session batch processing is out of scope. Multi-language support IS strictly in scope.

### Existing Code to Reference

**Similar Features Identified:**
- Feature: STT Adapter Pattern - Path: `src/lecture_auto/deepgram_adapter.py`
  - Reference for building the Gemini LLM adapter (API client initialization, error handling, provider-specific logic)
- Feature: STT Adapter Pattern - Path: `src/lecture_auto/whisper_adapter.py`
  - Reference for local adapter structure and interface consistency
- Feature: Session Service - Path: `src/lecture_auto/session_service.py`
  - Reference for session/file management, transcript path resolution, CommandResult pattern, error handling via SessionCommandError
- Feature: STT Configuration - Path: `src/lecture_auto/stt_config.py`
  - Reference for configuration dataclass pattern (LLM config should follow similar pattern with validation)
- Feature: CLI Output - Path: `src/lecture_auto/cli_output.py`
  - Reference for terminal output formatting and user-facing messages

**Key Code Patterns Observed:**
- Transcript file naming: raw = `transcripts/{session_id}.md`, edited = `transcripts/{session_id}-edited.md`
- Path resolution: `metadata_root = self.store.metadata_file.parent.parent` then join relative paths
- Error handling: Custom `SessionCommandError` with code, message, guidance, exit_code
- Return pattern: `CommandResult` dataclass with command, payload, message
- Lazy imports for optional dependencies (e.g., `from deepgram import ...` inside method)

### Follow-up Questions
No follow-up questions were needed.

## Visual Assets

### Files Provided:
No visual assets provided (confirmed via filesystem check).

## Requirements Summary

### Functional Requirements
- CLI command `refine <session-id>` to trigger LLM-based transcript refinement
- Default target: latest edited transcript (`{session_id}-edited.md`)
- Fallback to raw transcript if no edited version exists
- `--raw` flag to force refinement of raw transcript
- Refined output overwrites the edited transcript (or creates it if refining raw)
- Sentence-level refinement: typo correction, spacing, punctuation, wording improvements
- Preserve original lecture meaning and terminology
- Chunking for long transcripts with lecture topic context passed to each chunk
- Multi-language support (language detection or user-specified)
- Gemini API integration as the sole LLM provider for initial version
- API key configuration via environment variable or config

### Reusability Opportunities
- Adapter pattern from `deepgram_adapter.py` for Gemini API adapter
- Configuration dataclass pattern from `stt_config.py` for LLM config
- Session lookup and transcript path resolution from `session_service.py`
- Error handling pattern (`SessionCommandError`) for consistent CLI errors
- `CommandResult` return pattern for CLI output

### Scope Boundaries
**In Scope:**
- `refine` CLI command with session-id argument
- Gemini API adapter for LLM-based refinement
- Sentence-level text cleanup (typos, spacing, punctuation, wording)
- Chunking with topic context for long transcripts
- Multi-language support
- `--raw` flag to force raw transcript refinement
- Overwrite edited transcript with refined output
- API key configuration and validation

**Out of Scope:**
- Local LLM model support (e.g., Ollama)
- Multi-session batch processing
- Paragraph/section-level structural changes
- Dry-run/preview mode
- Separate refined file storage (refinement overwrites edited version)
- Custom refinement prompts from users
- Support for LLM providers other than Gemini

### Technical Considerations
- Gemini API requires API key (store in `.env` or OS keychain, consistent with existing STT key pattern)
- Chunking strategy: split transcript into manageable segments for LLM context window; maintain lecture topic context across chunks
- Existing transcript file convention: raw = `transcripts/{session_id}.md`, edited = `transcripts/{session_id}-edited.md`
- Follow existing adapter pattern for Gemini integration (lazy imports, error mapping)
- Follow existing config validation pattern from `STTConfig`
- Error categories to handle: auth errors, network errors, rate limiting, invalid input
- Session must have a transcript before refinement can be triggered
