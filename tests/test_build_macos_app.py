import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("zsh") is None, reason="macOS builder requires zsh")
@pytest.mark.parametrize("install", [False, True])
def test_macos_build_uses_stable_bundle_and_directory(tmp_path: Path, install: bool) -> None:
    root = tmp_path / "project with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    builder = scripts / "build_macos_app.sh"
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts/build_macos_app.sh", builder)

    def executable(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    tools = root / "tools"
    executable(tools / "uname", "#!/bin/sh\necho arm64\n")
    executable(tools / "codesign", "#!/bin/sh\nexit 0\n")
    executable(tools / "uv", "#!/bin/sh\nexit 0\n")
    executable(scripts / "prepare_ffmpeg_macos.sh", "#!/bin/sh\nexit 0\n")
    for name in ("ffmpeg", "ffprobe"):
        executable(root / "build/dependencies/ffmpeg-lgpl/bin" / name, "#!/bin/sh\nexit 0\n")
    python = tools / "python"
    executable(
        python,
        f"#!{sys.executable}\n" + '''
import sys
from pathlib import Path

args = sys.argv[1:]
if args[0] == "-c":
    if "platform.machine" in args[1]:
        print("arm64")
elif args[:2] == ["-m", "nuitka"]:
    assert any(arg.endswith("stt_refinement.py=addon_source/lecture_auto/stt_refinement.py") for arg in args)
    output = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("--output-dir=")))
    runtime = output / "LectureAuto.app/Contents/MacOS"
    runtime.mkdir(parents=True)
    for name in ("LectureAuto", "bin/ffmpeg", "bin/ffprobe"):
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("new build")
        path.chmod(0o755)
elif args[0].endswith("project_version.py"):
    print("0.1.11+hotfix")
elif args[0].endswith("verify_lightweight_app.py"):
    app = Path(args[args.index("--app") + 1])
    assert app.name == "Lecture Auto.app"
    assert (app / "Contents/MacOS/LectureAuto").is_file()
elif args[0].endswith("install_macos_app.py"):
    if args[1] == "install":
        assert Path(args[2]).name == Path(args[3]).name == "Lecture Auto.app"
        assert Path(args[2]).is_dir()
''',
    )
    app = root / "build/macos/Lecture Auto.app"
    app.mkdir(parents=True)
    (app / "old-build").touch()
    override = root / "build/macos-v0.1.11-hotfix"
    result = subprocess.run(
        ["zsh", str(builder), *(["--install"] if install else [])],
        env={**os.environ, "PATH": f"{tools}:{os.environ['PATH']}", "PYTHON": str(python),
             "UV": str(tools / "uv"), "BUILD_DIR": str(override)},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (app / "Contents/MacOS/LectureAuto").read_text() == "new build"
    assert not (app / "old-build").exists()
    assert not (app.parent / "LectureAuto.app").exists()
    assert not override.exists()
    assert (app.parent / "build-metadata.json").is_file()
