# 작업 기록 - Gemini 500 오류 조사와 제한적 재시도

- 일시: 2026-11-16 (Asia/Seoul)
- 작성자: Codex
- 작업 유형: 오류 조사 / 버그 수정

## 확인된 사실

- 사용자가 보고한 메시지는 `500 internal error occured`이다.
- 설치된 앱은 0.1.16-dev이고 사용 중인 모델은 gemma-4-26b-a4b-it이다.
- 직전 정제 성공 로그 세 건의 입력 토큰은 4,233 / 3,815 / 3,967(합계 12,015)이며
  각각 출력 토큰도 기록돼 있다. 이 성공한 요청 자체로 사용량이 생긴다.
- 실제 관리형 SDK 3.0.0에서 기본 retry_options=None, 최대 시도 1회를 확인했다.
- 정제 결과는 모든 chunk 성공 후 저장되므로 일부가 성공해도 후속 실패 시 최종 파일은
  저장되지 않는다. 이후 수동 재실행은 앞 구간도 다시 요청한다.
- 500은 provider 내부 오류 분류이며 이 메시지만으로 구체적 서버 원인은 확정할 수 없다.

## 변경

- 공통 Gemini client에 HTTP 500/502/503/504 최대 2회(최초+재시도 1회)를 명시한다.
- 실패한 요청만 1~2초 backoff 후 재시도하고 이미 완료한 chunk는 다시 실행하지 않는다.
- 400/401/403/429는 재시도하지 않으며 모델과 사용자 설정도 자동 변경하지 않는다.
- 오류가 지속되면 기존 예외 경로로 종료한다. 실패 구간의 입력은 재시도로 다시 전송될 수 있다.
- 영구 checkpoint/수동 재실행 재개 기능은 추가하지 않았다.

## 검증

- 개발 SDK에서 모의 HTTP 500→200 복구, 지속 500의 2회 제한,
  400/403/429의 단일 시도, 후속 chunk 재시도 시 이전 chunk 비반복을 검증했다.
- 실제 관리형 SDK 3.0.0에서도 로컬 MockTransport로 500→200 복구를 검증했다.
- 실제 API 요청·사용자 키를 사용한 유료 호출은 실행하지 않았다.
- 전체 자동 테스트: 440 passed, 1 skipped (41.22s). 실제 서비스 통합 스크립트 2개 제외.
- git diff --check 통과. 로그: build/gemini-server-error-checks/checks.log, checks.exit = 0.
- 앱 재빌드·설치는 기존 보류 지시를 유지한다. 이번 수정은 소스에만 반영한다.

## 참고

- https://ai.google.dev/gemini-api/docs/generate-content/api-errors
- https://github.com/googleapis/python-genai/blob/main/google/genai/_api_client.py
