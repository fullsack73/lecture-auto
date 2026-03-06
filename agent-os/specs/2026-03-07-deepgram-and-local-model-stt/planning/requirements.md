# Spec Requirements: deepgram-and-local-model-stt

## Initial Description
Deepgram api랑 로컬 모델 받아서 돌리는 기능을 구현하는 것

## Requirements Discussion

### First Round Questions

**Q1:** Deepgram API 통신 방식: Deepgram 연동 시 공식 Python SDK (`deepgram-sdk`)를 추가하여 사용하는 것을 가정해도 될까요? 아니면 의존성 추가를 최소화하기 위해 기본 HTTP 라이브러리(`httpx` 또는 `requests`)를 통해 직접 API를 호출할까요? (안정성을 위해 공식 SDK 사용을 권장합니다)
**Answer:** 어 deepgram sdk 사용 하는것으로 하자

**Q2:** 로컬 모델 종류: 로컬에서 구동할 모델 아키텍처는 오픈소스인 Whisper를 염두에 두고 계신가요? 만약 그렇다면 성능과 속도가 보장되는 `faster-whisper` 패키지(혹은 `openai-whisper`)를 사용하는 것이 어떨까요?
**Answer:** 어 로컬 모델은 whisper를 염두에 두고 있고 다국어 지원을 고려해서 large-v3 이상급으로 생각중이야

**Q3:** API 키 관리: Deepgram API 키는 기존의 `STTConfig` 구조에 맞추어 `lecture config set stt-api-key [키]`와 같이 CLI 명렁어로 받아서 로컬에 저장하도록 구현하는 것이 맞나요? 아니면 환경 변수(`.env`)에서 자동으로 읽어들이게 할까요?
**Answer:** 이미 구조가 있으니까 cli 명령어로 받는것으로 하자

**Q4:** 결과물 데이터 추출: 트랜스크립션 수행 시 단순 텍스트 외에 타임스탬프(Timestamps) 문자열이나 화자 분리(Speaker Diarization) 정보도 가져와서 `.md` 결과물에 포함해야 할까요, 아니면 오직 순수 텍스트(Transcript text)만 추출할까요?
**Answer:** 화자 분리 정보도 추가해줘

**Q5:** 언어 설정: STT 모델이 기본적으로 다국어를 지원하지만, 한국어(Korean)로 고정하여 호출할까요? 아니면 자동 언어 감지(Auto-detect language) 기능을 기본으로 활성화할까요?
**Answer:** 언어 감지를 기본으로 하되, 사용자가 명령어를 통해서 STT언어를 설정할 수 있도록 해줘. 예를 들어 stt language english를 입력하면 stt 언어가 영어로 바뀌는 식으로

**Q6:** 범위 제외 항목 (Out of Scope): 로컬 모델을 구동하기 위한 초기 모델 파일 자동 다운로드 로직은 직접 구현하지만, GPU(CUDA) 세팅이나 외부 드라이버 설치 지원 등 사용자의 OS 환경 디버깅까지 책임지는 것은 이번 스코프에서 제외하는 것이 맞나요?
**Answer:** 맞아 그런것들은 이번 스코프에서 제외야

### Existing Code to Reference
Based on user's response about similar features

**Similar Features Identified:**
- Feature: STT Config and Runtime Module - Path: `src/lecture_auto/stt_config.py`, `src/lecture_auto/stt_runtime.py`
- Components to potentially reuse: `STTConfig`, `APISTTRuntimeAdapter`, `LocalSTTRuntimeAdapter` interfaces and error handling implementations.
- Backend logic to reference: Error mapping semantics and validation flows present in configuring the CLI options.

### Follow-up Questions
None

## Visual Assets

### Files Provided:
No visual files found.

### Visual Insights:
No visual assets provided.

## Requirements Summary

### Functional Requirements
- **Deepgram API:** 공식 SDK(`deepgram-sdk`)를 사용하여 STT API 구현.
- **로컬 STT 모델:** 오픈소스 Whisper 채택 (large-v3 이상급 처리), 다국어 지원 포함.
- **CLI 설정 확장:** 기존 STTConfig를 확장하여 API 키 등록, 사용 언어 설정(예: `lecture config set stt-language english`), 및 화자 분리 설정(기본 지원 여부 로직 처리).
- **데이터 추출 결과물:** 단순 텍스트 파싱을 넘어서 화자 분리(Speaker Diarization) 정보를 반영한 트랜스크립트 마크다운 포맷 생성.

### Reusability Opportunities
- `src/lecture_auto/stt_config.py`: STTConfig 모델을 수정하여 STT 사용 언어 설정(`language` 속성 등) 및 다이얼로그 추가 옵션 지원 가능.
- `src/lecture_auto/stt_runtime.py`: Mock 어댑터들을 실제 동작하는 Deepgram SDK 및 Faster-Whisper 구현체로 대체하여 추상화 패턴 유지 및 확장.

### Scope Boundaries
**In Scope:**
- Deepgram SDK 연동 (화자 분리 처리 포함)
- Whisper (faster-whisper 엔진 권장) 파이프라인 구성 
- 언어 감지 기본화 및 CLI 명령어(`stt language english` 등)로 명시적 언어 설정 변경 지원
- 결과물 생성 시 화자 분리 포맷을 반영한 결과 출력 파싱 로직

**Out of Scope:**
- GPU/CUDA 세팅에 의존하는 런타임 환경 자동 구성
- 외부 드라이버 연동 오류나 컨테이너, OS 수준에서의 디버깅 대응
- (기타 Whisper 모델 캐싱 외의 OS 권한 이슈 관련)

### Technical Considerations
- `deepgram-sdk`를 활용한 안정적인 네트워크 오류 재시도 및 콜백 응답 제어
- 로컬 모델 속도와 메모리 최적화를 위해 Whisper 원본보다 빠르고 최적화된 `faster-whisper` 패키지 채택 검토
- 기존의 표준 `CommandResult` 출력 규격 및 `stt_runtime.py` 에러 컨벤션 준수
- 화자 분리 정보가 스크립트 리뷰 워크플로우를 비롯해 추후 Summary 작성(`roadmap` 6번 항목) 시에도 이질감이 없도록 확장성 뛰어난 마크다운 포맷 고려
