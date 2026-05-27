# Setup

Lecture Auto를 실행하기 위한 설치와 provider 설정.

## Requirements

- Python 3.11+
- FFmpeg
- macOS 녹음 기능을 쓸 경우 AVFoundation 사용 가능 환경
- 시스템 오디오 녹음 시 loopback device
  - BlackHole
  - Loopback
  - Soundflower
- cloud STT 사용 시 STT API key
- Gemini 사용 시 Gemini API key
- Ollama 사용 시 Ollama server와 model

## Install

```bash
git clone https://github.com/fullsack73/auto_lecture_notes.git
cd auto_lecture_notes
pip install -e .
```

설치 확인:

```bash
lecture-auto --help
lecture_auto --help
```

source checkout에서 직접 실행:

```bash
PYTHONPATH=src python -m lecture_auto.cli --help
```

## Workspace

기본 workspace는 `~/.lecture_auto`다.

변경:

```bash
lecture-auto config set --workspace ./lecture_data
```

명령 1회만 override:

```bash
lecture-auto --workspace ./lecture_data session history
```

환경변수:

```bash
export LECTURE_AUTO_WORKSPACE="$PWD/lecture_data"
```

## STT Setup

### Deepgram

```bash
lecture-auto config set \
  --stt-mode api \
  --stt-api-provider deepgram \
  --stt-api-key "your-deepgram-key" \
  --stt-language korean
```

### OpenAI-compatible STT

```bash
lecture-auto config set \
  --stt-mode api \
  --stt-api-provider openai-compatible \
  --stt-api-key "your-stt-key" \
  --stt-language korean
```

### Local Whisper

```bash
lecture-auto config set \
  --stt-mode local \
  --stt-local-model large-v3 \
  --stt-language korean
```

## LLM Setup

### Gemini

Gemini가 기본 LLM provider다.

```bash
lecture-auto config set \
  --gemini-api-key "your-gemini-key" \
  --llm-model gemini-3.1-flash-lite \
  --llm-thinking-level medium \
  --llm-language korean
```

지원 model preset:

```text
gemini-3.1-flash-lite
gemini-3-flash-preview
gemini-3.1-pro-preview
```

### Ollama

Ollama는 API key가 필요 없다. Ollama server가 떠 있고 model이 준비되어 있어야 한다.

```bash
LLM_PROVIDER=ollama LLM_MODEL=gemma4:31b-cloud lecture-auto summarize --id week-01
```

또는 TUI의 Config 메뉴에서 LLM provider를 `local`/`ollama`로 설정한다.

Ollama 노트 생성은 Markdown을 모델에게 직접 맡기지 않는다.

```text
transcript
-> section JSON generation
-> validation
-> optional repair
-> structured Markdown render
```

이 방식은 작은 모델이 Markdown 템플릿을 무시하는 문제를 줄인다.

## Capture Setup

마이크 녹음:

```bash
lecture-auto config set --capture-source microphone
```

시스템 오디오 녹음:

```bash
lecture-auto config set --capture-source system_audio
```

시스템 오디오는 macOS에 loopback device가 필요할 수 있다.

## Audio Refinement

STT 전처리에서 dynamic normalization:

```bash
lecture-auto config set --use-dynaudnorm
```

세션 녹음 파일 자체를 정규화:

```bash
lecture-auto session refine-audio week-01
```

DeepFilterNet noise reduction:

```bash
lecture-auto session refine-noise week-01
```

## Common Environment Variables

```text
LECTURE_AUTO_WORKSPACE
LECTURE_AUTO_CAPTURE_SOURCE
LECTURE_AUTO_AUDIO_FORMAT
STT_MODE
STT_API_PROVIDER
STT_API_KEY
STT_LOCAL_MODEL
USE_DYNAUDNORM
LLM_PROVIDER
LLM_MODEL
LLM_THINKING_LEVEL
GEMINI_API_KEY
```

## Troubleshooting

### `No LLM adapter configured`

Gemini API key가 없거나 Ollama provider/model 설정이 맞지 않다.

Gemini:

```bash
lecture-auto config set --gemini-api-key "your-gemini-key"
```

Ollama:

```bash
LLM_PROVIDER=ollama LLM_MODEL=<model> lecture-auto summarize --id <session_id>
```

### `Transcription config error`

STT mode/provider/API key를 확인한다.

```bash
lecture-auto config show
```

### Recording fails

FFmpeg 설치와 macOS audio permission을 확인한다.

```bash
ffmpeg -version
```

시스템 오디오 녹음이면 loopback device 설정도 확인한다.

### PPT/PPTX material import fails

PPT/PPTX 변환에는 LibreOffice가 필요할 수 있다. 안정성이 필요하면 PDF로 변환한 뒤 import하는 것이 가장 단순하다.
