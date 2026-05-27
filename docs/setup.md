# Setup

[Korean documentation](setup.ko.md)

Installation and provider setup for Lecture Auto.

## Requirements

- Python 3.11+
- FFmpeg
- macOS with AVFoundation support for built-in recording
- A loopback device for system-audio recording, such as:
  - BlackHole
  - Loopback
  - Soundflower
- An STT API key when using cloud STT
- A Gemini API key when using Gemini
- An Ollama server and model when using Ollama

## Install

```bash
git clone https://github.com/fullsack73/auto_lecture_notes.git
cd auto_lecture_notes
pip install -e .
```

Check the installed commands:

```bash
lecture-auto --help
lecture_auto --help
```

Run directly from a source checkout:

```bash
PYTHONPATH=src python -m lecture_auto.cli --help
```

## Workspace

The default workspace is `~/.lecture_auto`.

Set a default workspace:

```bash
lecture-auto config set --workspace ./lecture_data
```

Override it for one command:

```bash
lecture-auto --workspace ./lecture_data session history
```

Use an environment variable:

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

### OpenAI-Compatible STT

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

Gemini is the default LLM provider.

```bash
lecture-auto config set \
  --gemini-api-key "your-gemini-key" \
  --llm-model gemini-3.1-flash-lite \
  --llm-thinking-level medium \
  --llm-language korean
```

Supported model presets:

```text
gemini-3.1-flash-lite
gemini-3-flash-preview
gemini-3.1-pro-preview
```

### Ollama

Ollama does not require an API key. The Ollama server must be running and the target model must be available.

```bash
LLM_PROVIDER=ollama LLM_MODEL=gemma4:31b-cloud lecture-auto summarize --id week-01
```

You can also set the LLM provider to `local`/`ollama` from the TUI Config menu.

Ollama note generation does not ask the model to write Markdown directly.

```text
transcript
-> section JSON generation
-> validation
-> optional repair
-> structured Markdown render
```

This reduces template drift when smaller models ignore Markdown instructions.

## Capture Setup

Microphone recording:

```bash
lecture-auto config set --capture-source microphone
```

System audio recording:

```bash
lecture-auto config set --capture-source system_audio
```

System audio on macOS may require a loopback device.

## Audio Refinement

Dynamic normalization during STT preprocessing:

```bash
lecture-auto config set --use-dynaudnorm
```

Normalize a session recording:

```bash
lecture-auto session refine-audio week-01
```

Run DeepFilterNet noise reduction:

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

Gemini API key is missing, or Ollama provider/model config is wrong.

Gemini:

```bash
lecture-auto config set --gemini-api-key "your-gemini-key"
```

Ollama:

```bash
LLM_PROVIDER=ollama LLM_MODEL=<model> lecture-auto summarize --id <session_id>
```

### `Transcription config error`

Check STT mode, provider, and API key.

```bash
lecture-auto config show
```

### Recording Fails

Check FFmpeg and macOS audio permissions.

```bash
ffmpeg -version
```

For system audio recording, also check your loopback device setup.

### PPT/PPTX Material Import Fails

PPT/PPTX conversion may require LibreOffice. For the simplest path, convert slides to PDF first and import the PDF.
