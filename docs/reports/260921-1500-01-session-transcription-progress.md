# 작업 기록 - 세션 목록 전사 진행률

- 일시: 2026-09-21 15:00 (KST)
- 작성자: Codex
- 에이전트: Codex
- 작업 유형: 기능 추가

## 요약

- 전사 중인 세션 목록 행에 백분율과 좌→우 녹색 게이지를 표시한다.

## 변경 범위

- 기존 GUI 작업 progress 신호를 세션 목록 표현에 연결했다.
- 로컬 전사의 초 단위 실수 progress가 UI까지 전달되도록 보존했다.

## 주요 변경 파일

- `src/lecture_auto/gui/app.py`
- `src/lecture_auto/session_service.py`
- `src/lecture_auto/tasking.py`
- `tests/test_gui_smoke.py`

## 검증

- `pytest -q tests/test_gui_smoke.py`
- `pytest -q`

## 리스크/이슈

- API STT는 provider가 중간 progress를 제공하지 않으므로 전사 실행 중 10%에서 완료 시점까지 유지된다.

## 다음 작업

- 없음.

## 참고

- 관련 문서: `docs/03-product-plan.md`
