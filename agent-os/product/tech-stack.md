# Product Tech Stack

## Framework & Runtime
- **Application Framework:** Python CLI application (Typer)
- **Language/Runtime:** Python 3.11+
- **Package Manager:** `uv` (primary) + `pip` compatibility

## Local App Structure
- **Execution Mode:** Terminal-first workflow (no web frontend)
- **Command Interface:** Typer-based commands for record/transcribe/refine/summarize
- **Job Execution:** In-process sequential pipeline with optional local worker mode
- **Data Storage:** Local filesystem only (`recordings/`, `transcripts/`, `notes/`, `config/`)

## AI & Audio Processing
- **STT Engine (Local):** faster-whisper (Whisper based)
- **STT Engine (API):** OpenAI/Deepgram-style provider adapter via API keys
- **LLM Processing:** Provider-agnostic LLM adapter (OpenAI-compatible API) for transcript refinement and note generation
- **Audio Capture/Processing:** FFmpeg + PyAudio/SoundCard integration for system-audio recording and conversion

## Testing & Quality
- **Test Framework:** pytest
- **CLI/Integration Testing:** pytest with fixture-based audio/transcript/note scenarios
- **Linting/Formatting:** Ruff + Black
- **Type Checking:** mypy

## Security & Configuration
- **Secrets Management:** Local environment variables (`.env`) and OS keychain for API keys
- **Auth (Initial Scope):** Single-user local application (no account system)
- **Validation:** Pydantic request/response validation + server-side business rule validation

## Output Format
- **Primary Output:** Local Markdown (`.md`) summary notes saved per lecture session
- **Transcript Output:** Raw and refined transcripts stored as local text/Markdown files

## Product-Specific Notes
- **User-Specified Requirement:** Python is the primary language for this product and takes precedence over other defaults.
- **Execution Requirement:** Product is not web-based and is run locally through terminal commands.
- **Output Requirement:** Final summary notes are generated and saved as local `.md` files.
- **Model Flexibility:** STT and LLM layers support both local models and API-key providers to balance privacy, cost, and quality.
