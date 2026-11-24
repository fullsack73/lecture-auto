# 작업 기록 - OpenRouter 애드온

- 일시: 2026-11-23 13:31 (Asia/Seoul)
- 작성자: Codex
- 작업 유형: 기능 추가

## 변경 범위

- GUI 애드온과 CLI에서 관리형 Python에 OpenAI SDK를 설치한다. 데스크톱 번들에서는 SDK를 제외한다.
- OpenRouter 모델로 전사문을 정제하고 JSON 노트 하네스를 실행한다. API 키는 Gemini 키와 별도로 OS 자격 증명 저장소에 보관한다.
- 기본 모델 ID는 `openrouter/auto`다. 노트에는 JSON 모드를 요구한다. 첨부 PDF는 현재 Gemini에서 지원한다.

## 검증

- 모의 SDK로 전사 정제, 노트 생성, 오류 전달, 자격 증명 분리 경로를 검증했다.
- 실제 API 호출과 신규 데스크톱 번들 빌드는 실행하지 않았다.
