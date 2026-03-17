# Implementation: CLI Commands and Output Formatting

## Task Group 2: CLI Commands and Output Formatting

### Implemented
- Added `library_app` Typer sub-app in `src/lecture_auto/cli.py`.
- Registered `library_app` with `app.add_typer(library_app, name="library")`.
- Implemented CLI commands:
  - `lecture-auto library list`
  - `lecture-auto library search <query>`
  - `lecture-auto library open <session-id>`
- Added filters/options:
  - `--from`, `--to`, `--status`, `--sort recent`, `--json` for `list` and `search`
  - `--transcript`, `--recordings`, `--json` for `open`
- Wired all commands through `_run_or_exit(...)` and `LibraryService`.
- Added output formatting branches in `src/lecture_auto/cli_output.py`:
  - `library list`
  - `library search`
  - `library open`

### Tests (2.1 / 2.7)
- Added focused CLI tests in `tests/test_library_cli.py`.
- Executed only these tests:
  - `python -m pytest tests/test_library_cli.py -q`
- Result: `4 passed`.

### Notes
- Implementation follows existing CLI and formatting patterns used by `session` and other command groups.
- Error handling remains consistent with `SessionCommandError` + formatter flow.
