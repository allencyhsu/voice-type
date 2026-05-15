# VoiceType Tray App v1 Design

## Goal

VoiceType Tray App v1 makes the existing voice typing listener usable without manually opening a terminal. The user should be able to launch VoiceType from an icon, keep it running in the Windows system tray, and optionally start it automatically after login.

## Non-Goals

- Do not replace the current CLI listener core.
- Do not keep the microphone open while idle.
- Do not build a full desktop settings application yet.
- Do not build an installer, updater, account system, or cloud sync.
- Do not change the current hotkey toggle behavior.

## User Experience

The first tray version should feel like a lightweight resident utility:

1. User starts `python -m voicetype tray`, or clicks a shortcut that starts the same command through `pythonw.exe`.
2. A VoiceType icon appears in the Windows tray.
3. The existing Right Alt toggle works while the tray app is running.
4. The existing top-most overlay still shows `Listening...`, `Processing...`, and final result statuses.
5. The tray menu exposes practical commands:
   - status label
   - open logs directory
   - show latest log
   - enable or disable startup at login
   - quit VoiceType

The tray icon is not the recording trigger in v1. Recording remains controlled by Right Alt so that the existing tested flow remains stable.

## Architecture

Tray App v1 wraps the existing listener in a small runtime service. The listener service owns the blocking hotkey loop and runs it in a background thread when launched by the tray app. The voice pipeline, overlay notifier, session logging, temp audio retention, active app detection, Whisper, and Qwen clients remain the same components already used by CLI listener mode.

Startup-at-login is implemented with a Windows Startup folder entry. This keeps v1 simple and reversible. The startup target should use the current virtual environment's `pythonw.exe` when available, so startup does not show a console window.

## Proposed Modules

- `src/voicetype/listener_runtime.py`
  - Builds settings, Whisper/Qwen clients, injector, pipeline, and the listener loop.
  - Provides a `VoiceTypeListenerRuntime` class with `start_in_thread()` and status tracking.
  - Reuses existing `run_listen()` behavior where practical, but should make status visible to tray.

- `src/voicetype/startup.py`
  - Computes the Startup folder path.
  - Computes the command for launching tray mode.
  - Enables, disables, and checks the startup shortcut or command file.

- `src/voicetype/tray.py`
  - Owns pystray icon creation and menu actions.
  - Starts listener runtime in the background.
  - Opens logs folder.
  - Shows latest log using existing session log formatting helpers.
  - Toggles startup at login.
  - Quits cleanly.

- `src/voicetype/cli.py`
  - Adds `tray` command.
  - Delegates to `voicetype.tray.run_tray_app()`.

## Dependencies

Add runtime dependencies:

- `pystray`
- `pillow`

`pystray` provides the tray icon and menu. `pillow` generates a simple in-memory icon so v1 does not need a checked-in image asset.

## Startup Entry

The Startup entry should be named `VoiceType.cmd` or equivalent. It should launch tray mode using:

```powershell
<venv>\Scripts\pythonw.exe -m voicetype tray
```

If `pythonw.exe` is not available, fall back to `python.exe`. The startup module should only create or remove VoiceType-owned files and should not touch unrelated startup entries.

## Status Model

Minimum tray statuses:

- `Ready`
- `Listening`
- `Processing`
- `Stopped`
- `Error`

The overlay remains the primary high-visibility state surface. Tray status is a secondary affordance for checking whether VoiceType is running.

## Error Handling

- If tray dependencies are missing, `python -m voicetype tray` should print an actionable install message.
- If startup folder access fails, show a tray-safe error message and do not crash the listener.
- If logs do not exist, `Show Latest Log` should display or print the same friendly message as `logs --last`.
- If the listener crashes, tray status should move to `Error`.

## Privacy and Retention

Tray mode does not change retention behavior. WAV files are retained only for the current local day. JSONL logs remain under `%LOCALAPPDATA%\VoiceType\logs`.

## Testing Strategy

Unit tests should avoid opening an actual tray UI. Tray code should be dependency-injected so tests can verify menu actions, status strings, and startup toggles with fake backends. Startup tests should use temporary directories instead of the real Windows Startup folder.

Manual smoke checks are still required on Windows for:

- `python -m voicetype tray`
- right-click tray menu appears
- Right Alt listener still works
- startup entry enable/disable creates/removes the expected file
- `Quit VoiceType` stops the tray app

## Acceptance Criteria

- `python -m voicetype tray` starts without opening a terminal when run via `pythonw.exe`.
- Tray icon appears.
- Existing Right Alt listener works from tray mode.
- Tray menu can open logs directory.
- Tray menu can show latest log.
- Tray menu can enable and disable startup at login.
- Startup entry points to tray mode.
- Tests pass.
- Handoff and README are updated.
