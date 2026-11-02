# 작업 기록 - AI 작업 FIFO 큐와 독립 오디오 처리

- 일시: 2026-11-03 00:33 (Asia/Seoul)
- 작성자: Codex
- 에이전트: Codex
- 작업 유형: 버그 수정

## 요약

- GUI 전사·전사문 정제·노트 미리보기/저장을 같은 FIFO 대기열에서 요청 순서대로 하나씩 실행한다.
- 같은 세션의 후속 요청도 허용한다. 예: 전사 → 보정 → 다른 전사 → 요약.
- 녹음 시작/중지, 오디오 가져오기, 볼륨 보정, 노이즈 제거는 별도 풀로 실행한다.
- Whisper가 바쁠 때 추가 단발 프로세스를 만드는 병렬 fallback을 제거했다.

## 변경 범위

- 대기 요청 취소 시 실행 없이 제거하고, 실패·취소 후 다음 요청을 시작한다.
- 전체 취소/앱 종료 시 대기 작업도 취소한다. 대기열은 메모리에만 보관한다.
- 작업 목록을 접수 순서로 표시하고 실행·대기 개수를 나누어 표시한다.
- 같은 세션의 대기 전사를 취소해도 실행 중인 전사 진행률을 지우지 않는다.
- runtime 직접 동시 호출도 Whisper 요청을 직렬화하며, 대기 중 취소가 실행 중 worker를 종료하지 않는다.
- CLI/세션 파일 형식과 사용자 데이터는 바꾸지 않았다. 이미 순차 호출하는 CLI/TUI 흐름은 유지한다.

## 주요 변경 파일

- `src/lecture_auto/gui/jobs.py`, `src/lecture_auto/gui/app.py`
- `src/lecture_auto/local_runtime.py`
- `tests/test_gui_jobs.py`, `tests/test_gui_smoke.py`, `tests/test_local_runtime_concurrency.py`
- `docs/01-folder-architecture.md`, `docs/02-specs.md`, `docs/03-product-plan.md`, `docs/README.ko.md`

## 검증

- 관련 테스트 초기 실행: 40 passed.
- 최종 전체 테스트: 388 passed, 1 skipped, 2 warnings (33.98초). 경고는 기존 Ollama 테스트 반환값 경고다.
- 혼합 작업 FIFO, 같은 세션 후속 요청, 오류/취소 후 진행, 대기 취소/전체 취소, 독립 오디오 실행을 검증했다.
- GUI에서 막힌 전사/요약 대기열과 별개로 녹음 시작·중지가 동작하는 것을 Noop capture adapter로 검증했다.
- 합성 worker 프로세스로 한 worker 재사용, 대기 중 취소, 오류/비정상 종료/timeout 후 재생성, 오디오 runtime 독립 실행을 검증했다.
- `git diff --check` 통과. 실제 녹음 장치와 외부 STT/LLM API는 사용하지 않았다.

## 리스크/이슈

- 대기열은 앱 종료 시 사라지며 자동 복원하지 않는다.
- 실제 강의 자료를 사용한 provider 통합 실행은 미검증이다.
- 당시 버전 `0.1.11+hotfix`의 macOS 재빌드는 종료 코드 0으로 완료되었다. ARM64/경량 패키징, Ollama 경로 GUI smoke test, ad-hoc 서명을 통과했다. 후속 `0.1.12` 릴리스는 별도 재빌드한다.

## 다음 작업

- 후속 `0.1.12` 릴리스 빌드 및 GitHub Actions 결과를 확인한다.
- 명령: `PYTHON=/Applications/lecture_auto/.venv311/bin/python UV=/Applications/lecture_auto/.venv311/bin/uv scripts/build_macos_app.sh`
- PID 파일: `/Applications/lecture_auto/build/logs/serial-queue-build.pid`
- 로그: `/Applications/lecture_auto/build/logs/serial-queue-build.log`
- 종료 코드: `/Applications/lecture_auto/build/logs/serial-queue-build.exit`
- 출력: `build/macos/Lecture Auto.app` (Applications 설치는 포함하지 않음).

## 참고

- 관련 문서: `docs/02-specs.md`, `docs/03-product-plan.md`
