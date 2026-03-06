# Spec Requirements: Lecture Session Capture Flow

## Initial Description
Lecture Session Capture Flow — Build an end-to-end recording workflow where users can create a lecture session, start/stop system-audio capture, and view saved session history via terminal commands. Include local session metadata storage and success/failure states users can verify in tests.

## Requirements Discussion

### First Round Questions

**Q1:** I assume this feature is purely CLI-driven with Typer commands (no GUI/web), and the core flow is `session create` -> `capture start` -> `capture stop` -> `session history`. Is that correct, or do you want a different command structure?
**Answer:** 맞아 그대로 가면 돼. 근데 session_history 단계에서 녹음본 전사, 가공, 노트생성이 이뤄저야 해. 강의 끝나자 마자 생성하는게 아니라 오디오 파일은 보존한 상태로 집에 와서 노트를 생성할 수 있게끔 이 점을 참조해줘

**Q2:** I'm assuming a lecture session should include metadata like `session_id`, `title`, `course(optional)`, `started_at`, `ended_at`, `status`, and `audio_file_path(optional at this stage)`. Is that correct, or should we keep a smaller/larger metadata set?
**Answer:** started at, ended at은 date로 통합하도록 하고 title이랑 course는 유저가 입력하는 것을 상정하되, 입력이 없어도 작동해야 하고, 입력이 없는 경우 llm이 transcript를 기반으로 title과 course 이름을 생성하도록 만들어줘

**Q3:** I assume metadata storage should be local filesystem (for example a JSON/JSONL or SQLite file under `config/` or a dedicated local data folder), with deterministic structure for tests. Should we standardize on one storage format now, and if so which do you prefer?
**Answer:** 맞아, 표준화된 json파일로 되어있도록 만들어줘

**Q4:** I'm thinking system-audio capture should support clear runtime states: `idle`, `recording`, `stopping`, `completed`, `failed`, and prevent invalid transitions (e.g., start while already recording). Should we enforce strict state transition validation like this?
**Answer:** 맞아 invalid transition을 막는게 좋아.

**Q5:** I assume CLI output should be human-readable first, with optional machine-friendly output (like `--json`) to make integration tests more robust. Is that correct, or do you want plain text only for now?
**Answer:** cli output이 뭘 말하는건지 역으로 묻고싶어.

**Q6:** I'm assuming failure handling should explicitly cover: audio device unavailable, FFmpeg/PyAudio dependency missing, permission denied, interrupted capture, and write failures, with actionable error messages and non-zero exit codes. Is that the expected failure scope for this spec?
**Answer:** 맞아 그렇게 해줘

**Q7:** I assume "saved session history" means listing sessions with filtering/sorting basics (e.g., recent first, optional status filter), and showing enough info to identify outcomes quickly. Should history also support detail view by `session_id` in this spec, or keep that for a later spec?
**Answer:** session_id에 따라 디테일하게 볼 수 있는 기능도 추가해줘

**Q8:** I assume out-of-scope for this spec is transcription/summarization processing itself, and we only prepare session+capture artifacts that later roadmap items consume. Is that correct, and is there anything else you explicitly want excluded?
**Answer:** 맞아 지금은 세션 준비, 오디오 녹음만 하면 돼.

### Existing Code to Reference
No similar existing features identified for reference.

### Follow-up Questions

**Follow-up 1:** 각 명령(`session create/start/stop/history/detail`)에 `--json` 옵션을 넣어 테스트 친화적으로 갈까요, 아니면 이번 스펙에서는 텍스트 출력만으로 제한할까요?
**Answer:** 맞아, 플레인 텍스트를 기반으로 하되 --json 플레그가 있으면 한줄 출력이 되도록 만들어줘.

## Visual Assets

No visual assets provided.

## Requirements Summary

### Functional Requirements
- CLI(Typer) 기반으로 `session create`, `capture start`, `capture stop`, `session history`, `session detail(session_id)` 흐름을 제공한다.
- 녹음 직후 즉시 전사/가공/노트 생성을 강제하지 않고, 오디오 파일을 보존한 상태로 이후 시점(예: 귀가 후)에 노트 생성 파이프라인으로 이어질 수 있도록 세션 이력 단계에서 연결 가능성을 고려한다.
- 세션 메타데이터는 표준화된 로컬 JSON 파일에 저장한다.
- 메타데이터는 날짜 필드를 `date`로 통합하고, `title`/`course`는 사용자 입력을 우선하되 미입력 시에도 동작해야 한다.
- `title`/`course`가 미입력인 경우 transcript 기반 LLM 생성 경로를 지원하도록 요구사항에 포함한다.
- 캡처 상태 전이는 `idle`, `recording`, `stopping`, `completed`, `failed`를 기준으로 하고 invalid transition을 차단한다.
- CLI 출력은 기본 플레인 텍스트로 제공하고, `--json` 플래그 사용 시 한 줄(one-line) JSON 출력으로 제공한다.
- 실패 케이스(오디오 장치 불가, FFmpeg/PyAudio 누락, 권한 문제, 중단, 저장 실패)에 대해 actionable 메시지와 non-zero exit code를 제공한다.

### Reusability Opportunities
- 현재 사용자로부터 명시된 유사 기능/경로 정보는 없음.
- 스펙 작성 단계에서 기존 CLI 명령 패턴, 상태 전이 처리 로직, 로컬 JSON 저장 유틸 여부를 재확인할 필요가 있다.

### Scope Boundaries
**In Scope:**
- 세션 생성 및 메타데이터 저장
- 시스템 오디오 녹음 시작/중지
- 세션 이력 조회 및 `session_id` 기반 상세 조회
- 상태 전이 검증 및 에러 처리
- 기본 텍스트 출력 + `--json` 한 줄 출력

**Out of Scope:**
- 본 스펙에서 실제 전사(STT), 가공(refine), 노트 생성 실행 자체
- 고급 검색/필터링 확장, 공유/내보내기 기능
- 웹 UI/계정 시스템

### Technical Considerations
- Python 3.11+ / Typer 기반 CLI 아키텍처와 일치해야 한다.
- 로컬 파일시스템 중심 구조(`recordings/`, `transcripts/`, `notes/`, `config/`)와 정합성을 맞춰 JSON 저장 위치를 정의해야 한다.
- 테스트 가능성을 위해 JSON 스키마와 CLI 출력 형식(텍스트/JSON)을 결정론적으로 유지해야 한다.
- `title`/`course` LLM 생성은 transcript 존재를 전제로 하므로, 현재 스펙 범위에서는 후속 파이프라인 연계 지점으로 정의해야 한다.
- 오류 메시지는 사용자 친화적이며 조치 가능한 형태로 제공하고, 종료 코드는 명시적으로 관리해야 한다.
