# Spec Requirements: Local Notes Library and Search Commands

## Initial Description
Local Notes Library and Search Commands — Create a local notes library structure where students can list lectures, search transcript/note content, and reopen related audio and summaries from terminal commands. Include filtering and recent-activity metadata to reduce exam-prep time. [M]

## Requirements Discussion

### First Round Questions

**Q1:** 기존 `SessionMetadataStore`에 저장된 세션 정보(제목, 날짜, 상태 등)를 기반으로 강의 목록을 보여주되, `completed` 상태인 것만 필터링할까요, 아니면 모든 상태의 세션을 기본으로 보여줄까요?
**Answer:** 메타데이터로부터 모든 상태의 세션을 목록으로 표시해줘

**Q2:** 검색 기능은 transcript 파일과 notes(`.md` 요약) 파일 모두의 텍스트 내용을 검색하는 것으로 가정합니다. 파일명/세션 제목뿐 아니라 본문 내 키워드 검색이 필요한 것 맞나요?
**Answer:** 검색 대상은 session_id, 요약본 md파일 딱 2개로 제한해줘

**Q3:** 전문 검색(full-text search) 엔진을 도입하기보다, 로컬 파일 시스템의 간단한 문자열 매칭(`grep` 스타일)으로 시작하는 것이 이 프로젝트 규모에 적합할 것으로 보입니다. 이 접근이 맞을까요?
**Answer:** 맞아 그냥 grep으로 처리하는게 깔끔할거야

**Q4:** 필터링에는 날짜 범위, 세션 상태(completed/failed 등), 그리고 최근 활동순 정렬이 포함되어야 한다고 봅니다. 추가로 과목이나 태그 기반 필터도 필요한가요?
**Answer:** 니가 말한 모든 필터링 기준 전부 있어야 해 (날짜 범위, 세션 상태, 최근 활동순 정렬)

**Q5:** 터미널 명령으로 관련 오디오, transcript, summary를 "다시 열기"한다는 것이, 해당 파일의 경로를 출력하거나 기본 편집기/플레이어에서 열어주는 것으로 이해하면 될까요? 아니면 TUI 내에서 내용을 바로 표시하는 것을 의미하나요?
**Answer:** reopen은 tui에서 출력이 아니라 finder나 file explorer에서 열어주면 돼

**Q6:** "recent-activity metadata"가 세션의 마지막 수정 시각을 기록하는 것으로 가정합니다. 맞나요?
**Answer:** 맞아

**Q7:** 기존 Typer 기반 CLI에 `lecture-auto library list`, `lecture-auto library search <query>`, `lecture-auto library open <session-id>` 형태의 서브커맨드를 추가하는 것으로 생각합니다. 다른 명령 구조를 선호하시나요?
**Answer:** 맞아. 그리고 lecture-auto library search --filter 옵션을 추가하는걸 잊지 마

**Q8:** 이 기능에서 제외해야 할 것이 있나요?
**Answer:** 니가 제시한 것들은 전부 OOS고 로드맵의 7번 항목이 제시하거나 암시하지 않는 모든 기능을 구현하는 것 또한 있는 파일을 불필요하게 수정하는 것 역시 OOS야.

### Existing Code to Reference
No similar existing features identified for reference.

### Follow-up Questions
No follow-up questions were needed.

## Visual Assets

### Files Provided:
No visual assets provided. (Confirmed via bash check of visuals/ folder)

## Requirements Summary

### Functional Requirements
- **Library List Command (`lecture-auto library list`):** 모든 상태의 세션을 SessionMetadataStore 메타데이터로부터 읽어 목록으로 표시
- **Library Search Command (`lecture-auto library search <query>`):** session_id와 요약본 `.md` 파일 내용을 대상으로 grep 스타일 문자열 매칭 검색 수행
- **Search Filter Option (`--filter`):** 검색 결과에 대해 날짜 범위, 세션 상태, 최근 활동순 정렬로 필터링 가능
- **Library Open Command (`lecture-auto library open <session-id>`):** 관련 오디오, transcript, summary 파일을 OS 기본 Finder/File Explorer에서 열기
- **Recent-Activity Metadata:** 세션의 마지막 수정 시각(transcript 수정, summary 생성 등)을 기록하여 최근 활동순 정렬에 활용
- **Filtering:** 날짜 범위 필터, 세션 상태 필터, 최근 활동순 정렬 모두 지원

### Reusability Opportunities
- No existing similar features identified by the user for reference.

### Scope Boundaries
**In Scope:**
- `lecture-auto library list` — 모든 상태의 세션 목록 표시 (필터 옵션 포함)
- `lecture-auto library search <query>` — session_id + 요약본 md 파일에 대한 grep 스타일 검색 (--filter 옵션 포함)
- `lecture-auto library open <session-id>` — 관련 파일을 Finder/File Explorer에서 열기
- Recent-activity metadata 기록 및 활용
- 날짜 범위, 세션 상태, 최근 활동순 정렬 필터링

**Out of Scope:**
- 클라우드 동기화
- 다중 사용자 지원
- AI 기반 시맨틱 검색
- 로드맵 7번 항목이 제시하거나 암시하지 않는 모든 기능
- 기존 파일의 불필요한 수정

### Technical Considerations
- CLI 프레임워크: Typer 기반 서브커맨드 (`library` 그룹)
- 검색 방식: 간단한 문자열 매칭 (grep 스타일), 전문 검색 엔진 불필요
- 검색 대상: session_id 와 요약본 `.md` 파일 2가지로 제한
- 파일 열기: macOS `open` 명령어 (또는 cross-platform `subprocess` 활용)으로 Finder에서 열기
- 데이터 저장: 로컬 파일 시스템 기반 (`recordings/`, `transcripts/`, `notes/`, `config/`)
- Python 3.11+, Pydantic 기반 검증
- 에러 처리: 사용자 친화적 메시지, 존재하지 않는 세션 등에 대한 명확한 에러
