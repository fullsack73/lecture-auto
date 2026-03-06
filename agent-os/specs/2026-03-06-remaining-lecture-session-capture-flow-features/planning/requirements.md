# Spec Requirements: remaining-lecture-session-capture-flow-features

## Initial Description
로드맵에는 체크가 되어있어서 일단 수정하긴 헸는데, 로드맵 1번에 구현되어 있지 않은 나머지 기능에 대해서 #file:1-new-spec.md 프롬프트를 실행해줘

## Requirements Discussion

### First Round Questions

**Q1:** I assume this spec should focus on 로드맵 1번의 미구현 잔여 기능만 다루고, 로드맵 2번 이후 기능은 제외하는 게 맞나요? 아니면 2번 이후 일부도 이번 스펙에 포함할까요?
**Answer:** 맞아 1번의 잔여 기능을 구현하는게 목표고 그 이외는 OOS야

**Q2:** I’m assuming the highest priority is 실제 오디오 캡처 실행(FFmpeg/PyAudio/SoundCard 연동) 입니다. 맞다면 1순위 구현을 `capture start/stop`의 실제 녹음 프로세스 연결로 잡아도 될까요?
**Answer:** 맞아 최고 우선순위 기능은 capture start/stop 야

**Q3:** I’m thinking `session create -> capture start -> capture stop -> session history -> session detail`의 CLI 플로우를 실제 파일 생성까지 end-to-end로 보장해야 한다고 보는데, 이 수준을 이번 완료 기준으로 삼을까요?
**Answer:** 역으로 질문하고 싶은데 세션 생성부터 요약 노트 생성까지 전부 구현하는걸 목표로 하겠다는 거야?

**Q4:** I assume 녹음 파일 저장 경로는 기본 `recordings/`이고, 세션별 파일명은 결정론적으로(예: `recordings/{session_id}.wav`) 관리하면 좋겠습니다. 이 규칙으로 갈까요, 아니면 날짜/코스 포함 네이밍을 원하시나요?
**Answer:** 세션 id만 포함해줘

**Q5:** I’m assuming 실패 시나리오(장치 없음, 권한 거부, FFmpeg 미설치, 중단)는 명시적 에러 코드 + 다음 행동 안내를 유지해야 합니다. 현재 에러 계약을 그대로 강화하는 방향이 맞나요?
**Answer:** 맞아 현재의 에러 핸들링 방법을 유지해야해

**Q6:** I assume 테스트 범위는 통합 중심으로, 실제 장치 의존 테스트 대신 mock 기반 핵심 경로 + 실패 매핑 검증을 우선하고, 필요 시 수동 점검 절차를 문서화하는 게 맞나요?
**Answer:** 실제 장치 사용을 전제로 태스트 해줘

**Q7:** I’m thinking 이번 스펙에서는 터미널 UX는 이미 정의된 포맷을 유지하고, 녹음 실행 로직과 저장 일관성 쪽에 집중하는 게 적절해 보입니다. UI 텍스트 변경도 함께 원하시나요?
**Answer:** 정의된 포맷을 유지하는게 맞긴 한데 지금 UI 텍스트가 구현이 안되어있는걸로 아는데 수정할게 있을까 싶네

**Q8:** 마지막으로, 이번 스펙에서 명확히 제외할 항목(예: STT, transcript 편집, 요약 생성, export)이 있다면 무엇인가요?
**Answer:** 로드맵 1번 항목에서 명시하지 않는 모든 기능 + 저번 spec #file:2026-03-06-lecture-session-capture-flow 에서 구현한 기능이 OOS야

### Existing Code to Reference
Based on user's response about similar features

**Similar Features Identified:**
- Feature: Previous spec artifacts for Lecture Session Capture Flow - Path: `agent-os/specs/2026-03-06-lecture-session-capture-flow/`
- Components to potentially reuse: Existing session metadata store, lifecycle/business-rule service, CLI output formatting contracts from the previous spec deliverables
- Backend logic to reference: Task group implementation outputs documented in the previous spec's `implementation/` and validation behavior from `verification/` and `verifications/`

### Follow-up Questions

**Follow-up 1:** `6번`에서 “실제 장치 사용 전제 테스트”라고 하셨는데, 자동화 테스트는 mock 유지 + 실제 장치 수동 검증 절차(명령/기대결과) 추가로 갈까요, 아니면 자동화 테스트 자체도 실제 장치 의존으로 강제할까요?
**Answer:** mock 유지 + 실제 장치 수동 검증으로 해줘

**Follow-up 2:** `8번`의 “이전 spec에서 구현한 기능이 OOP”는 기존 구현 기능은 재구현/확장 대상이 아니라 변경 최소화(필요한 연동 수정만 허용)라는 의미가 맞나요?
**Answer:** OOP가 아니라 OOS를 치려고 한거야 오타임.

## Visual Assets

### Files Provided:
No visual assets provided.

### Visual Insights:
- Visual check was executed on `agent-os/specs/2026-03-06-remaining-lecture-session-capture-flow-features/planning/visuals/`
- No `.png/.jpg/.jpeg/.gif/.svg/.pdf` files found
- No visual design constraints inferred from assets

## Requirements Summary

### Functional Requirements
- Implement only the remaining, not-yet-implemented functionality within Roadmap item 1
- Highest-priority implementation target is real audio capture execution for `capture start/stop`
- Maintain the Roadmap 1 command flow scope: `session create -> capture start -> capture stop -> session history -> session detail`
- Persist recording outputs under `recordings/` with file naming that includes session ID only
- Maintain existing error handling approach: explicit error codes and actionable next-step guidance
- Keep currently defined output formatting contract for CLI responses

### Reusability Opportunities
- Reuse previously implemented patterns from `agent-os/specs/2026-03-06-lecture-session-capture-flow/`
- Reuse existing metadata persistence and lifecycle contract patterns where possible
- Reuse existing CLI output contract patterns to avoid unnecessary UX contract drift

### Scope Boundaries
**In Scope:**
- Remaining implementation gaps for Roadmap item 1 only
- Real device-backed capture execution wiring for start/stop
- Integration updates needed to connect real capture with existing session lifecycle/history/detail flow
- Mock-based automated tests plus manual real-device verification procedures

**Out of Scope:**
- Any roadmap features outside item 1
- STT pipeline, transcript review/edit, transcript refinement, summary generation, notes library, export/share package
- Rebuilding already completed features from previous spec unless minimal integration adjustment is required

### Technical Considerations
- Terminal-first Python CLI architecture must be preserved
- Audio processing stack target remains FFmpeg + PyAudio/SoundCard integration
- Testing strategy: keep automated tests deterministic with mocks and supplement with documented manual real-device validation
- Existing code/document artifacts from prior spec should be referenced for implementation consistency
