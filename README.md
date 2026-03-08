# Lecture Auto CLI

A powerful command-line interface for automating the capture, transcription, and summarization of lectures and audio sessions.

## Installation

To use `lecture-auto` from any folder in your terminal, install the package locally:
```bash
# From the root folder containing pyproject.toml
pip install -e .
```

## Quick Start

Once installed, you can invoke the CLI from anywhere using:
```bash
lecture-auto [OPTIONS] COMMAND [ARGS]...
```
*(Alternatively, you can run `python -m lecture_auto.cli` without installing.)*

To view help for any command or group, append `--help`.

---

## Global Options

These options can be added before subcommands.

| Option | Shortcut | Description | Environment Variable |
|--------|----------|-------------|----------------------|
| `--workspace` | `-w` | Custom workspace directory (default: `~/.lecture_auto`) | `LECTURE_AUTO_WORKSPACE` |

---

## Command Reference

### 1. Configuration (`config`)
Manage global default settings to avoid passing flags on every command.

- **`config set`**: Set default configuration values.
  ```bash
  lecture-auto config set [OPTIONS]
  ```
  - `-w, --workspace`: Default directory to store session metadata, audio, and transcripts.
  - `-stt, --stt-language`: Default language for STT transcription (e.g., `korean`).
  - `-llm, --llm-language`: Default language for generated summaries and notes (e.g., `korean`).
  - `--stt-api-provider`: Pre-configure your preferred STT provider (e.g., `deepgram`).
  - `--stt-api-key`: Pre-configure your API key for STT processing.
  - `--gemini-api-key`: Pre-configure your LLM API key.

  *Example:*
  ```bash
  lecture-auto config set -w ./my_data -stt korean --stt-api-provider deepgram --stt-api-key "your-key"
  ```

- **`config show`**: Display your current global configurations formatted as JSON.
  ```bash
  lecture-auto config show
  ```

---

### 2. Session Management (`session`)
Sessions group your lecture's audio, metadata, and generated notes.

- **`session create`**: Create a new tracking session before starting a recording.
  ```bash
  lecture-auto session create --session-id <id> --date <YYYY-MM-DD> [OPTIONS]
  ```
  - `--session-id` (Required): Unique identifier for the session.
  - `--date` (Required): Session date formatted as `YYYY-MM-DD`.
  - `--title`: Session title.
  - `--course`: Course name.
  - `--json`: Render output as JSON.

- **`session history`**: List recently created sessions.
  ```bash
  lecture-auto session history [--json]
  ```

- **`session detail`**: View detailed metadata, status, and associated file paths for a single session.
  ```bash
  lecture-auto session detail <session_id> [--json]
  ```

---

### 3. Audio Capture (`capture`)
Manage the live recording of your system's audio input.

- **`capture start`**: Begin capturing audio for a session.
  ```bash
  lecture-auto capture start <session_id> [OPTIONS]
  ```
  - `<session_id>` (Required): The target session ID.
  - `--audio-file-path`: Explicitly define where the recorded file should be saved.
  - `--json`: Render output as JSON.

- **`capture stop`**: End the active audio recording.
  ```bash
  lecture-auto capture stop <session_id> [OPTIONS]
  ```
  - `<session_id>` (Required): The target session ID.
  - `--failed`: Flag to specify if the recording process was interrupted and mark the capture as failed.
  - `--json`: Render output as JSON.

---

### 4. Transcription (`transcription`)
Transcribe recorded audio into text via Speech-to-Text (STT) models. Local and API-based modes (such as Deepgram) are supported based on your environment configurations (`STT_MODE`, `STT_API_PROVIDER`, `STT_API_KEY`).

- **`transcription run`**: Run STT transcription on the attached audio for a session.
  ```bash
  lecture-auto transcription run <session_id> [--json]
  ```

---

### 5. Summarization (`summarize`)
Generate polished lecture notes from your transcribed audio using LLMs (e.g., Gemini). Configurations like your Gemini API Key should be set via `GEMINI_API_KEY` in your environment.

- **`summarize`**: Summarize the transcript into study notes using a predefined template.
  ```bash
  lecture-auto summarize [OPTIONS]
  ```
  - `--id`: Target session ID.
  - `--template`: Name of the custom template file to use for the notes output structure.
  - `--preview`: Preview the generated AI notes in the terminal without saving to disk.
  - `--json`: Render output as JSON.

## Environment Variables

Beyond the CLI configuration options, the tool operates using the following environment variables:

- `LECTURE_AUTO_WORKSPACE`: Explicit root folder for the application. Overrides global config.
- `GEMINI_API_KEY`: API Key for LLM summarization features.
- `LLM_MODEL`: Override the default `gemini-3-flash-preview` model.
- `STT_MODE`: Define STT mode (`api`, `local`). Default is `api`.
- `STT_API_PROVIDER`: E.g., `openai-compatible` or `deepgram`.
- `STT_API_KEY`: API Key for standard web STT providers.
- `STT_LOCAL_MODEL`: Local STT Whisper model identifier (default: `base`).
