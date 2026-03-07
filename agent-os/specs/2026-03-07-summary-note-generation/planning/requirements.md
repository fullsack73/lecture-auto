# Spec Requirements: Summary Note Generation with Templates

## Initial Description
Summary Note Generation with Templates — Let users generate lecture notes from selected transcript versions using predefined or custom output formats. Implement end-to-end generation, preview, save, and regenerate flows through CLI commands with final output stored as `.md` files. [L]

## Requirements Discussion

### First Round Questions

**Q1:** I assume the `summarize` command will take a transcript file (raw or refined) as input and generate a `.md` summary note. Is that correct, or should it also accept a session ID and automatically find the latest transcript version?
**Answer:** The `summarize` command will automatically target the most recent transcript by default. If the user provides an `--id` flag (e.g., `summarize --id 12345`), it will target that specific session instead.

**Q2:** I'm thinking we'll provide 2-3 predefined templates (e.g., "bullet-point summary", "structured lecture notes with headings", "Q&A review format"). Should we include these specific formats, or do you have other template types in mind?
**Answer:** Yes, provide several `.md` template presets. One of them should be set as the default. Users should also be able to create their own custom templates and specify them for use.

**Q3:** I assume custom templates will be user-defined Markdown templates stored in a local directory, where users can define their own output structure. Is that correct, or should custom templates be specified inline via CLI arguments?
**Answer:** Correct. Which template to use is specified via a `--template` flag on the CLI command.

**Q4:** For the "preview" flow, I assume the user runs a command like `lecture-auto summarize --preview` which displays the generated summary in the terminal before saving. Is that correct, or should preview write to a temporary file that the user can open?
**Answer:** Correct — the preview should display the generated summary in the terminal before saving, not write to a temporary file.

**Q5:** For the "regenerate" flow, I assume the user can re-run the summarize command on the same transcript to produce a new version, and both the old and new summaries are kept (versioned). Is that correct, or should regeneration overwrite the previous summary?
**Answer:** The new version of the summary should overwrite the old version. No versioning of summaries.

**Q6:** I assume the LLM adapter (`llm_adapter.py`) already used for transcript refinement will be reused for summary generation, using the same provider-agnostic configuration. Is that correct?
**Answer:** Yes, correct.

**Q7:** I assume the generated notes will be stored under a `notes/` directory within the session folder structure, following the existing pattern of `recordings/` and `transcripts/`. Is that correct, or do you prefer a different storage location?
**Answer:** Yes, correct. Notes will be stored under a `notes/` directory.

**Q8:** Is there anything specific you want to exclude from this feature's scope? For example, should we avoid multi-session summary merging or PDF export at this stage?
**Answer:** Yes — multi-session summary merging, PDF export, and any other functionality not explicitly described in roadmap item #6 are all out of scope.

### Existing Code to Reference

No specific similar features were explicitly identified by the user, but the following existing code is directly relevant and should be referenced:
- Feature: LLM Transcript Refinement - Path: `src/lecture_auto/llm_adapter.py` (provider-agnostic LLM adapter to reuse for summary generation)
- Feature: LLM Config - Path: `src/lecture_auto/llm_config.py` (LLM configuration to reuse)
- Feature: Session Service - Path: `src/lecture_auto/session_service.py` (session management, transcript file handling, CLI commands)
- Feature: CLI Output - Path: `src/lecture_auto/cli_output.py` (terminal output formatting for preview display)

### Follow-up Questions
No follow-up questions were needed. All answers were clear and specific.

## Visual Assets

### Files Provided:
No visual assets provided.

## Requirements Summary

### Functional Requirements
- `summarize` CLI command that generates lecture notes from a transcript
- Default behavior: automatically targets the most recent transcript version
- `--id <session_id>` flag to target a specific session
- `--template <template_name>` flag to specify which template to use
- Predefined `.md` template presets (2-3 types, e.g., bullet-point summary, structured lecture notes, Q&A review format)
- One predefined template set as the default
- Users can create custom `.md` templates and specify them via `--template`
- Preview flow: display generated summary in terminal before saving
- Save flow: persist the generated summary as a `.md` file under `notes/` directory
- Regenerate flow: re-running summarize overwrites the existing summary (no versioning)
- Uses the existing provider-agnostic LLM adapter for generation

### Reusability Opportunities
- `llm_adapter.py` — reuse for LLM-based summary generation
- `llm_config.py` — reuse LLM provider configuration
- `session_service.py` — reuse session management patterns, transcript file lookup, CLI command structure
- `cli_output.py` — reuse terminal output formatting for preview display

### Scope Boundaries
**In Scope:**
- `summarize` CLI command with `--id` and `--template` flags
- Predefined template presets with a default
- Custom user-defined templates
- Preview in terminal before saving
- Save generated notes as `.md` files under `notes/`
- Regeneration by overwriting existing summary
- End-to-end generation flow using existing LLM adapter

**Out of Scope:**
- Multi-session summary merging
- PDF export
- Any functionality not explicitly described in roadmap item #6

### Technical Considerations
- Reuse existing `llm_adapter.py` (provider-agnostic LLM adapter) for summary generation
- Reuse existing `llm_config.py` for LLM configuration
- Follow existing CLI command patterns in `session_service.py` using Typer
- Store generated notes under `notes/` directory within session folder structure
- Template storage location needs to be determined (e.g., `config/templates/` or similar)
- Python 3.11+ with Typer CLI framework
- pytest for testing
- Pydantic for validation
