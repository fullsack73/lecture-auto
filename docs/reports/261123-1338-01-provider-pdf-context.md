# 작업 기록 - OpenRouter·Ollama PDF 참고문

- 일시: 2026-11-23 13:38 (Asia/Seoul)
- 작성자: Codex
- 작업 유형: 기능 추가

## 변경 범위

- OpenRouter는 PDF를 한 번 첨부해 참고문을 만든다.
- Ollama 비전 모델은 페이지 이미지를 읽고, 텍스트 모델은 PDF의 텍스트 레이어를 사용한다.
- 참고문은 8,000자로 제한하고 노트 생성에 재사용한다.

## 검증

- OpenRouter 파일 요청과 노트 참고문 전달을 모의 SDK로 검증했다.
- 생성한 PDF로 Ollama 텍스트 추출과 PNG 렌더링을 검증했다.
