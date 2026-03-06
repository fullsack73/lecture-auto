# Spec Requirements: Audio Import, Local Storage, and Job Runner

## Initial Description
Audio Import, Local Storage, and Job Runner — Enable users to attach captured or imported audio files to sessions, persist files under local project folders, and trigger processing from terminal commands. Provide clear CLI progress output and retry handling for failed jobs.

## Requirements Discussion

### First Round Questions

**Q1:** I assume users will attach audio to an existing lecture session by referencing a `session_id` (or latest active session) in CLI. Is that correct, or should we also support creating a new session implicitly during import?
**Answer:** 세션 시작이랑 녹음 기능은 이미 구현이 되어있어서 라이브 캡쳐가 아닌 pre existing audio를 업로드 할 때 처리하는 것만 가정하면 돼. 그리고 맞아. 유저가 오디오 파일과 동시에 session id를 제공할거야

**Q2:** I'm assuming we should support common local audio formats first (`.wav`, `.mp3`, `.m4a`) and reject unsupported formats with actionable CLI errors. Is that correct, or do you want a stricter/expanded format list?
**Answer:** 맞아 .wav .mp3 같은 파일만 처리하고 그 이외는 거절하도록 해줘

**Q3:** I assume imported/captured audio files should be persisted under a deterministic local structure (for example, session-scoped folders) with stable naming and collision handling. Is that correct, or do you prefer preserving original filenames/paths as much as possible?
**Answer:** 맞아, 라이브로 캡쳐되거나 업로드된 파일은 구조화된 이름을 가져야해

**Q4:** I'm thinking the job runner should be sequential and in-process for now (aligned with current product stack), with statuses like `queued`, `running`, `succeeded`, `failed`. Should we include `canceled` in this phase as well, or defer cancellation?
**Answer:** 그래 phase에 취소된 상태도 추가해

**Q5:** I assume retry should target failed jobs only, with a bounded retry count and clear reason output per failure (user-friendly, no stack traces by default). Is that correct, or should retry also allow manual rerun of successful jobs?
**Answer:** 맞아 실패한 작업만 리트라이를 하고 3번정도로 제한해줘

**Q6:** I assume CLI progress output should include start/end timestamps, current stage, and final summary per job, while remaining concise and testable via pytest assertions. Is that the desired level, or do you want more verbose step-by-step logs?
**Answer:** 맞아. 그렇게 해줘

**Q7:** I assume validation/business rules should fail fast (missing file, invalid session, duplicate attachment policy) and follow existing error-handling conventions. Should duplicate audio for the same session be blocked, or allowed with versioning?
**Answer:** 맞아 중복되는 오디오는 안받는걸로 해줘

**Q8:** For scope control, I assume this spec should not yet include STT execution/provider logic (that’s roadmap item 3), and should focus on attach/store/job-trigger lifecycle only. Is that correct?
**Answer:** 맞아 STT 관련 기능은 지금으로선 OOS야

**Q9:** What should be explicitly out of scope for this spec even if it seems related?
**Answer:** 로드맵 2번 항목에 명시되어 있지 않은 기능은 전부 OOS

### Existing Code to Reference

No similar existing features identified for reference.

### Follow-up Questions
No follow-up questions were required.

## Visual Assets

### Files Provided:
No visual assets provided.

### Visual Insights:
- Visual folder check was performed using the required command.
- No design files were found in `agent-os/specs/2026-03-06-audio-import-local-storage-and-job-runner/planning/visuals/`.

## Requirements Summary

### Functional Requirements
- Accept pre-existing local audio upload only for this feature phase (live capture initiation is already implemented).
- Require user to provide both audio file and `session_id` when attaching audio.
- Support common audio formats such as `.wav` and `.mp3`; reject unsupported formats with actionable CLI errors.
- Persist imported (and captured) audio files with structured, deterministic naming and organized local folder layout.
- Trigger processing through terminal commands using a sequential in-process job runner.
- Include job lifecycle statuses: `queued`, `running`, `succeeded`, `failed`, `canceled`.
- Provide retry only for failed jobs, with max retry count of 3.
- Provide clear CLI progress output including start/end timestamps, current stage, and final summary.
- Enforce business rules including duplicate audio rejection for the same logical attachment policy.
- Fully cover roadmap item 2 scope: attach captured/imported audio to sessions, persist files under local project folders, trigger processing from terminal commands, provide clear CLI progress output, and retry handling for failed jobs.

### Reusability Opportunities
- Reuse existing lecture session ID handling pattern from current session capture flow.
- Reuse existing CLI output formatting and test assertion style used by current command flows.
- Reuse existing metadata/storage patterns for local filesystem persistence where applicable.

### Scope Boundaries
**In Scope:**
- Pre-existing audio import and attachment to existing sessions via CLI.
- Local structured file persistence and naming.
- Job triggering, status tracking (including canceled), failed-job retry policy, and progress output.
- Validation and business rules for file type, session ID presence/validity, and duplicate audio blocking.

**Out of Scope:**
- STT execution/provider selection and transcription pipeline behavior (roadmap item 3).
- Any feature not explicitly included in roadmap item 2.
- New live-capture start/stop workflow changes.

### Technical Considerations
- Keep implementation aligned with terminal-first Python CLI architecture and current in-process execution model.
- Keep errors user-friendly and actionable; fail fast on invalid input.
- Maintain compatibility with existing test strategy (pytest) and deterministic CLI output expectations.
- Ensure local filesystem paths and naming conventions are deterministic for reliable tests and reproducibility.
