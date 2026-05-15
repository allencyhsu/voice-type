# VoiceType Tray App v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Windows system tray entrypoint so VoiceType can run as a background utility and optionally start at login.

**Architecture:** Keep the existing CLI listener and voice pipeline as the core. Add small modules for startup entry management, listener runtime wrapping, and tray UI orchestration. Use dependency injection so tests do not open real tray UI or touch the real Startup folder.

**Tech Stack:** Python 3.11+, pystray, pillow, pytest, pathlib, threading, existing pynput/sounddevice/Whisper/Qwen stack.

---

## File Structure

- Modify: `pyproject.toml` - add `pystray` and `pillow` runtime dependencies.
- Create: `src/voicetype/startup.py` - Windows Startup folder command file management.
- Create: `tests/test_startup.py` - startup path, command, enable, disable, and status tests.
- Create: `src/voicetype/listener_runtime.py` - builds and runs the existing listener in a background thread.
- Create: `tests/test_listener_runtime.py` - runtime status and thread-start tests with fake callbacks.
- Create: `src/voicetype/tray.py` - tray app state, menu actions, icon creation, and pystray integration.
- Create: `tests/test_tray.py` - tray menu/action tests using fake tray backend.
- Modify: `src/voicetype/cli.py` - add `tray` command and delegate to tray runner.
- Modify: `tests/test_cli_entrypoint.py` - parser test for `tray`.
- Modify: `README.md` - document tray mode and startup behavior.
- Modify: `CODEX_HANDOFF.md` - update latest state, commands, and cautions.

---

### Task 1: Add Tray Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependencies**

In `pyproject.toml`, add these lines to `[project].dependencies`:

```toml
    "pystray>=0.19.5",
    "pillow>=10.0",
```

- [ ] **Step 2: Install editable package**

Run:

```powershell
python -m pip install -e ".[dev]"
```

Expected: pip installs or confirms `pystray` and `pillow`.

- [ ] **Step 3: Verify import**

Run:

```powershell
python -c "import pystray, PIL; print('tray deps ok')"
```

Expected:

```text
tray deps ok
```

- [ ] **Step 4: Commit dependency change**

Run:

```powershell
git add pyproject.toml
git commit -m "chore: add tray dependencies"
git push origin feature/voice-type-mvp
```

---

### Task 2: Startup Entry Management

**Files:**
- Create: `src/voicetype/startup.py`
- Create: `tests/test_startup.py`

- [ ] **Step 1: Write failing startup tests**

Create `tests/test_startup.py`:

```python
from pathlib import Path

from voicetype.startup import (
    StartupEntry,
    build_startup_command,
    disable_startup,
    enable_startup,
    is_startup_enabled,
    startup_entry_path,
)


def test_startup_entry_path_uses_startup_dir():
    assert startup_entry_path(startup_dir=Path("C:/Startup")) == Path("C:/Startup/VoiceType.cmd")


def test_build_startup_command_prefers_pythonw(tmp_path):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    pythonw = scripts / "pythonw.exe"
    pythonw.write_text("", encoding="utf-8")

    command = build_startup_command(python_executable=scripts / "python.exe")

    assert command == f'"{pythonw}" -m voicetype tray'


def test_enable_startup_writes_command_file(tmp_path):
    entry = enable_startup(
        startup_dir=tmp_path,
        python_executable=Path("C:/Project/.venv/Scripts/python.exe"),
    )

    assert entry == StartupEntry(path=tmp_path / "VoiceType.cmd", enabled=True)
    assert "voicetype tray" in entry.path.read_text(encoding="utf-8")


def test_disable_startup_removes_command_file(tmp_path):
    path = tmp_path / "VoiceType.cmd"
    path.write_text("old", encoding="utf-8")

    entry = disable_startup(startup_dir=tmp_path)

    assert entry == StartupEntry(path=path, enabled=False)
    assert not path.exists()


def test_is_startup_enabled_checks_command_file(tmp_path):
    assert is_startup_enabled(startup_dir=tmp_path) is False
    (tmp_path / "VoiceType.cmd").write_text("command", encoding="utf-8")
    assert is_startup_enabled(startup_dir=tmp_path) is True
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest tests/test_startup.py -q
```

Expected: FAIL because `voicetype.startup` does not exist.

- [ ] **Step 3: Implement startup module**

Create `src/voicetype/startup.py`:

```python
from dataclasses import dataclass
import os
from pathlib import Path
import sys


STARTUP_FILENAME = "VoiceType.cmd"


@dataclass(frozen=True)
class StartupEntry:
    path: Path
    enabled: bool


def default_startup_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        return Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_entry_path(*, startup_dir: str | Path | None = None) -> Path:
    base_dir = Path(startup_dir) if startup_dir is not None else default_startup_dir()
    return base_dir / STARTUP_FILENAME


def build_startup_command(*, python_executable: str | Path | None = None) -> str:
    executable = Path(python_executable or sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else executable
    return f'"{launcher}" -m voicetype tray'


def enable_startup(
    *,
    startup_dir: str | Path | None = None,
    python_executable: str | Path | None = None,
) -> StartupEntry:
    path = startup_entry_path(startup_dir=startup_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"@echo off\nstart \"\" {build_startup_command(python_executable=python_executable)}\n", encoding="utf-8")
    return StartupEntry(path=path, enabled=True)


def disable_startup(*, startup_dir: str | Path | None = None) -> StartupEntry:
    path = startup_entry_path(startup_dir=startup_dir)
    if path.exists():
        path.unlink()
    return StartupEntry(path=path, enabled=False)


def is_startup_enabled(*, startup_dir: str | Path | None = None) -> bool:
    return startup_entry_path(startup_dir=startup_dir).exists()
```

- [ ] **Step 4: Run startup tests**

Run:

```powershell
python -m pytest tests/test_startup.py -q
```

Expected: all startup tests pass.

- [ ] **Step 5: Commit startup module**

Run:

```powershell
git add src/voicetype/startup.py tests/test_startup.py
git commit -m "feat: manage Windows startup entry"
git push origin feature/voice-type-mvp
```

---

### Task 3: Listener Runtime Wrapper

**Files:**
- Create: `src/voicetype/listener_runtime.py`
- Create: `tests/test_listener_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Create `tests/test_listener_runtime.py`:

```python
from voicetype.listener_runtime import ListenerStatus, VoiceTypeListenerRuntime


def test_runtime_starts_listener_in_background_thread():
    calls = []

    def fake_runner():
        calls.append("run")

    runtime = VoiceTypeListenerRuntime(listener_runner=fake_runner)

    runtime.start_in_thread()
    runtime.join(timeout=2)

    assert calls == ["run"]
    assert runtime.status == ListenerStatus.STOPPED


def test_runtime_marks_error_when_runner_raises():
    def fake_runner():
        raise RuntimeError("boom")

    runtime = VoiceTypeListenerRuntime(listener_runner=fake_runner)

    runtime.start_in_thread()
    runtime.join(timeout=2)

    assert runtime.status == ListenerStatus.ERROR
    assert runtime.error == "boom"
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest tests/test_listener_runtime.py -q
```

Expected: FAIL because `voicetype.listener_runtime` does not exist.

- [ ] **Step 3: Implement runtime wrapper**

Create `src/voicetype/listener_runtime.py`:

```python
from collections.abc import Callable
from enum import StrEnum
import threading


class ListenerStatus(StrEnum):
    READY = "Ready"
    RUNNING = "Running"
    STOPPED = "Stopped"
    ERROR = "Error"


class VoiceTypeListenerRuntime:
    def __init__(self, *, listener_runner: Callable[[], None]) -> None:
        self.listener_runner = listener_runner
        self.status = ListenerStatus.READY
        self.error: str | None = None
        self._thread: threading.Thread | None = None

    def start_in_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="voicetype-listener", daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        self.status = ListenerStatus.RUNNING
        try:
            self.listener_runner()
            self.status = ListenerStatus.STOPPED
        except Exception as exc:
            self.error = str(exc)
            self.status = ListenerStatus.ERROR
```

- [ ] **Step 4: Run runtime tests**

Run:

```powershell
python -m pytest tests/test_listener_runtime.py -q
```

Expected: pass.

- [ ] **Step 5: Add factory for CLI listener runner**

Append to `src/voicetype/listener_runtime.py`:

```python
from argparse import Namespace

from voicetype.cli import run_listen
from voicetype.injector import TextInjector
from voicetype.pipeline import DictationPipeline
from voicetype.qwen_client import QwenClient
from voicetype.settings import Settings
from voicetype.whisper_client import WhisperClient


def build_default_listener_runner() -> Callable[[], None]:
    settings = Settings()
    whisper = WhisperClient(settings.whisper_url, timeout_sec=settings.asr_timeout_sec)
    qwen = QwenClient(settings.llm_base_url, settings.llm_model, settings.llm_timeout_sec) if settings.enable_llm else None
    pipeline = DictationPipeline(
        whisper,
        qwen,
        TextInjector(),
        enable_llm=settings.enable_llm,
    )
    args = Namespace(
        no_paste=False,
        no_llm=not settings.enable_llm,
        hotword=[],
        min_seconds=None,
        notify="overlay",
    )
    return lambda: run_listen(args, settings, pipeline)
```

- [ ] **Step 6: Import-cycle check**

Run:

```powershell
python -c "from voicetype.listener_runtime import build_default_listener_runner; print(callable(build_default_listener_runner()))"
```

Expected:

```text
True
```

- [ ] **Step 7: Commit runtime wrapper**

Run:

```powershell
git add src/voicetype/listener_runtime.py tests/test_listener_runtime.py
git commit -m "feat: add listener runtime wrapper"
git push origin feature/voice-type-mvp
```

---

### Task 4: Tray App Core

**Files:**
- Create: `src/voicetype/tray.py`
- Create: `tests/test_tray.py`

- [ ] **Step 1: Write failing tray state tests**

Create `tests/test_tray.py`:

```python
from voicetype.listener_runtime import ListenerStatus
from voicetype.tray import TrayController


class FakeRuntime:
    def __init__(self):
        self.status = ListenerStatus.READY
        self.started = False

    def start_in_thread(self):
        self.started = True
        self.status = ListenerStatus.RUNNING


def test_tray_controller_starts_runtime():
    runtime = FakeRuntime()
    controller = TrayController(runtime=runtime)

    controller.start()

    assert runtime.started is True


def test_tray_status_label_uses_runtime_status():
    runtime = FakeRuntime()
    runtime.status = ListenerStatus.RUNNING
    controller = TrayController(runtime=runtime)

    assert controller.status_label() == "Status: Running"
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest tests/test_tray.py -q
```

Expected: FAIL because `voicetype.tray` does not exist.

- [ ] **Step 3: Implement tray controller**

Create `src/voicetype/tray.py`:

```python
from pathlib import Path
import os

from PIL import Image, ImageDraw

from voicetype.listener_runtime import VoiceTypeListenerRuntime, build_default_listener_runner
from voicetype.session_log import default_log_dir
from voicetype.startup import disable_startup, enable_startup, is_startup_enabled


class TrayController:
    def __init__(self, *, runtime: VoiceTypeListenerRuntime) -> None:
        self.runtime = runtime

    def start(self) -> None:
        self.runtime.start_in_thread()

    def status_label(self) -> str:
        return f"Status: {self.runtime.status}"

    def open_logs(self) -> None:
        log_dir = default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(log_dir)

    def startup_label(self) -> str:
        return f"Start at Login: {'On' if is_startup_enabled() else 'Off'}"

    def toggle_startup(self) -> None:
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()


def create_icon_image() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#2563eb")
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 10, 50, 46), fill="#f97316")
    draw.rectangle((28, 42, 36, 54), fill="#fff7ed")
    draw.rectangle((20, 54, 44, 58), fill="#fff7ed")
    return image


def run_tray_app() -> None:
    import pystray

    runtime = VoiceTypeListenerRuntime(listener_runner=build_default_listener_runner())
    controller = TrayController(runtime=runtime)
    controller.start()

    icon = pystray.Icon(
        "VoiceType",
        create_icon_image(),
        "VoiceType",
        menu=pystray.Menu(
            pystray.MenuItem(lambda item: controller.status_label(), None, enabled=False),
            pystray.MenuItem("Open Logs", lambda icon, item: controller.open_logs()),
            pystray.MenuItem(lambda item: controller.startup_label(), lambda icon, item: controller.toggle_startup()),
            pystray.MenuItem("Quit VoiceType", lambda icon, item: icon.stop()),
        ),
    )
    icon.run()
```

- [ ] **Step 4: Run tray tests**

Run:

```powershell
python -m pytest tests/test_tray.py -q
```

Expected: pass.

- [ ] **Step 5: Verify icon generation**

Run:

```powershell
python -c "from voicetype.tray import create_icon_image; image=create_icon_image(); print(image.size)"
```

Expected:

```text
(64, 64)
```

- [ ] **Step 6: Commit tray core**

Run:

```powershell
git add src/voicetype/tray.py tests/test_tray.py
git commit -m "feat: add tray controller"
git push origin feature/voice-type-mvp
```

---

### Task 5: CLI Tray Command

**Files:**
- Modify: `src/voicetype/cli.py`
- Modify: `tests/test_cli_entrypoint.py`

- [ ] **Step 1: Write failing parser test**

Add to `tests/test_cli_entrypoint.py`:

```python
def test_cli_has_tray_command():
    parser = build_parser()

    args = parser.parse_args(["tray"])

    assert args.command == "tray"
```

- [ ] **Step 2: Run test and verify red**

Run:

```powershell
python -m pytest tests/test_cli_entrypoint.py::test_cli_has_tray_command -q
```

Expected: FAIL because `tray` is not a valid command.

- [ ] **Step 3: Add parser command**

In `build_parser()`, add:

```python
tray_parser = subparsers.add_parser("tray")
tray_parser.set_defaults(command="tray")
```

- [ ] **Step 4: Add CLI branch**

In `main()`, after parsing args and before service client creation:

```python
if args.command == "tray":
    from voicetype.tray import run_tray_app

    run_tray_app()
    return
```

- [ ] **Step 5: Run CLI tests**

Run:

```powershell
python -m pytest tests/test_cli_entrypoint.py -q
```

Expected: pass.

- [ ] **Step 6: Verify help**

Run:

```powershell
python -m voicetype --help
python -m voicetype tray --help
```

Expected: `tray` appears as a command and `tray --help` exits successfully.

- [ ] **Step 7: Commit CLI command**

Run:

```powershell
git add src/voicetype/cli.py tests/test_cli_entrypoint.py
git commit -m "feat: add tray CLI command"
git push origin feature/voice-type-mvp
```

---

### Task 6: Manual Windows Tray Verification

**Files:**
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Start tray app manually**

Run:

```powershell
python -m voicetype tray
```

Expected:

- VoiceType tray icon appears.
- Right-click menu appears.
- Status item displays current runtime status.

- [ ] **Step 2: Verify Right Ctrl flow**

Manual steps:

1. Open Notepad or another text input.
2. Put the caret in the input field.
3. Press Right Ctrl once.
4. Confirm overlay shows `Listening...`.
5. Speak one short sentence.
6. Press Right Ctrl again.
7. Confirm overlay shows `Processing...`.
8. Confirm text is pasted into the focused input.
9. Run:

```powershell
python -m voicetype logs --today --limit 1
```

Expected: latest log includes the new segment.

- [ ] **Step 3: Verify startup toggle**

Manual steps:

1. Right-click tray icon.
2. Click `Start at Login`.
3. Run:

```powershell
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\VoiceType.cmd"
```

Expected:

```text
True
```

4. Click `Start at Login` again.
5. Re-run the `Test-Path` command.

Expected:

```text
False
```

- [ ] **Step 4: Verify quit**

Manual steps:

1. Right-click tray icon.
2. Click `Quit VoiceType`.

Expected: tray icon disappears.

- [ ] **Step 5: Update README**

Add:

```markdown
## Tray Mode

Start VoiceType in the Windows system tray:

```powershell
python -m voicetype tray
```

For no-console startup, create a shortcut or startup entry that runs:

```powershell
.\.venv\Scripts\pythonw.exe -m voicetype tray
```

Tray mode keeps the existing Right Ctrl listener and overlay behavior. The microphone is still opened only while actively recording.
```

- [ ] **Step 6: Update handoff**

Update `CODEX_HANDOFF.md` with:

- latest tray commits
- tray command
- startup entry behavior
- manual verification results
- caution that tray mode wraps CLI listener and must not keep microphone open while idle

- [ ] **Step 7: Final verification**

Run:

```powershell
python -m pytest -q
python -m compileall -q src tests
git diff --check
git status --short --branch
```

Expected:

- tests pass
- compileall OK
- no diff-check output
- only intended doc changes before commit

- [ ] **Step 8: Commit docs and verification notes**

Run:

```powershell
git add README.md CODEX_HANDOFF.md
git commit -m "docs: document tray mode"
git push origin feature/voice-type-mvp
```

---

## Final Verification Checklist

- [ ] `python -m pytest -q`
- [ ] `python -m compileall -q src tests`
- [ ] `python -m voicetype --help`
- [ ] `python -m voicetype tray --help`
- [ ] `python -m voicetype logs --today --limit 1`
- [ ] manual tray icon appears
- [ ] Right Ctrl listener works from tray mode
- [ ] Startup entry toggle creates/removes `VoiceType.cmd`
- [ ] Quit removes tray icon
- [ ] `git status --short --branch` is clean

---

## Self-Review

Spec coverage:

- Icon click / no terminal launch is covered by `tray` command and `pythonw.exe` startup command.
- Startup at login is covered by `startup.py`.
- Tray menu and background listener are covered by `tray.py` and `listener_runtime.py`.
- Existing listener, overlay, logging, and microphone-idle behavior remain unchanged.

Placeholder scan:

- No placeholder terms remain.
- Manual verification steps include concrete commands and expected results.

Type consistency:

- Startup entry type is `StartupEntry`.
- Runtime status type is `ListenerStatus`.
- Tray runner is `run_tray_app()`.
- CLI command is `python -m voicetype tray`.
