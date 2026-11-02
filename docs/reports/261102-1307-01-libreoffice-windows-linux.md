# 작업 기록 - Windows/Linux LibreOffice 애드온 설치

- 일시: 2026-11-02 13:07 (Asia/Seoul)
- 작업 유형: 기능 추가

## 요약

- Windows와 Linux에서 공식 LibreOffice 설치 파일을 checksum 검증 후 사용자 runtime에 설치한다.
- 실행 검증에 성공한 경우에만 기존 관리형 설치를 교체하며 시스템 LibreOffice는 변경하지 않는다.
- Windows MSI 관리 이미지와 Linux DEB 패키지를 관리자 권한 없이 분리된 경로에 풀어 설치한다.

## 검증

- 플랫폼 설치·실패 복구·경로 탐색 및 GUI/runtime 테스트: 75 passed.
- 실제 Windows/Linux 장치의 설치 및 변환은 검증하지 못했다.

## 리스크/이슈

- Linux 보안 압축 해제에는 Python 3.11.4 이상이 필요하다.
- HWP/HWPX 변환은 LibreOffice 기본 설치에서 지원되지 않는다.
