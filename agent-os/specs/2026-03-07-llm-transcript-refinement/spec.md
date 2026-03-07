# Specification: LLM-Based Transcript Refinement

## Goal
Add an optional transcript refinement step driven by an LLM (Gemini API) that improves sentence-level spacing, punctuation, wording, and typo correction. This helps users clean up raw STT outputs or correct existing edited transcripts while preserving the original lecture meaning.

## User Stories
- As a college student, I want to refine my lecture transcripts so that typos and awkward phrasing from raw STT models are corrected for better readability.
- As a study-focused learner, I want the refined transcript to automatically overwrite my edited version so I don't have to juggle multiple files.
- As a user with longer lecture sessions, I want the system to handle long transcripts automatically via chunking while retaining the topic context across parts.

## Core Requirements
### Functional Requirements
- CLI command `refine <session-id>` to trigger the refinement process explicitly.
- The command targets the latest edited transcript by default (`{session_id}-edited.md`).
- A `--raw` flag allows forcing refinement on the raw transcript instead.
- If refining raw, or if edited doesn't exist, save the result as the new edited transcript.
- Uses Gemini API for LLM processing.
- Splits long transcripts into chunks and maintains a lecture topic context during the LLM calls.
- Supports multi-language transcripts implicitly or explicitly.

### Non-Functional Requirements
- **Performance:** Handle transcripts of any length efficiently through chunking.
- **Resilience:** Gracefully handle API rate limits and transient network errors.
- **Configurability:** Require an API key configured either via `.env` or system environment variable, consistent with the STT config.

## Visual Design
- No visual mockups provided or needed.
- CLI output will follow the existing standard using Typer with `CommandResult`, showing progress, success, and error states clearly on the terminal.

## Reusable Components
### Existing Code to Leverage
- **Components:** `CommandResult`, `SessionCommandError` for CLI outputs and exception handling (`src/lecture_auto/cli_output.py`, `src/lecture_auto/session_service.py`).
- **Services:** `SessionService` for file path resolution (`_write_transcript_file`, `_require_session`).
- **Patterns:** Adapter Pattern from `deepgram_adapter.py` / `whisper_adapter.py` to be used for the Gemini API adapter. Configuration dataclass pattern from `STTConfig`.

### New Components Required
- **LLMProviderAdapter:** A new adapter interface specific to LLM interactions.
- **GeminiLLMAdapter:** Concrete implementation for Gemini API processing and chunk handling. Existing STT adapters are audio-specific; text refinement needs an LLM API client.
- **RefinementService (or integrate into SessionService):** The domain logic coordinating transcript chunking, context summarization, and LLM calls.

## Technical Approach
- **Database (Metadata):** No changes needed. Paths match the existing `{session_id}-edited.md` convention supported by `SessionService`.
- **API (External):** Integration with the official Gemini API SDK / API.
- **Frontend (CLI):** Add a `refine` command in the Typer CLI app, consuming `session_id` and the optional `--raw` flag.
- **Testing:** Unit tests verifying chunking logic, LLM adapter response parsing, CLI error handling, and file overwrite behavior with mock files.

## Out of Scope
- Local LLM models support (e.g., Ollama/Llama.cpp).
- Batch processing multiple sessions concurrently.
- Paragraph or section-level structural changes.
- Providing separate refined files (overwrites edited transcript).
- Dry-run or preview mode.

## Success Criteria
- Executing `lecture-auto refine <session-id>` correctly parses the file, cleans the text via Gemini, and saves it successfully.
- Meaning and terminology of the original lecture remain intact as tested via comparative diffs.
- Graceful termination with helpful `guidance` when keys are missing or invalid (`SessionCommandError`).
