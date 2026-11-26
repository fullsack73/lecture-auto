# 작업 기록 - 무음 녹음 전사

- 일시: 2026-11-26 13:13 (Asia/Seoul)
- 작성자: Codex
- 에이전트: Codex
- 작업 유형: 버그 수정

## 요약

- STT가 전사할 발화를 반환하지 않으면 원본 Markdown에 `음성이 감지되지 않았습니다.`를 저장하고 전사를 성공 처리한다.

## 변경 범위

- 로컬 Whisper는 자동 언어 감지에서 발화를 찾지 못하면 추론을 건너뛰고, 언어와 발화 구간을 비운 결과와 `no_speech` 감지 상태를 반환한다.
- CLI, TUI, GUI가 사용하는 공용 전사 저장 경로에서 안내 문구를 기록한다.

## 주요 변경 파일

- `src/lecture_auto/local_ai_worker.py`
- `src/lecture_auto/session_service.py`

## 검증

- 전사 관련 테스트 34개 통과.
- 1초 무음 WAV를 로컬 Whisper `base`로 전사해 정상 완료 상태, Markdown 안내 문구와 STT sidecar를 확인했다.
- 전체 테스트 466개 통과, 1개 건너뜀. Ollama 통합 테스트 3개는 서비스의 HTTP 402 응답으로 실패했다.

## 리스크/이슈

- 검증한 앱 실행 경로는 소스 워크스페이스와 로컬 Whisper 런타임이다.
