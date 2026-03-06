# Spec Requirements: stt-pipeline-with-provider-selection

## Initial Description
STT Pipeline with Provider Selection — Deliver transcription from recorded/imported audio using selectable STT modes (local model or API key provider) with setup checks in CLI config. Users should be able to run transcription from terminal commands and receive complete raw transcript files with actionable error messages.

## Requirements Discussion

### First Round Questions

**Q1:** I assume the transcription command will target an existing session that already has an attached audio file (captured or imported). Is that correct, or should we also allow direct transcription from a standalone file path without session linkage?
**Answer:** 맞아. 오디오 파일은 세션에서 녹음되거나 불러와진 파일일거야. 세션 이외 경로에서 업로드 된 파일은 scope 에서 제외하자

**Q2:** I'm assuming we should support two STT modes in CLI config: `local` (faster-whisper) and `api` (provider + API key), with one default mode selected globally. Is that correct, or do you want per-command mode override as well?
**Answer:** 유저는 로컬 모델을 불러오거나 아니면 api를 통해 쓰거나 둘 중 하나를 택하는 방식이야. 기본은 api로 할거야

**Q3:** I assume setup checks should fail fast before transcription starts (e.g., missing model, missing API key, invalid provider, missing ffmpeg dependency if needed). Is that correct, or should some checks be warnings with best-effort execution?
**Answer:** 맞아 필요한 사항들을 체크한 다음 transcription 해야해

**Q4:** I'm thinking raw transcript output should be saved per session under a deterministic local path and file naming rule (for example by session id + timestamp). Should we keep only the latest raw transcript, or version every run attempt?
**Answer:** 가장 최근의 raw transcript만 저장하자

**Q5:** I assume actionable error handling should classify failures like `config error`, `provider auth error`, `network/transient error`, and `audio format/decoding error`, with retry guidance only for retryable categories. Is that correct, or do you want a different error taxonomy?
**Answer:** 맞아 니가 제시한 방향으로 해줘

**Q6:** I'm assuming retry behavior should be automatic only for transient API failures (with bounded retries/backoff), while local-model failures should be immediate with fix instructions. Is that correct, or should retries be user-triggered only?
**Answer:** 맞아 니가 제시한 방향으로 하되 api 사용시 retry 횟수는 최대 2회로 제한하고싶어

**Q7:** I assume terminal progress output should include clear stages such as `preflight checks -> mode/provider init -> transcription in progress -> file write complete`, and end with output file path. Is that correct, or do you want more granular progress/events?
**Answer:** 맞아 명확한 스테이지를 제시 해줘야해

**Q8:** What should be explicitly out of scope for this spec so we avoid feature creep (for example speaker diarization, timestamps/segments export, multilingual translation, or transcript editing UX)?
**Answer:** 로드맵의 3번 항목이 제시하지 않는 사항들은 전부 OOS야

### Existing Code to Reference
No similar existing features identified for reference.

### Follow-up Questions
No follow-up questions were asked.

## Visual Assets

### Files Provided:
No visual assets provided.

### Visual Insights:
No visual assets provided.

## Requirements Summary

### Functional Requirements
- Transcription runs only for audio files already attached to existing sessions (recorded or imported within session flow).
- Direct transcription from arbitrary standalone file paths outside session context is out of scope.
- CLI config supports exactly two STT modes: local model mode and API provider mode.
- Default STT mode is API mode.
- Preflight setup checks must complete before transcription starts and fail fast on missing or invalid prerequisites.
- Raw transcript output persists as a single latest artifact per session (overwrite or replace prior raw transcript for that session).
- Error reporting uses actionable categories: configuration, provider authentication, network/transient, and audio format/decoding.
- Automatic retry applies only to transient API failures, with a maximum of 2 retries.
- Local model failures do not auto-retry and must return immediate fix-oriented error guidance.
- CLI progress output must present clear execution stages and conclude with transcript output path.

### Reusability Opportunities
- Existing session-based audio attachment and job-runner command flow can be investigated for reuse during spec writing and implementation.
- Existing CLI progress formatting patterns can be reused to keep stage output consistent.
- Existing session metadata and persistence patterns can be reused for latest raw transcript replacement behavior.

### Scope Boundaries
**In Scope:**
- STT execution pipeline from session-linked audio using selectable provider mode.
- CLI preflight checks for selected STT mode and required setup.
- Raw transcript generation and persistence as latest-per-session artifact.
- Actionable error messaging and constrained retry behavior for API transient failures.
- Stage-based CLI progress output for transcription runs.

**Out of Scope:**
- Any capability not described by roadmap item 3.
- Transcription from non-session arbitrary file paths.
- Features aligned with later roadmap items (transcript review/edit workflow, LLM refinement, summary generation, search/library, export/share enhancements).
- Additional STT enhancements not explicitly defined in item 3 (for example diarization, advanced segment exports, translation).

### Technical Considerations
- Must align with terminal-first Python CLI architecture and current Typer command model.
- Must align with product STT stack direction: local faster-whisper option plus API provider adapter option.
- API key and provider validation should use existing local configuration and secret handling approach.
- Retry policy should be explicit and bounded (max 2 retries) to avoid hidden long-running behavior.
- Error messages should remain user-friendly and actionable per global error-handling standards.
- Validation should be consistent and fail early across command entry points.
