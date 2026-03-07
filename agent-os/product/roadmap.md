# Product Roadmap

1. [x] Lecture Session Capture Flow — Build an end-to-end recording workflow where users can create a lecture session, start/stop system-audio capture, and view saved session history via terminal commands. Include local session metadata storage and success/failure states users can verify in tests. `[M]`
2. [x] Audio Import, Local Storage, and Job Runner — Enable users to attach captured or imported audio files to sessions, persist files under local project folders, and trigger processing from terminal commands. Provide clear CLI progress output and retry handling for failed jobs. `[M]`
3. [x] STT Pipeline with Provider Selection — Deliver transcription from recorded/imported audio using selectable STT modes (local model or API key provider) with setup checks in CLI config. Users should be able to run transcription from terminal commands and receive complete raw transcript files with actionable error messages. `[L]`
4. [x] Transcript File Review and Edit Workflow — Provide command-driven transcript review where users can open, search, and edit transcript files, then save revised versions locally. Ensure versioned transcript states (raw vs edited) are testable and recoverable from filesystem artifacts. `[M]`
5. [x] LLM-Based Transcript Refinement — Add optional transcript cleanup that improves spacing, wording, and typo correction while preserving lecture meaning. Save before/after transcript outputs as separate local files so users can compare and choose the final input for summarization. `[M]`
6. [ ] Summary Note Generation with Templates — Let users generate lecture notes from selected transcript versions using predefined or custom output formats. Implement end-to-end generation, preview, save, and regenerate flows through CLI commands with final output stored as `.md` files. `[L]`
7. [ ] Local Notes Library and Search Commands — Create a local notes library structure where students can list lectures, search transcript/note content, and reopen related audio and summaries from terminal commands. Include filtering and recent-activity metadata to reduce exam-prep time. `[M]`
8. [ ] Markdown Export and Share Package — Enable users to package transcripts and summaries into share-ready local files (Markdown/TXT/PDF) for classmates. Validate export quality and failure handling across command execution and local file generation paths. `[S]`

> Notes
> - Include 4–12 items total
> - Order items by technical dependencies and product architecture
> - Each item should represent an end-to-end (frontend + backend) functional and testable feature
