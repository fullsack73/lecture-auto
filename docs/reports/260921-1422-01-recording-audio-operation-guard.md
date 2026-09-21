# 작업 기록 - 녹음 중 오디오 작업 충돌 방지

- 일시: 2026-09-21 14:22 (KST)
- 작성자: Codex
- 에이전트: Codex
- 작업 유형: 버그 수정

## 요약

- 녹음 중인 세션의 미완성 오디오를 볼륨/노이즈 보정, 가져오기, 전사가 읽지 못하도록 차단했다.

## 변경 범위

- `SessionService`에서 녹음·종료 처리 상태를 공통 검증한다.
- GUI에서 녹음 중 충돌 가능한 오디오 작업 버튼을 비활성화한다.

## 주요 변경 파일

- `src/lecture_auto/session_service.py`
- `src/lecture_auto/gui/app.py`
- `tests/test_session_business_rules.py`
- `tests/test_gui_smoke.py`

## 검증

- `PYTHONPATH=. ./.venv/bin/pytest -q`: 343 passed, 1 skipped

## 리스크/이슈

- 서로 다른 완료 세션의 FFmpeg 작업은 불필요하게 직렬화하지 않는다.

## 다음 작업

- 없음

## 참고

- 관련 문서: `docs/02-specs.md`
