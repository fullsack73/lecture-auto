# 작업 기록 - macOS 빌드 경로와 앱 이름 고정

- 일시: 2026-11-03 00:24 (Asia/Seoul)
- 작성자: Codex
- 에이전트: Codex
- 작업 유형: 버그 수정

## 요약

- macOS 빌드 출력은 `build/macos/Lecture Auto.app`으로 고정했다.
- `BUILD_DIR` 환경변수로 버전별 출력 폴더가 생기는 것을 막고, Nuitka 내부 번들을 설치 대상과 같은 이름으로 바꾼 뒤 검증/서명한다.
- 빌드 경로의 앱이 실행 중이면 덮어쓰기 전에 중단한다.

## 변경 범위

- 기존 `macos-parallel-fix`, `macos-v0.1.11-hotfix` 빌드 폴더는 실행 중인 앱이 없는지 확인한 뒤 `build/archive/261103-macos-naming/`으로 보관했다.
- 앱 내부 실행 파일 `LectureAuto`, bundle ID `com.anarchytoast.lectureauto`, 앱 버전은 유지한다.

## 주요 변경 파일

- `scripts/build_macos_app.sh`
- `tests/test_build_macos_app.py`
- `docs/02-specs.md`, `docs/setup.md`, `docs/setup.ko.md`, `deployment/README.md`

## 검증

- 관련 테스트: 13 passed.
- 전체 테스트: 383 passed, 1 skipped, 2 warnings (40.79초). 경고는 기존 Ollama 테스트의 반환값 관련 경고다.
- `zsh -n scripts/build_macos_app.sh`, `git diff --check`: 통과.
- 공백이 있는 경로, 기존 번들 교체, `BUILD_DIR` 무시, `--install` 경로의 번들 이름 일치를 가짜 도구로 실행해 확인했다.
- Python 3.11.15 ARM64와 PySide6 6.11.1 빌드 환경을 확인했다.

## 리스크/이슈

- 해당 macOS 재빌드는 종료 코드 0으로 완료되었다. `build/macos/Lecture Auto.app` 생성, ARM64/경량 패키징 검증, Ollama 경로 GUI smoke test, ad-hoc 서명 완료를 로그에서 확인했다.
- 명령: `PYTHON=/Applications/lecture_auto/.venv311/bin/python UV=/Applications/lecture_auto/.venv311/bin/uv scripts/build_macos_app.sh`
- PID: 13438 (`build/logs/macos-name-fix-build.pid`)
- 로그: `/Applications/lecture_auto/build/logs/macos-name-fix-build.log`
- 종료 코드 파일: `/Applications/lecture_auto/build/logs/macos-name-fix-build.exit`
- 빌드 스크립트는 패키징/GUI smoke 검증과 ad-hoc 서명을 수행한다. 이번 명령에는 설치를 포함하지 않았다.

## 다음 작업

- 이후 FIFO 큐 변경은 별도 재빌드로 검증한다.

## 참고

- 관련 문서: `docs/02-specs.md`, `docs/setup.ko.md`
