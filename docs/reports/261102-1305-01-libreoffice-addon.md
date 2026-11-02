# 작업 기록 - LibreOffice 애드온

- 일시: 2026-11-02 13:05 (Asia/Seoul)
- 작업 유형: 기능 추가

## 요약

- macOS 설정 및 CLI에 LibreOffice 관리형 설치와 상태 확인을 추가했다.
- 공식 설치 이미지의 SHA-256을 검증하고 기존 관리형 설치를 보존한다.
- 기존 시스템 설치도 탐색하며 PPT/PPTX 변환 결과는 임시 폴더에 생성한다.

## 검증

- LibreOffice 설치·탐색 및 변환, GUI와 runtime 회귀 테스트: 61 passed.
- CLI 도움말 및 runtime status JSON 확인.
- 실제 LibreOffice 설치 이미지 다운로드 및 타 플랫폼 실기기 검증은 수행하지 않았다.

## 리스크/이슈

- 자동 설치는 macOS 전용이다. Windows/Linux는 기존 설치가 필요하다.
- LibreOffice 기본 설치는 최신 HWP/HWPX 변환을 제공하지 않는다.
