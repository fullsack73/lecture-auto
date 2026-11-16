#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
BUILD_DIR="$ROOT/build/macos"
SOURCE="$ROOT/src/lecture_auto/gui/LectureAuto.py"
WORKER="$ROOT/src/lecture_auto/local_ai_worker.py"
GEMINI_WORKER="$ROOT/src/lecture_auto/gemini_addon_worker.py"
PACKAGE_INIT="$ROOT/src/lecture_auto/__init__.py"
LLM_ADAPTER="$ROOT/src/lecture_auto/llm_adapter.py"
LLM_CONFIG="$ROOT/src/lecture_auto/llm_config.py"
STT_REFINEMENT="$ROOT/src/lecture_auto/stt_refinement.py"
NOTE_TEMPLATE="$ROOT/src/lecture_auto/templates/structured-notes.md"
UV="${UV:-$ROOT/.venv/bin/uv}"
FFMPEG_ROOT="$ROOT/build/dependencies/ffmpeg-lgpl"
FFMPEG="$FFMPEG_ROOT/bin/ffmpeg"
FFPROBE="$FFMPEG_ROOT/bin/ffprobe"
ICON_PNG="$ROOT/src/lecture_auto/gui/assets/app-icon.png"
ICON_ICNS="$ROOT/src/lecture_auto/gui/assets/LectureAuto.icns"
NUITKA_APP="$BUILD_DIR/LectureAuto.app"
APP="$BUILD_DIR/Lecture Auto.app"
INSTALL_APP="/Applications/Lecture Auto.app"
INSTALLER="$ROOT/scripts/install_macos_app.py"

INSTALL_REQUESTED=0
APP_VERSION_OVERRIDE=""
while (( $# )); do
  case "$1" in
    --install) INSTALL_REQUESTED=1; shift ;;
    --version)
      if (( $# < 2 )) || [[ -z "$2" || -n "$APP_VERSION_OVERRIDE" ]]; then
        print -u2 -- "--version requires one version, e.g. 0.1.16-dev"
        exit 2
      fi
      APP_VERSION_OVERRIDE="$2"
      shift 2
      ;;
    --help|-h)
      print "Usage: $0 [--install] [--version VERSION]"
      print "Example: $0 --install --version 0.1.16-dev"
      exit 0
      ;;
    *) print -u2 "Unknown argument: $1"; exit 2 ;;
  esac
done
if [[ -n "$APP_VERSION_OVERRIDE" && ! "$APP_VERSION_OVERRIDE" =~ '^[0-9]+[.][0-9]+[.][0-9]+([-+][A-Za-z0-9][A-Za-z0-9.-]*)?$' ]]; then
  print -u2 "Invalid version: $APP_VERSION_OVERRIDE (expected X.Y.Z or X.Y.Z-label)"
  exit 2
fi

if [[ "$(uname -m)" != "arm64" ]]; then
  print -u2 "This build script requires a native arm64 shell."
  exit 2
fi

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  print -u2 "Python environment not found: $PYTHON"
  exit 2
fi

if [[ ! -x "$UV" ]]; then
  UV="$(command -v uv || true)"
fi

if [[ -z "$UV" || ! -x "$UV" ]]; then
  print -u2 "uv build binary not found: $UV"
  print -u2 "Install build dependencies with: $PYTHON -m pip install -e '$ROOT[build]'"
  exit 2
fi

if [[ "$($PYTHON -c 'import platform; print(platform.machine())')" != "arm64" ]]; then
  print -u2 "Python is not arm64: $PYTHON"
  exit 2
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)'; then
  print -u2 "macOS app builds require Python 3.11 exactly: $PYTHON ($($PYTHON --version 2>&1))"
  print -u2 "Create a Python 3.11 environment or set PYTHON to its interpreter."
  exit 2
fi

APP_VERSION="${APP_VERSION_OVERRIDE:-$("$PYTHON" "$ROOT/scripts/project_version.py")}"
NUMERIC_VERSION="${APP_VERSION%%[-+]*}"
print "Building Lecture Auto $APP_VERSION"
"$UV" pip install --python "$PYTHON" --no-deps --editable "$ROOT"

if (( INSTALL_REQUESTED )); then
  "$PYTHON" "$INSTALLER" check "$INSTALL_APP"
fi
"$PYTHON" "$INSTALLER" check "$APP"
"$PYTHON" "$INSTALLER" check "$NUITKA_APP"

"$ROOT/scripts/prepare_ffmpeg_macos.sh"

if [[ ! -x "$FFMPEG" || ! -x "$FFPROBE" ]]; then
  print -u2 "Prepared FFmpeg tools not found under: $FFMPEG_ROOT/bin"
  exit 2
fi

mkdir -p "$BUILD_DIR"
STARTED_AT="$(date +%s)"
PREVIOUS_KB="$(du -sk "$BUILD_DIR" 2>/dev/null | awk '{print $1}' || print 0)"
rm -rf "$BUILD_DIR/app.build" "$BUILD_DIR/app.dist" "$BUILD_DIR/app.app" \
  "$BUILD_DIR/LectureAuto.build" "$BUILD_DIR/LectureAuto.dist" "$NUITKA_APP" "$APP"

# Nuitka's bundled ccache 4.2.1 is x86_64-only on this machine and causes
# xcrun to launch under Rosetta against arm64 Command Line Tools.
"$PYTHON" -m nuitka "$SOURCE" \
  --enable-plugin=pyside6 \
  --standalone \
  --include-distribution-metadata=lecture-auto \
  --macos-create-app-bundle \
  --macos-target-arch=arm64 \
  --macos-app-name="Lecture Auto" \
  --macos-signed-app-name="com.anarchytoast.lectureauto" \
  --macos-app-version="$NUMERIC_VERSION" \
  --macos-app-icon="$ICON_ICNS" \
  --macos-app-protected-resource="NSMicrophoneUsageDescription:Lecture Auto records lecture audio selected by the user." \
  --output-dir="$BUILD_DIR" \
  --output-filename=LectureAuto \
  --output-folder-name=LectureAuto \
  --disable-cache=ccache \
  --module-parameter=torch-disable-jit=yes \
  --no-prefer-source-code \
  --nofollow-import-to=torch \
  --nofollow-import-to=torchaudio \
  --nofollow-import-to=faster_whisper \
  --nofollow-import-to=ctranslate2 \
  --nofollow-import-to=df \
  --nofollow-import-to=onnxruntime \
  --nofollow-import-to=google.genai \
  --nofollow-import-to=google.api_core \
  --include-data-file="$WORKER=local_ai_worker.py" \
  --include-data-file="$GEMINI_WORKER=gemini_addon_worker.py" \
  --include-data-file="$PACKAGE_INIT=addon_source/lecture_auto/__init__.py" \
  --include-data-file="$LLM_ADAPTER=addon_source/lecture_auto/llm_adapter.py" \
  --include-data-file="$LLM_CONFIG=addon_source/lecture_auto/llm_config.py" \
  --include-data-file="$STT_REFINEMENT=addon_source/lecture_auto/stt_refinement.py" \
  --include-data-file="$NOTE_TEMPLATE=lecture_auto/templates/structured-notes.md" \
  --include-data-file="$UV=bin/uv" \
  --include-data-file="$FFMPEG=bin/ffmpeg" \
  --include-data-file="$FFPROBE=bin/ffprobe" \
  --include-data-dir="$FFMPEG_ROOT/licenses=licenses/ffmpeg" \
  --include-data-file="$ICON_PNG=assets/app-icon.png" \
  --report="$BUILD_DIR/nuitka-report.xml" \
  --assume-yes-for-downloads

# Keep the distributed bundle name identical to the Applications install target.
mv "$NUITKA_APP" "$APP"

if [[ ! -x "$APP/Contents/MacOS/LectureAuto" ]]; then
  print -u2 "Build completed without expected app executable: $APP"
  exit 3
fi

"$PYTHON" - "$APP/Contents/Info.plist" "$APP_VERSION" <<'PYVERSION'
import plistlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
info = plistlib.loads(path.read_bytes())
info["LectureAutoDisplayVersion"] = sys.argv[2]
path.write_bytes(plistlib.dumps(info))
PYVERSION

chmod +x "$APP/Contents/MacOS/bin/ffmpeg" "$APP/Contents/MacOS/bin/ffprobe"

codesign --force --deep --sign - --identifier "com.anarchytoast.lectureauto" "$APP"

"$PYTHON" "$ROOT/scripts/verify_lightweight_app.py" \
  --app "$APP" \
  --report "$BUILD_DIR/nuitka-report.xml" \
  --platform macos \
  --architecture arm64 \
  --smoke-test

FINISHED_AT="$(date +%s)"
APP_KB="$(du -sk "$APP" | awk '{print $1}')"
printf '{"version":"%s","started_at":%s,"finished_at":%s,"duration_seconds":%s,"app_size_kb":%s,"previous_partial_size_kb":%s}\n' \
  "$APP_VERSION" "$STARTED_AT" "$FINISHED_AT" "$((FINISHED_AT-STARTED_AT))" "$APP_KB" "$PREVIOUS_KB" \
  > "$BUILD_DIR/build-metadata.json"

if (( INSTALL_REQUESTED )); then
  "$PYTHON" "$INSTALLER" install "$APP" "$INSTALL_APP"
  print "Installed: $INSTALL_APP ($APP_VERSION)"
else
  print "Built: $APP ($APP_VERSION)"
fi
