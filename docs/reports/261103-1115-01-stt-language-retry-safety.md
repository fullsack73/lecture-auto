# 작업 기록 - 무음 언어 감지 및 재전사 품질 보호

- 일시: 2026-11-03 (Asia/Seoul)
- 작성자: Codex
- 작업 유형: 버그 수정

## 요약

- 시작 무음에서 언어를 감지한 뒤 그 언어를 재전사까지 강제하는 경로를 수정했다.
- PyAV 충돌을 피하는 FFmpeg 디코딩은 유지했다.
- 재전사에 실제 구간 PCM만 전달하고, 원문보다 나쁜 후보가 원문을 덮어쓰지 않도록 했다.

## 변경 범위

- 자동 언어 감지에만 VAD를 사용한다. 60초 단위로 검사해 실제 음성을 최대 90초
  모으고 30초씩 최대 3회 감지한다. 확률 0.8 이상이면 채택하며, 그 외에는
  다수결과 확률로 선택한다. 명시한 언어와 본 전사의 VAD 설정은 유지한다.
- 자동 감지 확률과 감지 방식을 sidecar metadata에 보존한다. 낮은 확률의 언어는
  재전사에 강제하지 않고, 구간의 VAD 적용 후 다시 감지한다. 음성이 없는 입력은
  언어를 추측하지 않고 명확한 오류를 반환한다.
- 재전사 PCM을 시간 구간으로 잘라 VAD를 적용하고, segment/word 시간을 원본
  기준으로 복원한다. 기존의 추측에 의한 상대/절대 timestamp 보정은 제거했다.
- 빈 후보, 품질 경고, 구간 이탈, 원문 segment의 시간 누락, 문자 수 절반 이상
  축약은 교체하지 않는다. 길이 가중 confidence 점수가 개선된 구간만 채택한다.

## 주요 변경 파일

- `src/lecture_auto/local_ai_worker.py`
- `src/lecture_auto/stt_quality.py`
- `tests/test_stt_transcription_safety.py`
- 기존 worker/재전사 회귀 테스트 및 `docs/02-specs.md`

## 검증

- 관련 테스트 최초 실행: 28 passed.
- 전체 테스트 1차 실행: 402 passed, 1 skipped, 기존 Ollama 반환값 경고 2개.
- 실제 관리형 Python 3.11 / faster-whisper 1.2.1 / medium CPU int8에서 문제 녹음을
  읽어 수정된 언어 감지만 검증했다. 기존 sidecar의 `cy` 0.5582 대신 `en` 0.8015를
  반환했다. 짧은 앞 2분만 검사했을 때는 `ko` 0.6200이었으므로, 짧은 샘플의
  낮은 확률을 재전사까지 강제하지 않는 규칙도 유지한다.
- 샘플 경계 반올림 회귀 테스트 추가 후 최종 전체 테스트: 403 passed, 1 skipped,
  기존 Ollama 반환값 경고 2개 (37.26초). `git diff --check` 통과.

## 리스크/이슈

- confidence와 길이/반복 검사는 보수적인 교체 기준이며 실제 내용의 정확도를
  보장하지 않는다. 유효한 축약/교정도 거부해 원문이 남을 수 있다.
- 전체 강의의 전사 정확도 A/B와 설치된 macOS 앱 재빌드/교체는 수행하지 않았다.
- 사용자 녹음, 기존 전사문과 설정은 변경하지 않았다. 실음성 확인용 스크립트와
  로그는 ignore 대상인 `build/stt-safety-checks/`에만 두었다.

## 참고

- `docs/02-specs.md`
- faster-whisper 공개 API와 지연 segment generator 동작:
  https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py
