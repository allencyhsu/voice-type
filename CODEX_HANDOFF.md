# VoiceType Handoff

## Current State

- Repo: `git@github.com:allencyhsu/voice-type.git`
- Working branch: `feature/env-example-settings`
- Latest implementation/test commit covered by this handoff: `efd0844 test: verify env example defaults`
- Env-example branch docs are covered through `35e1ad4 docs: refresh env example handoff state`; check `git log --oneline` for the exact latest docs refresh after this fix commit.
- Workspace used in recent work: `C:\Users\Allen\Desktop\Projects\VoiceType`
- Python environment: local `.venv`

This handoff tracks the current VoiceType branch state, including the env-example settings workflow and earlier output-mute work. Env-example branch docs are committed through `35e1ad4 docs: refresh env example handoff state`; the latest implementation/test commit before the final review fix is `efd0844 test: verify env example defaults`.

## Service Endpoints

- Faster Whisper server: `http://forge2.tail9d0481.ts.net:8008`
- Faster Whisper model: `large-v2`
- Qwen llama-server OpenAI-compatible base URL: `http://ai-srv.tail9d0481.ts.net:8001/v1`
- Chat completions path: `/chat/completions`
- Qwen model setting: `qwen3.6-35b`

Important note: Whisper and Qwen are on different hosts. Do not mix the earlier `forge2` llama-server path with the current Qwen endpoint.

## Implemented Capabilities

- CLI package with `doctor`, `transcribe`, `record`, `listen`, `logs`, `memory`, and `tray` commands.
- `.env-example` is a tracked settings template; copy it to ignored `.env` for local endpoint, timeout, recording, and LLM settings.
- Tray mode wraps the existing listener runtime and keeps Right Ctrl as the recording toggle.
- Tray status now reflects the listener state (`Ready`, `Listening`, `Processing`, `Stopped`, or `Error`) instead of only showing a generic running state.
- Tray mode includes `Show Latest Log`, which displays the newest session log record without opening the log directory.
- Tray mode can toggle a Windows Startup folder entry named `VoiceType.cmd`.
- Tray Quit stops the background listener/hotkey path before closing the icon.
- Right Ctrl toggles listener mode:
  - first press starts recording
  - second press stops recording, normalizes audio, transcribes, optionally polishes, and pastes through the clipboard
- Microphone is opened only during active recording. It is not kept open while idle.
- If VoiceType exits while recording, the active audio stream is cancelled and closed instead of being left open.
- Windows default output audio is muted only during active recording and restored to its previous mute state before transcription, Qwen polish, or paste work begins.
- Default status UI is a top-most Tk overlay above the Windows taskbar.
- Overlay behavior:
  - `Listening...` remains visible until the next Right Ctrl press
  - `Processing...`, `Inserted text.`, `No text recognized.`, and ignored-short-recording statuses auto-hide
  - diagnostic messages such as captured file path and normalization gain are not shown in the overlay
- Optional notification modes:
  - `--notify overlay`
  - `--notify console`
  - `--notify toast`
  - `--notify off`
- Audio normalization is applied before transcription when the captured peak is low.
- Very short accidental recordings are ignored by `min_record_seconds`, default `0.7`.
- Temporary WAV files are retained for the current local calendar day only. On startup, `voicetype-*.wav` older than local midnight are removed.
- Listener session logs are written as JSONL to `%LOCALAPPDATA%\VoiceType\logs\YYYY-MM-DD.jsonl`.
- Session logs include start/end time, WAV path, audio duration, file bytes, normalization info, ASR status, raw/final text, paste flag, correction memory metadata, Whisper hotword filtering metadata, and ignored-recording reason.
- `logs` CLI command can show today's recent session records, show only the newest record with `--last`, emit records as JSONL, and open the log directory.
- `--hotword` values are passed to Qwen polish payloads. Faster Whisper receives only the filtered hotword shortlist.
- Faster Whisper hotwords are capped to five entries of five Unicode characters each.
- Phrase corrections and long terms are sent only to Qwen, not Faster Whisper.
- Correction Memory v1 stores local term and phrase corrections in `%LOCALAPPDATA%\VoiceType\memory\corrections.jsonl`.
- The `memory` CLI can add, list, remove, and learn conservative phrase corrections from the latest session log.
- Listener mode detects the currently focused Windows app and passes the app name to Qwen as `app_name`.
- Listener session logs include `app_name`; older logs before this feature show `app=unknown` in summaries.
- Qwen polish is instructed to preserve the Chinese script used by the transcript. Traditional Chinese input should remain Traditional Chinese, and Simplified Chinese input should remain Simplified Chinese.
- Qwen polish fails open to raw Whisper text on server error, timeout, invalid JSON, or unusable response.

## Common Commands

Set up:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env-example .env
```

Run listener:

```powershell
python -m voicetype listen
```

Run listener without paste or Qwen:

```powershell
python -m voicetype listen --no-paste --no-llm
```

Run with hotwords:

```powershell
python -m voicetype listen --hotword Qwen --hotword Allen
```

Manage correction memory:

```powershell
python -m voicetype memory add --type term --wrong "cue and" --correct "Qwen"
python -m voicetype memory add --type phrase --wrong "重新開幾" --correct "重新開機"
python -m voicetype memory list
python -m voicetype memory remove <id>
python -m voicetype memory learn --from-last --corrected "corrected final text"
```

Check services:

```powershell
python -m voicetype doctor
```

Show recent session logs:

```powershell
python -m voicetype logs --today
python -m voicetype logs --today --limit 5
python -m voicetype logs --today --limit 5 --json
python -m voicetype logs --last
python -m voicetype logs --last --json
python -m voicetype logs --open-dir
```

Run tray mode:

```powershell
python -m voicetype tray
.\.venv\Scripts\pythonw.exe -m voicetype tray
```

Verification:

```powershell
python -m pytest -q
python -m compileall -q src tests
python -m voicetype --help
python -m voicetype record --help
python -m voicetype tray --help
python -m voicetype listen --help
```

Last known verification:

```text
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
OK, installed pycaw/comtypes runtime dependency in the worktree venv

.\.venv\Scripts\python.exe -m pytest -q
100 passed

.\.venv\Scripts\python.exe -m compileall -q src tests
OK

.\.venv\Scripts\python.exe -m voicetype --help
OK

.\.venv\Scripts\python.exe -m voicetype record --help
OK

.\.venv\Scripts\python.exe -m voicetype listen --help
OK

.\.venv\Scripts\python.exe -m voicetype tray --help
OK

real Windows output endpoint smoke
OK, pycaw resolved AudioUtilities.GetSpeakers().EndpointVolume
OK, mute state changed initial 0 -> during 1 -> restored 0
```

## Recent Commits

- `35e1ad4 docs: refresh env example handoff state`
- `23d884b docs: document env settings workflow`
- `efd0844 test: verify env example defaults`
- `5393762 feat: add env example template`
- `60874ae docs: plan env example settings`
- `afcf89e docs: design env example settings`
- `64d052a docs: refresh handoff after pycaw endpoint fix`
- `ffd1f34 fix: support current pycaw speaker endpoint`
- `153de28 docs: refresh output mute verification`
- `c07ad93 docs: make output mute handoff state durable`
- `cf7108d docs: align output mute handoff commit state`
- `4f8423e docs: refresh output mute handoff state`
- `5f8f5bb docs: document recording output mute`
- `5ee74e8 fix: restore output when recording stop fails`
- `011b14b feat: mute output during recording`
- `a76b363 feat: add output mute guard`
- `cb74368 docs: plan output mute during recording`
- `dbe597c docs: design output mute during recording`
- `597ff28 feat: add correction memory CLI`
- `f5ac281 feat: use correction memory in pipeline`
- `c05785a feat: send correction memory to Qwen`
- `beef3a4 feat: cap Faster Whisper hotwords`
- `17e1efe feat: add correction memory store`
- `52ce2fb docs: plan correction memory v1`
- `ad561b9 docs: design correction memory v1`
- `8f32d6e revert: restore right ctrl toggle hotkey`
- `e0231bb fix: complete tray review follow-ups`
- `467b802 docs: document tray mode`
- `913dcf2 feat: add tray CLI command`
- `c20f526 feat: add tray controller`
- `c00bfcf feat: add listener runtime wrapper`
- `f1c9e98 feat: manage Windows startup entry`
- `13e8fea chore: add tray dependencies`
- `019c42d docs: plan tray app v1`
- `76d91ff feat: pass active app context to Qwen`
- `66e755f docs: update handoff for Chinese script preservation`
- `0b1efe1 fix: preserve Chinese script in Qwen polish`
- `54d1fd8 docs: update handoff after log CLI`
- `9d8132d feat: add session log CLI`
- `b6d8e2a docs: add VoiceType handoff`
- `d07ee14 feat: pass hotwords to Qwen polish`
- `902ad6c feat: add listener session logs`
- `bd5a548 feat: keep overlay visible while listening`
- `555ce97 feat: add overlay status notifier`
- `c8c7eb6 feat: add optional toast notifications`
- `1ba22e9 feat: add listen status guard`
- `a27e16b feat: clean old temp audio on startup`
- `e31c241 fix: normalize recorded audio before transcription`

## User Preferences and Decisions

- Primary interaction should feel like Typeless: hotkey-driven, low-friction, and visible while listening.
- Right Ctrl is the current toggle key.
- The user does not want the microphone kept open while VoiceType is idle.
- Output audio should be muted during active recording to reduce playback bleed into the microphone, then restored to the user's previous mute state.
- About 0.2 seconds of microphone cold-start latency is acceptable.
- Toast notifications are less intuitive for this workflow; overlay is preferred.
- Overlay should be visually obvious, not plain black/white, and should sit above the Windows taskbar rather than at the top of the screen.
- `Captured...` and `Normalized audio...` are diagnostic and should stay out of the overlay.
- Audio files should be retained only for the current day, with cleanup based on local midnight at app startup.
- Logs should exist so future debugging can inspect what happened without relying on terminal copy/paste.
- Qwen cleanup must not convert Traditional Chinese speech/text to Simplified Chinese.
- Qwen cleanup should receive the focused app context in listener mode so style can adapt to the target app.
- Correction memory should be used by Qwen as the main repair layer; do not grow Faster Whisper hotwords into a dictionary.
- Faster Whisper should receive at most five short hotwords, each five Unicode characters or fewer.
- Tray mode should remain a wrapper around the existing listener core. Do not fork the dictation logic.
- Startup-at-login is currently implemented through a reversible Startup folder command file, not an installer.

## Useful Files

- `src/voicetype/cli.py` - command parsing, listener loop, session logging hookup
- `src/voicetype/audio.py` - recording, normalization, temp WAV cleanup
- `src/voicetype/output_audio.py` - Windows output mute guard and safe restore helpers
- `src/voicetype/active_window.py` - focused Windows app/window detection
- `src/voicetype/listener_runtime.py` - background runtime wrapper for listener mode
- `src/voicetype/startup.py` - Windows Startup folder entry management
- `src/voicetype/tray.py` - tray controller, menu actions, icon generation, and pystray entrypoint
- `src/voicetype/notifier.py` - console/toast/overlay notifications and overlay presentation rules
- `src/voicetype/session_log.py` - JSONL session log writer and record builder
- `src/voicetype/pipeline.py` - ASR, optional Qwen polish, paste orchestration
- `src/voicetype/memory.py` - local correction memory store, selector, and Whisper hotword filter
- `src/voicetype/qwen_client.py` - llama-server chat completions client and fail-open JSON parsing
- `src/voicetype/whisper_client.py` - Faster Whisper HTTP client
- `.env-example` - tracked template for local `VOICETYPE_*` settings
- `README.md` - user-facing setup and test instructions
- `docs/superpowers/specs/2026-05-15-voice-type-design.md` - original design spec
- `docs/superpowers/specs/2026-05-15-voice-type-tray-app-design.md` - Tray App v1 design
- `docs/superpowers/plans/2026-05-15-voice-type-mvp.md` - original implementation plan
- `docs/superpowers/specs/2026-05-19-voice-type-correction-memory-design.md` - Correction Memory v1 design
- `docs/superpowers/plans/2026-05-15-voice-type-tray-app.md` - Tray App v1 implementation plan
- `docs/superpowers/plans/2026-05-19-voice-type-correction-memory.md` - Correction Memory v1 implementation plan

## Suggested Next Steps

1. Manually validate tray icon right-click menu, `Show Latest Log`, Quit, and Right Ctrl dictation flow from `python -m voicetype tray`.
2. Add an optional setting for log retention or cleanup if JSONL grows too large.
3. Improve the Qwen prompt with explicit app-specific style hints now that app context and correction memory are available.
4. Add an integration smoke script that records a very short test WAV, transcribes it with `--no-paste --no-llm`, and prints the session log path.
5. Consider packaging or shortcut creation after tray mode has been manually exercised for a few sessions.

## Cautions

- Do not replace the current Qwen endpoint with `forge2`; the corrected host is `ai-srv.tail9d0481.ts.net`.
- Do not commit `.env`; keep local machine-specific settings in the ignored `.env` file.
- Do not send full correction memory, contact lists, project glossaries, or long terms to Faster Whisper.
- Do not change the idle microphone behavior without explicit approval.
- Do not mute output outside active recording, and do not overwrite a user's preexisting muted state.
- Do not make overlay diagnostic-heavy; keep diagnostics in terminal and logs.
- Avoid long-term WAV retention until the user explicitly asks for it, because the files can contain private speech.
- Do not replace the Startup folder approach with installer behavior until tray mode is stable.
