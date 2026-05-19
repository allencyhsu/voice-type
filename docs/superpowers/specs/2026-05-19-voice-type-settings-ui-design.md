# VoiceType Settings UI v1 Design

## Summary

VoiceType Settings UI v1 adds a small native Windows settings window opened from the existing tray menu. The UI should make day-to-day configuration possible without editing environment variables, command lines, or JSONL files by hand.

The first version stays inside the current Python desktop stack. It uses Tkinter because VoiceType already uses Tk for overlay/status dialogs, and it avoids adding a local web server, WebView shell, installer, or additional runtime.

## Goals

- Add a `Settings...` action to the VoiceType tray menu.
- Show a focused Tkinter settings window for common VoiceType configuration.
- Persist UI settings under `%LOCALAPPDATA%\VoiceType\settings.json`.
- Preserve environment variable overrides for advanced/debug use.
- Let the user manage correction memory entries from the UI.
- Keep startup-at-login reversible through the existing Startup folder command file.
- Keep listener/tray runtime behavior stable while settings UI is open.

## Non-Goals

- Do not replace the tray app with a full standalone desktop application.
- Do not add a web server, browser UI, Tauri, Electron, or .NET shell for v1.
- Do not build a rich table editor with search, bulk import, or sync in v1.
- Do not change the Right Ctrl hotkey behavior in v1.
- Do not make the microphone stay open while idle.
- Do not send full correction memory or long hotwords to Faster Whisper.

## User Flow

1. User starts VoiceType tray mode.
2. User right-clicks the tray icon.
3. User chooses `Settings...`.
4. VoiceType opens a top-most settings window.
5. User changes settings and clicks `Save`.
6. VoiceType writes `%LOCALAPPDATA%\VoiceType\settings.json`.
7. VoiceType applies settings that are safe to apply immediately.
8. For settings that require listener restart, the UI shows a short status message.

The window should be modeless enough that it does not block tray shutdown, but only one settings window should be open at a time.

## Settings Store

Create a small settings store separate from environment variables:

```text
%LOCALAPPDATA%\VoiceType\settings.json
```

Example:

```json
{
  "enable_llm": true,
  "notify": "overlay",
  "record_seconds": 8.0,
  "min_record_seconds": 0.7,
  "whisper_url": "http://forge2.tail9d0481.ts.net:8008",
  "llm_base_url": "http://ai-srv.tail9d0481.ts.net:8001/v1",
  "llm_model": "qwen3.6-35b"
}
```

Configuration precedence:

1. `VOICETYPE_*` environment variables
2. `%LOCALAPPDATA%\VoiceType\settings.json`
3. built-in defaults in `Settings`

If the settings file is missing or malformed, VoiceType should fall back to defaults and show a non-fatal status message in the UI.

## UI Content

Settings window sections:

- Services
  - Faster Whisper URL
  - Qwen base URL
  - Qwen model
  - Enable Qwen polish checkbox
- Dictation
  - Notification mode dropdown: `overlay`, `console`, `toast`, `off`
  - Record seconds numeric input
  - Minimum recording seconds numeric input
  - Read-only reminder: hotkey is Right Ctrl
- Startup and diagnostics
  - Start at login checkbox
  - Open logs button
  - Show latest log button
- Correction memory
  - List existing correction entries
  - Add term correction: `wrong` and `correct`
  - Add phrase correction: `wrong` and `correct`
  - Remove selected correction

The UI should use compact controls and plain labels. It should not become a marketing-style page or a large dashboard.

## Correction Memory UI Rules

- Correction memory continues to live in `%LOCALAPPDATA%\VoiceType\memory\corrections.jsonl`.
- Add term and add phrase actions call the same store used by the CLI.
- Remove selected entry calls the same remove logic used by the CLI.
- The UI must display Unicode correctly.
- The UI should remind the user that long terms and phrase corrections go to Qwen, not Faster Whisper.
- Faster Whisper hotword policy remains unchanged: at most five hotwords, each at most five Unicode characters.

## Runtime Behavior

The tray controller owns opening the settings window. The listener runtime should keep running while the settings window is open.

Immediate effects:

- Startup-at-login toggle should enable or disable `VoiceType.cmd` immediately.
- Correction memory add/remove should take effect for future dictation segments.
- Opening logs and showing latest log should work immediately.

Restart-required or next-session effects:

- Service URL changes
- Qwen model changes
- Enable Qwen polish changes
- Notification mode changes for the existing listener runtime
- Recording duration thresholds

The first version shows `Saved. Restart VoiceType for all settings to take effect.` after save for settings that are not applied immediately.

## Error Handling

- If settings save fails, keep the window open and show the exception text in a status label.
- If settings load fails, fall back to defaults and show `Loaded defaults; settings file could not be read.`
- If startup toggle fails, show a non-fatal status message.
- If correction memory load has malformed rows, skip malformed rows using the existing memory store behavior.
- If correction memory add/remove fails, show a non-fatal status message and do not close the window.

## File Boundaries

Expected implementation units:

- `src/voicetype/user_settings.py`
  - default settings file path
  - load/save JSON settings
  - merge settings-file values with `Settings`
- `src/voicetype/settings_ui.py`
  - Tkinter settings window
  - controls and callbacks
  - correction memory list management
- `src/voicetype/tray.py`
  - add `Settings...` menu item
  - open only one settings window
- `src/voicetype/settings.py`
  - optionally read settings JSON as a lower-priority source than env vars

Existing files should not be broadly refactored. Keep tray mode as a wrapper around the listener core.

## Testing Strategy

- Unit test settings JSON path and load/save behavior.
- Unit test environment variables override settings JSON.
- Unit test malformed settings JSON falls back safely.
- Unit test tray controller calls the settings window opener.
- Unit test startup checkbox actions use the existing startup functions through injectable callbacks.
- Unit test correction memory add/remove callbacks use `CorrectionMemoryStore`.
- Unit test Settings UI model helpers without requiring a real interactive display where possible.

Manual verification:

- `python -m voicetype tray` shows a `Settings...` menu item.
- Opening settings twice reuses or focuses the existing window instead of creating duplicate windows.
- Saving settings writes `%LOCALAPPDATA%\VoiceType\settings.json`.
- Start at login checkbox updates `VoiceType.cmd`.
- Add/remove correction memory from UI is reflected by `python -m voicetype memory list`.
- Existing listener and quit behavior still work.

## Acceptance Criteria

- `python -m pytest -q` passes.
- `python -m compileall -q src tests` passes.
- `python -m voicetype tray --help` still works.
- The tray menu includes `Settings...`.
- Settings can be saved to `%LOCALAPPDATA%\VoiceType\settings.json`.
- Environment variables still override UI settings.
- Correction memory can be added and removed from the settings window.
- Startup-at-login can be toggled from the settings window.
- The existing tray Quit path still stops the listener/runtime cleanly.
