# VoiceType Output Mute During Recording Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mute the Windows default output device while VoiceType is actively recording, then restore the user's previous output mute state.

**Architecture:** Add a focused output-audio guard module with a pycaw-backed Windows implementation and fake-endpoint-friendly unit tests. Wire the guard into the existing `record` command and right Ctrl listener lifecycle so output is restored before ASR, Qwen, paste, short-recording returns, or shutdown cleanup. Tray mode inherits the behavior because it already wraps the listener core.

**Tech Stack:** Python 3.11+, pytest, pycaw/Windows Core Audio, existing sounddevice listener and CLI modules.

---

## File Structure

- Create: `src/voicetype/output_audio.py` - output mute guard protocol, null guard, Windows Core Audio guard, safe helper functions, and factory.
- Create: `tests/test_output_audio.py` - fake endpoint tests for snapshot, restore, idempotency, and safe helper diagnostics.
- Modify: `pyproject.toml` - add `pycaw` runtime dependency.
- Modify: `src/voicetype/cli.py` - create and use output mute guard around fixed-duration recording and right Ctrl listener recording.
- Modify: `tests/test_cli_entrypoint.py` - listener and fixed-recording tests using fake guards, fake recorders, and fake listeners.
- Modify: `README.md` - document that output is muted only during active recording.
- Modify: `CODEX_HANDOFF.md` - update current-state notes, useful files, recent commits, and verification state after implementation.

---

### Task 1: Output Audio Guard

**Files:**
- Create: `src/voicetype/output_audio.py`
- Create: `tests/test_output_audio.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing output guard tests**

Create `tests/test_output_audio.py`:

```python
from voicetype.output_audio import (
    NullOutputMuteGuard,
    WindowsOutputMuteGuard,
    try_mute_for_recording,
    try_restore_output,
)


class FakeEndpointVolume:
    def __init__(self, muted: bool = False) -> None:
        self.muted = muted
        self.calls: list[tuple[str, int | None]] = []

    def GetMute(self) -> int:
        self.calls.append(("GetMute", None))
        return 1 if self.muted else 0

    def SetMute(self, muted: int, event_context) -> None:
        self.calls.append(("SetMute", muted))
        self.muted = bool(muted)


class RaisingGuard:
    def mute_for_recording(self) -> None:
        raise RuntimeError("mute failed")

    def restore(self) -> None:
        raise RuntimeError("restore failed")


def test_windows_guard_restores_unmuted_output_state():
    endpoint = FakeEndpointVolume(muted=False)
    guard = WindowsOutputMuteGuard(endpoint_factory=lambda: endpoint)

    guard.mute_for_recording()
    assert endpoint.muted is True

    guard.restore()
    assert endpoint.muted is False
    assert endpoint.calls == [
        ("GetMute", None),
        ("SetMute", 1),
        ("SetMute", 0),
    ]


def test_windows_guard_preserves_preexisting_muted_state():
    endpoint = FakeEndpointVolume(muted=True)
    guard = WindowsOutputMuteGuard(endpoint_factory=lambda: endpoint)

    guard.mute_for_recording()
    guard.restore()

    assert endpoint.muted is True
    assert endpoint.calls == [
        ("GetMute", None),
        ("SetMute", 1),
        ("SetMute", 1),
    ]


def test_windows_guard_is_idempotent_during_one_recording():
    endpoint = FakeEndpointVolume(muted=False)
    guard = WindowsOutputMuteGuard(endpoint_factory=lambda: endpoint)

    guard.mute_for_recording()
    endpoint.muted = False
    guard.mute_for_recording()
    guard.restore()
    guard.restore()

    assert endpoint.muted is False
    assert endpoint.calls == [
        ("GetMute", None),
        ("SetMute", 1),
        ("SetMute", 0),
    ]


def test_null_guard_is_safe_to_call_repeatedly():
    guard = NullOutputMuteGuard()

    guard.mute_for_recording()
    guard.mute_for_recording()
    guard.restore()
    guard.restore()


def test_safe_helpers_report_mute_and_restore_failures():
    messages: list[str] = []
    guard = RaisingGuard()

    try_mute_for_recording(guard, report=messages.append)
    try_restore_output(guard, report=messages.append)

    assert messages == [
        "[VoiceType] Could not mute output audio: mute failed",
        "[VoiceType] Could not restore output audio: restore failed",
    ]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_output_audio.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'voicetype.output_audio'`.

- [ ] **Step 3: Add pycaw dependency**

In `pyproject.toml`, add `pycaw` to `[project].dependencies`:

```toml
    "pycaw>=20240210",
```

Keep it with the other Windows runtime dependencies near `pystray` and `pillow`.

- [ ] **Step 4: Implement output guard module**

Create `src/voicetype/output_audio.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from ctypes import POINTER, cast
import sys
from typing import Protocol


class OutputMuteGuard(Protocol):
    def mute_for_recording(self) -> None:
        raise NotImplementedError

    def restore(self) -> None:
        raise NotImplementedError


class EndpointVolume(Protocol):
    def GetMute(self) -> int:
        raise NotImplementedError

    def SetMute(self, muted: int, event_context) -> None:
        raise NotImplementedError


class NullOutputMuteGuard:
    def mute_for_recording(self) -> None:
        return

    def restore(self) -> None:
        return


class WindowsOutputMuteGuard:
    def __init__(self, *, endpoint_factory: Callable[[], EndpointVolume] | None = None) -> None:
        self._endpoint_factory = endpoint_factory or _default_endpoint_volume
        self._endpoint: EndpointVolume | None = None
        self._previous_mute: bool | None = None
        self._active = False

    def mute_for_recording(self) -> None:
        if self._active:
            return

        endpoint = self._endpoint_factory()
        self._previous_mute = bool(endpoint.GetMute())
        endpoint.SetMute(1, None)
        self._endpoint = endpoint
        self._active = True

    def restore(self) -> None:
        if not self._active or self._endpoint is None or self._previous_mute is None:
            return

        endpoint = self._endpoint
        previous_mute = self._previous_mute
        try:
            endpoint.SetMute(1 if previous_mute else 0, None)
        finally:
            self._endpoint = None
            self._previous_mute = None
            self._active = False


def create_output_mute_guard() -> OutputMuteGuard:
    if sys.platform != "win32":
        return NullOutputMuteGuard()
    return WindowsOutputMuteGuard()


def try_mute_for_recording(
    guard: OutputMuteGuard,
    *,
    report: Callable[[str], None] = print,
) -> None:
    try:
        guard.mute_for_recording()
    except Exception as exc:
        report(f"[VoiceType] Could not mute output audio: {exc}")


def try_restore_output(
    guard: OutputMuteGuard,
    *,
    report: Callable[[str], None] = print,
) -> None:
    try:
        guard.restore()
    except Exception as exc:
        report(f"[VoiceType] Could not restore output audio: {exc}")


def _default_endpoint_volume() -> EndpointVolume:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    speakers = AudioUtilities.GetSpeakers()
    interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))
```

- [ ] **Step 5: Run output guard tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_output_audio.py -q
```

Expected: `5 passed`.

- [ ] **Step 6: Commit output guard**

Run:

```powershell
git add pyproject.toml src/voicetype/output_audio.py tests/test_output_audio.py
git commit -m "feat: add output mute guard"
```

---

### Task 2: Wire Guard Into Recording Flows

**Files:**
- Modify: `src/voicetype/cli.py`
- Modify: `tests/test_cli_entrypoint.py`

- [ ] **Step 1: Write failing tests for fixed recording and listener lifecycle**

Append to `tests/test_cli_entrypoint.py`:

```python
from argparse import Namespace
from pathlib import Path

import voicetype.cli as cli


class FakeOutputGuard:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def mute_for_recording(self) -> None:
        self.events.append("guard.mute")

    def restore(self) -> None:
        self.events.append("guard.restore")


def test_record_wav_with_output_muted_restores_after_recording(tmp_path):
    events: list[str] = []
    audio_path = tmp_path / "sample.wav"

    def fake_record_wav(seconds: float, *, sample_rate: int, channels: int) -> Path:
        events.append(f"record:{seconds}:{sample_rate}:{channels}")
        audio_path.write_bytes(b"fake wav")
        return audio_path

    result = cli.record_wav_with_output_muted(
        3.0,
        sample_rate=16000,
        channels=1,
        output_guard=FakeOutputGuard(events),
        record_func=fake_record_wav,
    )

    assert result == audio_path
    assert events == ["guard.mute", "record:3.0:16000:1", "guard.restore"]


def test_record_wav_with_output_muted_restores_when_recording_fails():
    events: list[str] = []

    def fake_record_wav(seconds: float, *, sample_rate: int, channels: int) -> Path:
        events.append("record")
        raise RuntimeError("record failed")

    try:
        cli.record_wav_with_output_muted(
            3.0,
            sample_rate=16000,
            channels=1,
            output_guard=FakeOutputGuard(events),
            record_func=fake_record_wav,
        )
    except RuntimeError as exc:
        assert str(exc) == "record failed"
    else:
        raise AssertionError("recording failure was not propagated")

    assert events == ["guard.mute", "record", "guard.restore"]


def test_run_listen_mutes_after_start_and_restores_before_processing(monkeypatch, tmp_path):
    events: list[str] = []
    audio_path = tmp_path / "listen.wav"
    audio_path.write_bytes(b"fake wav")

    class FakeRecorder:
        def __init__(self, *, sample_rate: int, channels: int) -> None:
            self.is_recording = False
            self.duration_seconds = 1.0

        def start(self) -> None:
            events.append("recorder.start")
            self.is_recording = True

        def stop_to_wav(self) -> Path:
            events.append("recorder.stop")
            self.is_recording = False
            return audio_path

        def cancel(self) -> None:
            events.append("recorder.cancel")
            self.is_recording = False

    class FakeListener:
        def __init__(self, on_toggle) -> None:
            self.on_toggle = on_toggle

        def run(self) -> None:
            self.on_toggle()
            self.on_toggle()

        def stop(self) -> None:
            events.append("listener.stop")

    class FakeNotifier:
        def notify(self, message: str) -> None:
            return

    class FakePipeline:
        def process_file_result(self, audio_path, *, app_name, hotwords, paste):
            events.append("pipeline.process")
            return cli.PipelineResult(status="inserted", raw_text="raw", final_text="final")

    monkeypatch.setattr(cli, "ToggleRecorder", FakeRecorder)
    monkeypatch.setattr(cli, "RightCtrlToggleListener", FakeListener)
    monkeypatch.setattr(cli, "create_output_mute_guard", lambda: FakeOutputGuard(events))
    monkeypatch.setattr(cli, "create_notifier", lambda notify: FakeNotifier())
    monkeypatch.setattr(cli, "get_active_app_name", lambda: "notepad")
    monkeypatch.setattr(cli, "normalize_wav", lambda path: events.append("normalize") or None)
    monkeypatch.setattr(cli, "append_session_record", lambda logger, record: events.append("session.log"))
    monkeypatch.setattr(cli, "SessionLogger", lambda: object())

    args = Namespace(
        no_paste=True,
        no_llm=True,
        hotword=[],
        min_seconds=None,
        notify="off",
        listener_holder=None,
    )
    settings = Namespace(sample_rate=16000, channels=1, min_record_seconds=0.7)

    cli.run_listen(args, settings, FakePipeline())

    assert events[:5] == [
        "recorder.start",
        "guard.mute",
        "recorder.stop",
        "guard.restore",
        "normalize",
    ]
    assert "pipeline.process" in events


def test_run_listen_restores_output_for_short_recording(monkeypatch, tmp_path):
    events: list[str] = []
    audio_path = tmp_path / "short.wav"
    audio_path.write_bytes(b"fake wav")

    class FakeRecorder:
        def __init__(self, *, sample_rate: int, channels: int) -> None:
            self.is_recording = False
            self.duration_seconds = 0.1

        def start(self) -> None:
            events.append("recorder.start")
            self.is_recording = True

        def stop_to_wav(self) -> Path:
            events.append("recorder.stop")
            self.is_recording = False
            return audio_path

        def cancel(self) -> None:
            events.append("recorder.cancel")
            self.is_recording = False

    class FakeListener:
        def __init__(self, on_toggle) -> None:
            self.on_toggle = on_toggle

        def run(self) -> None:
            self.on_toggle()
            self.on_toggle()

        def stop(self) -> None:
            return

    class FakeNotifier:
        def notify(self, message: str) -> None:
            return

    class FakePipeline:
        def process_file_result(self, *args, **kwargs):
            events.append("pipeline.process")
            raise AssertionError("short recording should not be processed")

    monkeypatch.setattr(cli, "ToggleRecorder", FakeRecorder)
    monkeypatch.setattr(cli, "RightCtrlToggleListener", FakeListener)
    monkeypatch.setattr(cli, "create_output_mute_guard", lambda: FakeOutputGuard(events))
    monkeypatch.setattr(cli, "create_notifier", lambda notify: FakeNotifier())
    monkeypatch.setattr(cli, "get_active_app_name", lambda: "notepad")
    monkeypatch.setattr(cli, "append_session_record", lambda logger, record: events.append("session.log"))
    monkeypatch.setattr(cli, "SessionLogger", lambda: object())

    args = Namespace(
        no_paste=True,
        no_llm=True,
        hotword=[],
        min_seconds=None,
        notify="off",
        listener_holder=None,
    )
    settings = Namespace(sample_rate=16000, channels=1, min_record_seconds=0.7)

    cli.run_listen(args, settings, FakePipeline())

    assert events[:4] == ["recorder.start", "guard.mute", "recorder.stop", "guard.restore"]
    assert "pipeline.process" not in events


def test_run_listen_restores_output_when_stopped_while_recording(monkeypatch):
    events: list[str] = []

    class FakeRecorder:
        def __init__(self, *, sample_rate: int, channels: int) -> None:
            self.is_recording = False

        def start(self) -> None:
            events.append("recorder.start")
            self.is_recording = True

        def cancel(self) -> None:
            events.append("recorder.cancel")
            self.is_recording = False

    class FakeListener:
        def __init__(self, on_toggle) -> None:
            self.on_toggle = on_toggle

        def run(self) -> None:
            self.on_toggle()
            raise KeyboardInterrupt

        def stop(self) -> None:
            return

    class FakeNotifier:
        def notify(self, message: str) -> None:
            return

    monkeypatch.setattr(cli, "ToggleRecorder", FakeRecorder)
    monkeypatch.setattr(cli, "RightCtrlToggleListener", FakeListener)
    monkeypatch.setattr(cli, "create_output_mute_guard", lambda: FakeOutputGuard(events))
    monkeypatch.setattr(cli, "create_notifier", lambda notify: FakeNotifier())
    monkeypatch.setattr(cli, "SessionLogger", lambda: object())

    args = Namespace(
        no_paste=True,
        no_llm=True,
        hotword=[],
        min_seconds=None,
        notify="off",
        listener_holder=None,
    )
    settings = Namespace(sample_rate=16000, channels=1, min_record_seconds=0.7)

    cli.run_listen(args, settings, object())

    assert events == ["recorder.start", "guard.mute", "recorder.cancel", "guard.restore"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_cli_entrypoint.py -q
```

Expected: FAIL with `AttributeError: module 'voicetype.cli' has no attribute 'record_wav_with_output_muted'`.

- [ ] **Step 3: Import output guard helpers in CLI**

In `src/voicetype/cli.py`, add:

```python
from collections.abc import Callable
```

Add these imports with the other `voicetype` imports:

```python
from voicetype.output_audio import (
    OutputMuteGuard,
    create_output_mute_guard,
    try_mute_for_recording,
    try_restore_output,
)
```

- [ ] **Step 4: Add fixed-recording helper**

In `src/voicetype/cli.py`, add this function above `main()`:

```python
def record_wav_with_output_muted(
    seconds: float,
    *,
    sample_rate: int,
    channels: int,
    output_guard: OutputMuteGuard | None = None,
    record_func: Callable[..., Path] = record_wav,
) -> Path:
    guard = output_guard or create_output_mute_guard()
    try_mute_for_recording(guard)
    try:
        return record_func(seconds, sample_rate=sample_rate, channels=channels)
    finally:
        try_restore_output(guard)
```

- [ ] **Step 5: Use helper in `record` command**

In `main()`, replace:

```python
        audio_file = record_wav(
            args.seconds or settings.record_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
        )
```

with:

```python
        audio_file = record_wav_with_output_muted(
            args.seconds or settings.record_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
        )
```

- [ ] **Step 6: Wire output guard into listener start, stop, and cleanup**

In `run_listen()`, after `recording_started_at = {"value": None}`, add:

```python
    output_guard = create_output_mute_guard()
```

In the start-recording branch, after `recorder.start()`, add:

```python
                try_mute_for_recording(output_guard)
```

The start branch should be:

```python
            if not recorder.is_recording:
                recorder.start()
                try_mute_for_recording(output_guard)
                recording_started_at["value"] = current_timestamp()
                notifier.notify("Listening...")
                update_listener_status(args, "Listening")
                return
```

In the stop-recording branch, after `audio_path = recorder.stop_to_wav()`, add:

```python
            try_restore_output(output_guard)
```

The stop branch should begin:

```python
            notifier.notify("Processing...")
            update_listener_status(args, "Processing")
            audio_path = recorder.stop_to_wav()
            try_restore_output(output_guard)
            completed_at = current_timestamp()
```

In the `finally` block, after `recorder.cancel()`, add restore:

```python
        if recorder.is_recording:
            recorder.cancel()
            try_restore_output(output_guard)
```

- [ ] **Step 7: Run CLI tests to verify GREEN**

Run:

```powershell
python -m pytest tests/test_cli_entrypoint.py tests/test_output_audio.py -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Commit CLI wiring**

Run:

```powershell
git add src/voicetype/cli.py tests/test_cli_entrypoint.py
git commit -m "feat: mute output during recording"
```

---

### Task 3: Documentation and Handoff

**Files:**
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Update README listener behavior**

In `README.md`, replace the tray/listener sentence:

```markdown
Tray mode keeps the existing right Ctrl listener and overlay behavior. The microphone is still opened only while actively recording.
```

with:

```markdown
Tray mode keeps the existing right Ctrl listener and overlay behavior. The microphone is still opened only while actively recording, and Windows output audio is temporarily muted during that active recording window.
```

After the manual test step `Press the right Ctrl key once to start listening.`, add this step:

```markdown
5. Windows output audio is muted while VoiceType records.
```

Renumber the following manual test steps so the flow remains sequential.

After the paragraph that begins `When you press right Ctrl to start recording`, add:

```markdown
VoiceType restores the previous Windows output mute state as soon as recording stops. If output was already muted before dictation, it remains muted afterward.
```

- [ ] **Step 2: Update handoff current state**

In `CODEX_HANDOFF.md`, add a bullet under the right Ctrl behavior bullets:

```markdown
- Windows default output audio is muted only during active recording and restored to its previous mute state before transcription, Qwen polish, or paste work begins.
```

In `Useful Files`, add:

```markdown
- `src/voicetype/output_audio.py` - Windows output mute guard and safe restore helpers
```

In `User Preferences and Decisions`, add:

```markdown
- Output audio should be muted during active recording to reduce playback bleed into the microphone, then restored to the user's previous mute state.
```

In `Cautions`, add:

```markdown
- Do not mute output outside active recording, and do not overwrite a user's preexisting muted state.
```

- [ ] **Step 3: Run documentation diff check**

Run:

```powershell
git diff -- README.md CODEX_HANDOFF.md
```

Expected: diff only documents output muting during active recording and does not change hotkey, endpoint, hotword, or correction-memory behavior.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add README.md CODEX_HANDOFF.md
git commit -m "docs: document recording output mute"
```

---

### Task 4: Full Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
python -m compileall -q src tests
```

Expected: exits 0 with no output.

- [ ] **Step 3: Run CLI help smoke tests**

Run:

```powershell
python -m voicetype --help
python -m voicetype record --help
python -m voicetype listen --help
python -m voicetype tray --help
```

Expected: each command prints help and exits 0.

- [ ] **Step 4: Confirm git state**

Run:

```powershell
git status --short
git log -5 --oneline
```

Expected: clean worktree. The latest commits include:

```text
docs: document recording output mute
feat: mute output during recording
feat: add output mute guard
docs: design output mute during recording
```

- [ ] **Step 5: Update handoff verification if full checks passed**

If all verification commands pass, update the `Last known verification` block in `CODEX_HANDOFF.md` to include the new pass count and the compile/help smoke checks. Commit only this verification refresh:

```powershell
git add CODEX_HANDOFF.md
git commit -m "docs: refresh VoiceType handoff"
```

Skip this commit if Task 3 already recorded the exact verification results after implementation.

---

## Self-Review

Spec coverage:

- Active-recording-only mute is covered by Task 2 listener and fixed-record helper wiring.
- Previous mute state restoration is covered by Task 1 fake endpoint tests.
- Short recording restore is covered by Task 2 listener test.
- Shutdown cleanup restore is covered by Task 2 KeyboardInterrupt test.
- Tray inheritance is covered by using the existing `run_listen()` core.
- Documentation is covered by Task 3.

Placeholder scan:

- The plan contains no unresolved placeholder markers or unspecified test steps.

Type consistency:

- The plan consistently uses `OutputMuteGuard.mute_for_recording()` and `OutputMuteGuard.restore()`.
- The CLI helper consistently accepts `output_guard` and `record_func` injection for tests.
- `WindowsOutputMuteGuard(endpoint_factory=...)` supports fake endpoint tests without touching real Windows audio devices.
