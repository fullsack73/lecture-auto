# Spec Requirements: transcript-file-review-and-edit-workflow

## Initial Description
4. [ ] Transcript File Review and Edit Workflow — Provide command-driven transcript review where users can open, search, and edit transcript files, then save revised versions locally. Ensure versioned transcript states (raw vs edited) are testable and recoverable from filesystem artifacts. `[M]`

## Requirements Discussion

### First Round Questions

**Q1:** I assume users will specify the transcript file to open by its associated session ID or lecture name (e.g. `lecture open --session 123` or `lecture open --transcript "Math 101"`). Is that correct, or do you prefer users providing direct file paths (e.g., `lecture open transcripts/math-101.md`)?
**Answer:** 맞아 세션id나 이름을 통해서 전사 결과 파일을 열람하게 될거야 explicit하게 디렉토리 명시가 안되어있어도. (Yes, users will open the transcript file by session ID or name, without explicitly specifying the directory.)

**Q2:** I'm thinking the "open" and "edit" commands will launch the file in the user's default system text editor (e.g., via `typer.launch()` or `os.startfile`) so they can review and modify the text in their preferred IDE/editor. Should we do that, or are you envisioning building an in-terminal interactive text editor (which would be much more complex)?
**Answer:** 맞아 열람 하면 유저가 기본으로 설정해놓은 텍스트 에디터로 볼 수 있게 하면 돼 (Yes, viewing should open the file in the user's default text editor.)

**Q3:** For the "search" functionality, I assume from the terminal, users can run a command like `lecture search "keyword"` which will recursively grep through all saved transcript files and output the matched lines and their corresponding file/session names. Is that correct?
**Answer:** 전사 파일의 내용을 까보면 너무 오래걸리니까 제목만 검색하는 것으로 하자 (Searching through transcript content would take too long, so let's only search by title.)

**Q4:** You mentioned "save revised versions locally" and "Ensure versioned transcript states (raw vs edited)". I'm assuming we will keep the original transcript file untouched (e.g., `raw.md`) and save the edited text to a new file (e.g., `edited.md`) in the same session directory when they finish editing. Is that the correct approach for versioning?
**Answer:** 맞아 (Yes.)

**Q5:** I assume when a user edits the transcript via their external editor, the CLI will block/wait until the editor is closed, and then automatically detect if the file was modified, saving the new changes to the `edited.md` artifact. Is that correct, or should saving an edited version require an explicit separate save/import command?
**Answer:** 맞아 변경된 파일을 저장하는데 추가로 명령어를 쓸 필요는 없어야 해 (Yes, saving the modified file should not require an additional command.)

**Q6:** I assume we should enforce that the saved edited transcripts simply replace the active transcript state for that session without preserving intermediate edits (so we only have one `raw` state and one `edited` state). Is that correct, or do you need multiple edit history versions (e.g. `edited_v1`, `edited_v2`)?
**Answer:** 맞아 수정이 이뤄진 파일은 몇번 다시 수정하건 그냥 덮어 씌우는 방식으로 해줘 (Yes, edited files should just overwrite the existing edited file, no matter how many times it's modified.)

**Q7:** I'm thinking we should output a clear terminal summary of changes (e.g. "Transcript edited: 5 lines changed") after the text editor closes and the new version is saved. Should we provide this diff summary?
**Answer:** 아냐, 뭐가 바뀌었는지 몇 줄이 바뀌었는지 표시해 줄 필요는 없어 (No, there's no need to display what changed or how many lines changed.)

**Q8:** Are there any specific terminal-based edge cases or exclusions we should ignore for now, such as handling concurrent edits to the same transcript file from different terminal windows?
**Answer:** 로드맵의 4번 항목이 제시하지 않는 기능을 구현하는건 OOS야 (Implementing any features not specified in item 4 of the roadmap is Out Of Scope.)

### Existing Code to Reference
No similar existing features identified for reference.

### Follow-up Questions
No follow-up questions were asked.

## Visual Assets

### Files Provided:
No visual files found.

### Visual Insights:
No visual assets provided.

## Requirements Summary

### Functional Requirements
- Command to search transcripts by session ID or title.
- Command to open/edit a transcript in the user's default system text editor.
- Automatic saving of edited transcripts as a new version (`edited` state) when the editor closes, without requiring an explicit save command.
- The CLI must pause/wait while the external editor is open and detect changes upon closure.

### Reusability Opportunities
- None identified.

### Scope Boundaries
**In Scope:**
- Searching transcripts by title only.
- Opening transcripts in default text editor.
- Versioning transcripts into `raw` and `edited` states.
- Overwriting the `edited` state on subsequent edits.

**Out of Scope:**
- Searching through the content/text of transcript files (due to performance concerns).
- Multi-version history (e.g., `edited_v1`, `edited_v2`), just a single `edited` state.
- Diff output or change summary in the terminal.
- Any features or edge cases not explicitly listed in roadmap item 4.
- In-terminal text editing.

### Technical Considerations
- Integration with user's system to launch default text editor (`typer.launch` or similar cross-platform approach).
- Synchronous blocking of the CLI process while the file is being edited.
- File modification detection (e.g., comparing last modified timestamps or file hashes before and after edit).
- Managing two states per session: raw and edited, keeping the raw state intact.
