# Task Breakdown: Summary Note Generation with Templates

## Overview
Total Tasks: 14
Assigned roles: api-engineer, testing-engineer

## Task List

### Core Service & CLI Layer

#### Task Group 1: Note Generation Service & CLI Command
**Assigned implementer:** api-engineer
**Dependencies:** None (reuses existing llm_adapter, session_service, cli_output patterns)

- [x] 1.0 Complete note generation service and CLI command
  - [x] 1.1 Write 2–8 focused tests for the summarize service
    - Limit to 2–8 highly focused tests maximum
    - Test only critical behaviors:
      - Session lookup resolves most recent transcript by default
      - `--id` flag targets specified session
      - `--preview` flag returns notes without writing to disk
      - Save flow writes to `notes/{session_id}.md` (overwrite if exists)
    - Mock LLM adapter and filesystem; do NOT call real APIs
    - Skip edge cases and exhaustive error-state testing
  - [x] 1.2 Extend `LLMProviderAdapter` protocol with `generate_notes` method
    - Add `generate_notes(transcript: str, template: str, context_topic: str | None = None) -> str` to `llm_adapter.py` Protocol
    - Implement `generate_notes` in `GeminiLLMAdapter`
    - Reuse chunking and error-handling pattern from existing `refine_transcript` method
  - [x] 1.3 Create template resolution logic
    - Predefined templates stored under `src/lecture_auto/templates/` (create directory)
    - Create 3 predefined `.md` template presets: `bullet-summary.md`, `structured-notes.md`, `qa-review.md`
    - Designate `bullet-summary.md` as the default template
    - User custom templates resolved from `~/.lecture_auto/templates/` if not found among presets
    - `--template <name>` resolves by name (without `.md` extension) against presets first, then user directory
  - [x] 1.4 Add `build_note_path` to `SessionMetadataStore`
    - Returns `notes/{session_id}.md`
    - Follow pattern of `build_raw_transcript_path`
  - [x] 1.5 Implement `summarize_session` method on `SessionService`
    - Accept `session_reference: str`, `template_name: str | None`, `preview: bool`
    - Resolve session by session_id or title (reuse `transcript_refine` lookup pattern)
    - Select transcript: prefer `{session_id}-edited.md`, fall back to raw
    - Raise `SessionCommandError` if no transcript found
    - Load and resolve template; raise `SessionCommandError` if template not found
    - Call `llm_adapter.generate_notes(transcript, template, context_topic)`
    - If `preview=True`: return `CommandResult` with generated notes in message, do not write to disk
    - If `preview=False`: write to `notes/{session_id}.md` (overwrite), return `CommandResult`
    - Wrap LLM errors with appropriate `SessionCommandError` codes (reuse pattern from `transcript_refine`)
  - [x] 1.6 Register `summarize` Typer CLI command in the CLI entry point
    - Flags: `--id` (optional, targets specific session; default: most recent session), `--template` (optional), `--preview` (bool flag)
    - Wire to `summarize_session` on `SessionService`
    - Add `format_command_output` branch in `cli_output.py` for `"summarize"` command result
  - [x] 1.7 Ensure task group tests pass
    - Run ONLY the 2–8 tests written in 1.1
    - Verify critical flows pass (session lookup, preview, save, overwrite)
    - Do NOT run the entire test suite at this stage

**Acceptance Criteria:**
- The 2–8 tests written in 1.1 pass
- `lecture-auto summarize` generates and saves notes from the most recent session's transcript
- `lecture-auto summarize --id <session_id>` targets the specified session
- `lecture-auto summarize --template <name>` uses the specified template
- `lecture-auto summarize --preview` displays notes in terminal without writing to disk
- Re-running summarize overwrites the existing `notes/{session_id}.md`
- LLM errors produce meaningful `SessionCommandError` with guidance

### Testing

#### Task Group 2: Test Review & Gap Analysis
**Assigned implementer:** testing-engineer
**Dependencies:** Task Group 1

- [x] 2.0 Review existing tests and fill critical gaps only
  - [x] 2.1 Review tests from Task Group 1
    - Review the 2–8 tests written by api-engineer (Task 1.1)
    - Total existing tests: approximately 2–8 tests
  - [x] 2.2 Analyze test coverage gaps for THIS feature only
    - Identify critical user workflows that lack coverage:
      - Template not found error path
      - LLM auth/network error propagation
      - `--id` flag targeting a session with no transcript
      - Overwrite behavior (file exists and is replaced)
    - Focus ONLY on gaps related to this spec's feature requirements
    - Do NOT assess entire application test coverage
  - [x] 2.3 Write up to 10 additional strategic tests maximum
    - Add maximum of 10 new tests to fill identified critical gaps
    - Focus on integration points: template resolution + LLM call + file write chain
    - Do NOT write exhaustive coverage for all error states
    - Skip performance tests and low-importance edge cases
  - [x] 2.4 Run feature-specific tests only
    - Run ONLY tests related to this spec's feature (tests from 1.1 and 2.3)
    - Expected total: approximately 12–18 tests maximum
    - Do NOT run the entire application test suite
    - Verify all critical workflows pass

**Acceptance Criteria:**
- All feature-specific tests pass (approximately 12–18 tests total)
- Critical user workflows for this feature are covered
- No more than 10 additional tests added by testing-engineer
- Testing focused exclusively on this spec's feature requirements

## Execution Order

Recommended implementation sequence:
1. Core Service & CLI Layer (Task Group 1)
2. Test Review & Gap Analysis (Task Group 2)
