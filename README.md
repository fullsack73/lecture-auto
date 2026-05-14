# Lecture Auto CLI

`lecture-auto` is a local-first CLI/TUI for recording lectures, transcribing
session audio, importing lecture materials, and generating study notes.

The app stores metadata and artifacts in a workspace directory. By default this
is `~/.lecture_auto`, but it can be changed globally or per command.

## Current Capabilities

- Interactive TUI when `lecture-auto` is run without a subcommand.
- Session lifecycle management: create, update, delete, inspect, and history.
- FFmpeg-based macOS audio capture from microphone or a loopback/system-audio
  device.
- Audio refinement: volume normalization and DeepFilterNet noise reduction.
- STT transcription through API providers or local Whisper.
- LLM note generation through Gemini or Ollama.
- PDF/PPT/PPTX lecture material import, stored as session-scoped PDF material.
- Library listing, searching, and opening of notes/transcript/recording folders.

## Requirements

- Python 3.11+
- FFmpeg available on `PATH` for recording, audio probing, and audio processing.
- macOS for the built-in FFmpeg capture adapter, which uses AVFoundation.
- Optional system-audio loopback device such as BlackHole, Loopback, or
  Soundflower when using `system_audio`.
- Provider credentials when using cloud STT or Gemini.
- Ollama running locally when using the Ollama LLM provider.

## Installation

Clone the repository, enter the project directory, and install it in editable
mode:

```bash
git clone https://github.com/fullsack73/auto_lecture_notes.git
cd auto_lecture_notes
pip install -e .
```

The package exposes both command names:

```bash
lecture-auto --help
lecture_auto --help
```

You can also run the module form after installing, or from a source checkout
with `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m lecture_auto.cli --help
```

## Quick Start

Open the interactive UI:

```bash
lecture-auto
```

Or use the CLI directly:

```bash
lecture-auto config set \
  --workspace ./lecture_data \
  --stt-language korean \
  --llm-language korean \
  --stt-mode api \
  --stt-api-provider deepgram \
  --stt-api-key "your-stt-key" \
  --gemini-api-key "your-gemini-key"

lecture-auto session create \
  --session-id week-01 \
  --date 2026-05-08 \
  --title "Intro Lecture" \
  --course CS101

lecture-auto capture start week-01
lecture-auto capture stop week-01
lecture-auto transcription run week-01
lecture-auto summarize --id week-01 --template structured-notes
```

## Global Option

Global options are passed before the subcommand.

| Option | Shortcut | Description | Environment variable |
| --- | --- | --- | --- |
| `--workspace` | `-w` | Workspace directory for metadata and generated files | `LECTURE_AUTO_WORKSPACE` |

Example:

```bash
lecture-auto --workspace ./lecture_data session history
```

## Workspace Layout

Generated files are stored under the active workspace:

```text
metadata/sessions.json
recordings/[course/]session-id.wav
recordings/[course/]session-id-refined.wav
transcripts/[course/]session-id-raw.md
transcripts/[course/]session-id-edited.md
materials/[course/]session-id.pdf
notes/[course/]session-id.md
templates/custom-template.md
```

When `course` is set, it is normalized into a filesystem-safe folder name.

## Commands

### `config`

Persist default settings in `~/.lecture_auto/config.json`.

```bash
lecture-auto config set [OPTIONS]
lecture-auto config show
```

Supported `config set` options:

| Option | Description |
| --- | --- |
| `-w, --workspace` | Default workspace directory |
| `-stt, --stt-language` | Default transcription language, for example `korean` |
| `-llm, --llm-language` | Default summary/note language |
| `--stt-mode` | `api` or `local` |
| `--stt-api-provider` | `openai-compatible` or `deepgram` |
| `--stt-api-key` | STT API key |
| `--stt-local-model` | Local Whisper model, for example `base`, `medium`, or `large-v3` |
| `--gemini-api-key` | Gemini API key |
| `--llm-model` | Gemini model, currently `gemini-3.1-flash-lite`, `gemini-3-flash-preview`, or `gemini-3.1-pro-preview` |
| `--llm-thinking-level` | `minimal`, `low`, `medium`, or `high` |
| `--audio-format` | Recording format: `wav` or `mp3` |
| `--capture-source` | `microphone` or `system_audio` |
| `--use-dynaudnorm / --no-use-dynaudnorm` | Enable or disable dynamic audio normalization |
| `--dynaudnorm-f` | FFmpeg `dynaudnorm` frame length, 10 to 8000 |
| `--dynaudnorm-g` | FFmpeg `dynaudnorm` Gaussian window, odd integer 3 to 301 |
| `--gain-db` | Additional gain in dB, -60.0 to 60.0 |

### `session`

Create and maintain lecture sessions.

```bash
lecture-auto session create --session-id <id> --date <YYYY-MM-DD> [OPTIONS]
lecture-auto session history [--json]
lecture-auto session detail <session_id> [--json]
lecture-auto session update <session_id> [OPTIONS]
lecture-auto session delete <session_id> [--json]
lecture-auto session import-material <session_id> <material_path> [--json]
lecture-auto session refine-audio <session_id> [--json]
lecture-auto session refine-noise <session_id> [--json]
```

Useful options:

| Command | Options |
| --- | --- |
| `create` | `--title`, `--course`, `--json` |
| `update` | `--new-id`, `--title`, `--course`, `--date`, `--json` |
| `import-material` | Accepts PDF, PPT, or PPTX. PPT/PPTX are converted to PDF. Re-importing material merges with the existing session PDF when possible. |
| `refine-audio` | Uses the configured `dynaudnorm` settings and writes `recordings/[course/]session-id-refined.wav`. |
| `refine-noise` | Uses DeepFilterNet and writes a refined audio file for the session. |

### `capture`

Start and stop FFmpeg-based recording for a session.

```bash
lecture-auto capture start <session_id> [--audio-file-path <path>] [--json]
lecture-auto capture stop <session_id> [--failed] [--json]
```

If an existing recording path already exists, a new part is recorded and merged
back into the original audio on a successful stop.

### `transcription`

Transcribe the session-linked audio.

```bash
lecture-auto transcription run <session_id> [--json]
```

The command uses `refined_audio_file_path` when present, otherwise the original
session audio. API mode retries transient provider/network failures. Deepgram
output is written as speaker-attributed Markdown when diarized segments are
available; local Whisper output is written as plain text.

### `summarize`

Generate notes from the best available transcript.

```bash
lecture-auto summarize --id <session_id> [--template <name>] [--preview] [--json]
```

The summary source prefers an edited transcript when it exists and is newer than
the raw transcript. Imported material is passed to the LLM when available.

Built-in templates:

- `bullet-summary`
- `structured-notes`
- `qa-review`

Custom templates can be placed in:

```text
<workspace>/templates/<name>.md
```

### `library`

Browse stored sessions and open artifact folders.

```bash
lecture-auto library list [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--status STATUS] [--sort recent] [--json]
lecture-auto library search <query> [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--status STATUS] [--sort recent] [--json]
lecture-auto library open <session_id> [--transcript] [--recordings] [--json]
```

`library search` matches session IDs and note contents.

## Environment Variables

Environment variables override persisted config where applicable.

| Variable | Description |
| --- | --- |
| `LECTURE_AUTO_WORKSPACE` | Active workspace directory |
| `LECTURE_AUTO_CAPTURE_SOURCE` | `microphone` or `system_audio` |
| `LECTURE_AUTO_AUDIO_FORMAT` | `wav` or `mp3` |
| `STT_MODE` | `api` or `local` |
| `STT_API_PROVIDER` | `openai-compatible` or `deepgram` |
| `STT_API_KEY` | STT provider API key |
| `STT_LOCAL_MODEL` | Local Whisper model name |
| `USE_DYNAUDNORM` | Enable dynamic normalization during STT preprocessing |
| `LLM_PROVIDER` | `gemini`, `ollama`, or `local` alias for Ollama |
| `GEMINI_API_KEY` | Gemini API key |
| `LLM_MODEL` | LLM model override |
| `LLM_THINKING_LEVEL` | `minimal`, `low`, `medium`, or `high` |

## LLM Providers

Gemini is the default provider. Configure it with:

```bash
lecture-auto config set \
  --gemini-api-key "your-key" \
  --llm-model gemini-3.1-flash-lite \
  --llm-thinking-level medium
```

For Ollama, set the provider through the TUI config screen or an environment
variable:

```bash
LLM_PROVIDER=ollama LLM_MODEL=gemma4:31b-cloud lecture-auto summarize --id week-01
```

## JSON Output

Most operational commands support `--json`. JSON responses use this shape:

```json
{"command":"session detail","payload":{},"message":"Loaded details for session 'week-01'."}
```

## Notes

- Running `lecture-auto` with no subcommand starts the interactive TUI.
- Transcript refinement is available from the TUI transcription menu, but it is
  not currently exposed as a top-level CLI command.
- Audio import exists in the service layer, but it is not currently exposed as a
  top-level CLI command.
- `library open` opens folders through the operating system file manager.
