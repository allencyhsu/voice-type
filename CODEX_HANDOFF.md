# VoiceType Handoff

## Current State

- Repo: `git@github.com:allencyhsu/voice-type.git`
- Working branch: `feature/voice-type-mvp`
- Latest pushed commit: `d07ee14 feat: pass hotwords to Qwen polish`
- Workspace used in recent work: `C:\Users\Allen\Desktop\Projects\VoiceType\.worktrees\voice-type-mvp`
- Python environment: local `.venv`

The worktree was clean after the latest push.

## Service Endpoints

- Faster Whisper server: `http://forge2.tail9d0481.ts.net:8008`
- Faster Whisper model: `large-v2`
- Qwen llama-server OpenAI-compatible base URL: `http://ai-srv.tail9d0481.ts.net:8001/v1`
- Chat completions path: `/chat/completions`
- Qwen model setting: `qwen3.6-35b`

Important note: Whisper and Qwen are on different hosts. Do not mix the earlier `forge2` llama-server path with the current Qwen endpoint.

## Implemented Capabilities

- CLI package with `doctor`, `transcribe`, `record`, and `listen` commands.
- Right Ctrl toggles listener mode:
  - first press starts recording
  - second press stops recording, normalizes audio, transcribes, optionally polishes, and pastes through the clipboard
- Microphone is opened only during active recording. It is not kept open while idle.
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
- Session logs include start/end time, WAV path, audio duration, file bytes, normalization info, ASR status, raw/final text, paste flag, and ignored-recording reason.
- `--hotword` values are passed to both Whisper and Qwen polish payloads.
- Qwen polish fails open to raw Whisper text on server error, timeout, invalid JSON, or unusable response.

## Common Commands

Set up:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
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
python -m voicetype listen --hotword Typeless --hotword "Faster Whisper"
```

Check services:

```powershell
python -m voicetype doctor
```

Verification:

```powershell
python -m pytest -q
python -m compileall -q src tests
python -m voicetype listen --help
```

Last known verification:

```text
python -m pytest -q
41 passed

python -m compileall -q src tests
OK

python -m voicetype listen --help
OK
```

## Recent Commits

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
- About 0.2 seconds of microphone cold-start latency is acceptable.
- Toast notifications are less intuitive for this workflow; overlay is preferred.
- Overlay should be visually obvious, not plain black/white, and should sit above the Windows taskbar rather than at the top of the screen.
- `Captured...` and `Normalized audio...` are diagnostic and should stay out of the overlay.
- Audio files should be retained only for the current day, with cleanup based on local midnight at app startup.
- Logs should exist so future debugging can inspect what happened without relying on terminal copy/paste.

## Useful Files

- `src/voicetype/cli.py` - command parsing, listener loop, session logging hookup
- `src/voicetype/audio.py` - recording, normalization, temp WAV cleanup
- `src/voicetype/notifier.py` - console/toast/overlay notifications and overlay presentation rules
- `src/voicetype/session_log.py` - JSONL session log writer and record builder
- `src/voicetype/pipeline.py` - ASR, optional Qwen polish, paste orchestration
- `src/voicetype/qwen_client.py` - llama-server chat completions client and fail-open JSON parsing
- `src/voicetype/whisper_client.py` - Faster Whisper HTTP client
- `README.md` - user-facing setup and test instructions
- `docs/superpowers/specs/2026-05-15-voice-type-design.md` - original design spec
- `docs/superpowers/plans/2026-05-15-voice-type-mvp.md` - original implementation plan

## Suggested Next Steps

1. Add a lightweight manual diagnostics command for recent session logs, for example `python -m voicetype logs --today`.
2. Add an optional setting for log retention or cleanup if JSONL grows too large.
3. Improve app context detection so Qwen can tailor polish style based on the active app.
4. Consider a tray app wrapper after the CLI listener is stable.
5. Add an integration smoke script that records a very short test WAV, transcribes it with `--no-paste --no-llm`, and prints the session log path.

## Cautions

- Do not replace the current Qwen endpoint with `forge2`; the corrected host is `ai-srv.tail9d0481.ts.net`.
- Do not change the idle microphone behavior without explicit approval.
- Do not make overlay diagnostic-heavy; keep diagnostics in terminal and logs.
- Avoid long-term WAV retention until the user explicitly asks for it, because the files can contain private speech.
