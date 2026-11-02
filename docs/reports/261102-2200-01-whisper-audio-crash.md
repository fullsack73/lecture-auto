# 작업 기록 - 로컬 전사 오디오 디코딩 충돌

- 일시: 2026-11-02 (Asia/Seoul)
- 작업 유형: 버그 수정

## 요약

- macOS 충돌 기록에서 faster-whisper의 PyAV AudioFifo 네이티브 충돌을 확인했다. 종료 시 출력된 세마포어 경고는 이 충돌 후 나타났다.
- 번들 FFmpeg로 16kHz 단일 채널 PCM을 디코딩하여 Whisper에 전달하고, 품질 재전사 시에도 재사용한다.

## 검증

- 전체 테스트: 369 passed, 1 skipped, 경고 2개.
- 실제 관리형 Whisper runtime과 합성 오디오로 전사 smoke test를 통과했다.
- macOS arm64 앱 빌드 및 패키징 smoke test를 통과했다.
- 실제 사용자 녹음의 전체 전사는 수행하지 않았다.
