# 작업 기록 - 로컬 macOS 빌드 버전 인수

- 일시: 2026-11-16 (Asia/Seoul)
- 작성자: Codex
- 작업 유형: 기능 추가

## 변경

- macOS 빌더에 `--version 0.1.16-dev`와 도움말을 추가했다.
- `--install` 옵션 순서를 자유롭게 처리하고 누락·잘못된 형식·중복 버전·미지원 인수는
  빌드 파일이나 환경을 변경하기 전에 거부한다.
- 기본 버전은 pyproject.toml에서 읽고 원본 버전을 변경하지 않는다.
- macOS 표준 버전 필드는 숫자로 유지하며 전체 표시 버전은 번들
  LectureAutoDisplayVersion, GUI, 빌드 기록과 완료 출력에서 확인한다.
- 번들 plist 변경 후 서명한 다음 smoke 검증을 실행한다.
- 기존 앱 이름·출력·설치 경로와 실행 중 앱 교체 방지는 유지한다.

## 검증

- 가짜 빌드 도구로 기본 버전, override, 옵션 순서, 잘못된 인수, 경로 공백,
  plist와 빌드 기록, GUI 표시 및 기존 번들 fallback을 검증한다.
- 실제 Nuitka 빌드·설치는 실행하지 않는다. 기존 로컬 빌드 보류 지시를 유지한다.

- 관련 테스트 40개 통과. 전체 자동 테스트 434 passed, 1 skipped (35.76s).
- 실제 서비스 통합 스크립트 2개는 제외했다. zsh 구문 및 git diff --check 통과.
- 전체 로그: build/local-build-version-checks/checks.log, checks.exit = 0.

## 근거

- Apple CFBundleShortVersionString 형식: https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleshortversionstring
