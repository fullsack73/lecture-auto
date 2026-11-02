# 작업 기록 - 병렬 전사 runtime 오류 격리

- 일시: 2026-11-03 00:00 (Asia/Seoul)
- 작성자: Codex
- 작업 유형: 버그 수정

## 요약

- 재사용 Whisper worker는 하나의 잠금으로 전사를 직렬 처리했으며, 추가 요청의 idle 정리는 실행 중인 worker도 300초 경과 후 종료했다.
- 첫 작업이 실패하면 이미 같은 worker를 기다리던 다음 작업도 `Warm local AI worker is not running.`으로 실패하는 경로를 모의 프로세스로 재현했다.
- 실행 중인 worker를 idle 정리에서 제외하고, 바쁜 worker에 대한 추가 요청은 기존 단발 worker 경로로 병렬 실행한다.
- worker 실패 시 잠금을 반환하기 전에 프로세스를 정리해 다른 요청이 실패한 worker를 재사용하지 않도록 한다. 대기 중인 요청의 취소도 처리한다.

## 변경 범위

- 공용 local runtime과 회귀 테스트, STT 실행 규칙 및 사용자 문서.
- 모델·오디오·세션 데이터와 공개 CLI 응답 형식은 변경하지 않았다.

## 주요 변경 파일

- `src/lecture_auto/local_runtime.py`
- `tests/test_local_runtime_concurrency.py`
- `docs/02-specs.md`, `docs/03-product-plan.md`, `docs/README.ko.md`

## 검증

- 전체 테스트: 381 passed, 1 skipped, 기존 Ollama 테스트의 반환값 경고 2개.
- 새 회귀 테스트 12개: 병렬 실행, 유휴 기준 초과 시 실행 중 worker 보호, 양쪽 worker의 오류·비정상 종료·취소·timeout 격리, 실패 뒤 재시도, warm 재사용, 대기 중 취소.
- 관리형 Python 3.11 / 실제 faster-whisper base 모델 / 합성 2초 오디오로 두 worker를 동시에 시작하고 완료했으며, 후속 요청의 `warm_start=true`를 확인했다. 합성 오디오는 음성 내용과 전사 품질 검증용이 아니다.
- `git diff --check` 통과.
- macOS ARM64 앱 재빌드·패키징 smoke 및 설치 검증이 완료되었다 (`build/macos-parallel-fix.log`, 종료 코드 0). 이후 hotfix 버전 앱은 별도 경로에 생성한다.

## 리스크/이슈

- 병렬 전사는 모델과 오디오를 각 프로세스에 로드하므로 메모리·CPU 사용량이 증가한다.
- 실제 사용자 강의 전체의 전사 완료 및 품질은 검증하지 않았다.
- 첫 segment 결과 전까지의 진행률은 기존처럼 0%이며 임의의 진행률을 만들지 않는다.

## 참고

- 관련 문서: `docs/02-specs.md`, `docs/03-product-plan.md`
