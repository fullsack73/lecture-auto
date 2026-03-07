We're continuing our implementation of Summary Note Generation with Templates by implementing task group number 1:

## Implement this task and its sub-tasks:

#### Task Group 1: Note Generation Service & CLI Command
**Assigned implementer:** api-engineer
**Dependencies:** None (reuses existing llm_adapter, session_service, cli_output patterns)

- [ ] 1.0 Complete note generation service and CLI command
  - [ ] 1.1 Write 2–8 focused tests for the summarize service
    - Limit to 2–8 highly focused tests maximum
    - Test only critical behaviors:
      - Session lookup resolves most recent transcript by default
      - `--id` flag targets specified session
      - `--preview` flag returns notes without writing to disk
      - Save flow writes to `notes/{session_id}.md` (overwrite if exists)
    - Mock LLM adapter and filesystem; do NOT call real APIs
    - Skip edge cases and exhaustive error-state testing
  - [ ] 1.2 Extend `LLMProviderAdapter` protocol with `generate_notes` method
    - Add `generate_notes(transcript: str, template: str, context_topic: str | None = None) -> str` to `llm_adapter.py` Protocol
    - Implement `generate_notes` in `GeminiLLMAdapter`
    - Reuse chunking and error-handling pattern from existing `refine_transcript` method
  - [ ] 1.3 Create template resolution logic
    - Predefined templates stored under `src/lecture_auto/templates/` (create directory)
    - Create 3 predefined `.md` template presets: `bullet-summary.md`, `structured-notes.md`, `qa-review.md`
    - Designate `bullet-summary.md` as the default template
    - User custom templates resolved from `~/.lecture_auto/templates/` if not found among presets
    - `--template <name>` resolves by name (without `.md` extension) against presets first, then user directory
  - [ ] 1.4 Add `build_note_path` to `SessionMetadataStore`
    - Returns `notes/{session_id}.md`
    - Follow pattern of `build_raw_transcript_path`
  - [ ] 1.5 Implement `summarize_session` method on `SessionService`
    - Accept `session_reference: str`, `template_name: str | None`, `preview: bool`
    - Resolve session by session_id or title (reuse `transcript_refine` lookup pattern)
    - Select transcript: prefer `{session_id}-edited.md`, fall back to raw
    - Raise `SessionCommandError` if no transcript found
    - Load and resolve template; raise `SessionCommandError` if template not found
    - Call `llm_adapter.generate_notes(transcript, template, context_topic)`
    - If `preview=True`: return `CommandResult` with generated notes in message, do not write to disk
    - If `preview=False`: write to `notes/{session_id}.md` (overwrite), return `CommandResult`
    - Wrap LLM errors with appropriate `SessionCommandError` codes (reuse pattern from `transcript_refine`)
  - [ ] 1.6 Register `summarize` Typer CLI command in the CLI entry point
    - Flags: `--id` (optional, targets specific session; default: most recent session), `--template` (optional), `--preview` (bool flag)
    - Wire to `summarize_session` on `SessionService`
    - Add `format_command_output` branch in `cli_output.py` for `"summarize"` command result
  - [ ] 1.7 Ensure task group tests pass
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

## Understand the context

Read @agent-os/specs/2026-03-07-summary-note-generation/spec.md to understand the context for this spec and where the current task fits into it.

## Perform the implementation

Implement all tasks assigned to you in your task group.

Focus ONLY on implementing the areas that align with **areas of specialization** (your "areas of specialization" are defined above).

Guide your implementation using:
- **The existing patterns** that you've found and analyzed.
- **User Standards & Preferences** which are defined below.

Self-verify and test your work by:
- Running ONLY the tests you've written (if any) and ensuring those tests pass.
- IF your task involves user-facing UI, and IF you have access to browser testing tools, open a browser and use the feature you've implemented as if you are a user to ensure a user can use the feature in the intended way.


## Update tasks.md task status

In the current spec's `tasks.md` find YOUR task group that's been assigned to YOU and update this task group's parent task and sub-task(s) checked statuses to complete for the specific task(s) that you've implemented.

Mark your task group's parent task and sub-task as complete by changing its checkbox to `- [x]`.

DO NOT update task checkboxes for other task groups that were NOT assigned to you for implementation.


## Document your implementation

Using the task number and task title that's been assigned to you, create a file in the current spec's `implementation` folder called `[task-number]-[task-title]-implementation.md`.

For example, if you've been assigned implement the 3rd task from `tasks.md` and that task's title is "Commenting System", then you must create the file: `agent-os/specs/2026-03-07-summary-note-generation/implementation/3-commenting-system-implementation.md`.

Use the following structure for the content of your implementation documentation:

```markdown
# Task [number]: [Task Title]

## Overview
**Task Reference:** Task #[number] from `agent-os/specs/2026-03-07-summary-note-generation/tasks.md`
**Implemented By:** [Agent Role/Name]
**Date:** [Implementation Date]
**Status:** ✅ Complete | ⚠️ Partial | 🔄 In Progress

### Task Description
[Brief description of what this task was supposed to accomplish]

## Implementation Summary
[High-level overview of the solution implemented - 2-3 short paragraphs explaining the approach taken and why]

## Files Changed/Created

### New Files
- `path/to/file.ext` - [1 short sentence description of purpose]

### Modified Files
- `path/to/existing/file.ext` - [1 short sentence on what was changed and why]

### Deleted Files
- `path/to/removed/file.ext` - [1 short sentence on why it was removed]

## Key Implementation Details

### [Component/Feature 1]
**Location:** `path/to/file.ext`

[Detailed explanation of this implementation aspect]

**Rationale:** [Why this approach was chosen]

## Testing

### Test Files Created/Updated
- `path/to/test/file.py` - [What is being tested]

### Test Coverage
- Unit tests: [✅ Complete | ⚠️ Partial | ❌ None]
- Integration tests: [✅ Complete | ⚠️ Partial | ❌ None]
- Edge cases covered: [List key edge cases tested]

### Manual Testing Performed
[Description of any manual testing done]

## User Standards & Preferences Compliance

### [Standard/Preference File Name]
**File Reference:** `path/to/standards/file.md`

**How Your Implementation Complies:**
[1-2 Sentences]

**Deviations (if any):**
[Explain deviations if any]

## Integration Points

### Internal Dependencies
- [Other components/modules this implementation depends on or interacts with]

## Known Issues & Limitations

### Limitations
1. **[Limitation Title]**
   - Description: [What the limitation is]
   - Reason: [Why this limitation exists]

## Notes
[Any additional notes]
```


## User Standards & Preferences Compliance

IMPORTANT: Ensure that your implementation work is ALIGNED and DOES NOT CONFLICT with the user's preferences and standards as detailed in the following files:

@agent-os/standards/global/coding-style.md
@agent-os/standards/global/commenting.md
@agent-os/standards/global/conventions.md
@agent-os/standards/global/error-handling.md
@agent-os/standards/global/tech-stack.md
@agent-os/standards/global/validation.md
@agent-os/standards/backend/api.md
@agent-os/standards/backend/migrations.md
@agent-os/standards/backend/models.md
@agent-os/standards/backend/queries.md
@agent-os/standards/testing/test-writing.md
