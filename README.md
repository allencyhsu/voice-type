# VoiceType

Windows voice typing prototype using a remote Faster Whisper transcription server and a remote Qwen/llama-server polishing endpoint.

## Services

- Faster Whisper: `http://forge2.tail9d0481.ts.net:8008`
- Faster Whisper model: `large-v2`
- Qwen llama-server: `http://ai-srv.tail9d0481.ts.net:8001`
- Qwen OpenAI-compatible base URL: `http://ai-srv.tail9d0481.ts.net:8001/v1`

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If `python` points to the Windows Store stub, use the Python launcher:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Verify Services

```powershell
python -m voicetype doctor
```

## Transcribe Existing Audio

```powershell
python -m voicetype transcribe path\to\sample.wav
```

## Record and Paste

```powershell
python -m voicetype record --seconds 8 --paste
```

## Toggle Listening with Right Ctrl

Start the listener:

```powershell
python -m voicetype listen
```

## Tray Mode

Start VoiceType in the Windows system tray:

```powershell
python -m voicetype tray
```

Tray mode keeps the existing right Ctrl listener and overlay behavior. The microphone is still opened only while actively recording.

For no-console startup, create a shortcut or startup entry that runs:

```powershell
.\.venv\Scripts\pythonw.exe -m voicetype tray
```

The tray menu includes live status, Show Latest Log, Open Logs, startup-at-login, and quit actions. Quit stops the background listener before closing the tray icon.

Manual test flow:

1. Open Notepad or another text input.
2. Put the caret in the input field.
3. Leave the VoiceType terminal running in the background or on another monitor.
4. Press the right Ctrl key once to start listening.
5. Speak.
6. Press the right Ctrl key again to stop listening.
7. VoiceType transcribes, optionally polishes with Qwen, and pastes through the clipboard into the focused input.

Short accidental taps are ignored by default. A recording must be at least 0.7 seconds before VoiceType sends it to Whisper. Override this threshold with:

```powershell
python -m voicetype listen --min-seconds 1.0
```

Status notifications default to a vivid top-most overlay above the Windows taskbar:

```powershell
python -m voicetype listen
```

When you press right Ctrl to start recording, the overlay stays visible as a listening reminder until you press right Ctrl again. After you stop recording, it switches to the processing status and then hides automatically.

Use terminal-only status messages with:

```powershell
python -m voicetype listen --notify console
```

Use Windows toast notifications with:

```powershell
python -m voicetype listen --notify toast
```

Disable status notifications with:

```powershell
python -m voicetype listen --notify off
```

The terminal prints status messages:

```text
[VoiceType] Listening...
[VoiceType] Processing...
[VoiceType] Captured 4.50s, 143980 bytes: C:\Users\...\voicetype-abc.wav
[VoiceType] Normalized audio gain=50.0x peak=0.0106->0.5310
[VoiceType] Ignored short recording (0.31s < 0.70s).
[VoiceType] Inserted text.
```

The overlay only shows user-facing states such as `Listening...`, `Processing...`, `Inserted text.`, `No text recognized.`, and ignored short recordings. Diagnostic details such as captured file path and normalization gain stay in the terminal and session log.

Use this mode without paste when you only want to inspect the final text:

```powershell
python -m voicetype listen --no-paste
```

Use this mode to isolate microphone and Whisper behavior without Qwen or paste:

```powershell
python -m voicetype listen --no-paste --no-llm
```

Use hotwords sparingly for short product names, tools, people, or domain terms that Whisper and Qwen should preserve:

```powershell
python -m voicetype listen --hotword Qwen --hotword Allen
```

Faster Whisper receives at most five hotwords, and each hotword must be five Unicode characters or fewer. Longer terms and phrase corrections should go into correction memory so Qwen can apply them after ASR.

VoiceType treats Faster Whisper `hotwords` as a small prompt hint, not as an unlimited dictionary. Faster Whisper encodes hotwords into the Whisper decoder prompt, so long lists compete with `initial_prompt`, prior text context, and generated output space.

For development, keep `initial_prompt` plus `hotwords` bounded and prefer a deduped priority shortlist for the current dictation context. Target roughly 150-200 Whisper tokens, or use the conservative client fallback when the Whisper tokenizer is not available.

Qwen polish is instructed to output Chinese text in Traditional Chinese. Simplified Chinese characters should be converted to Traditional Chinese, while English technical terms, filenames, product names, and menu item names should remain in their original language.

The built-in polish prompt also includes a small set of common VoiceType correction rules observed from session logs, such as `.env`, `TTS Cache`, `LLM`, `TTS`, `Whisper`, `hotword`, `ONNX`, `瀏覽`, `回覆`, and `Codex-Handoff.md`. Longer or project-specific corrections should still go into correction memory instead of Faster Whisper hotwords.

In listener mode, VoiceType also detects the currently focused Windows app and passes the app name to Qwen so the polish step can account for the target writing context.

## Correction Memory

VoiceType uses Qwen, not Faster Whisper, as the main correction layer. Faster Whisper receives only a tiny hotword hint list. Longer vocabulary and phrase corrections are stored locally and sent only to Qwen when relevant.

Correction memory is stored at:

```text
%LOCALAPPDATA%\VoiceType\memory\corrections.jsonl
```

Add corrections:

```powershell
python -m voicetype memory add --type term --wrong "cue and" --correct "Qwen"
python -m voicetype memory add --type phrase --wrong "重新開幾" --correct "重新開機"
```

List or remove corrections:

```powershell
python -m voicetype memory list
python -m voicetype memory remove <id>
```

Learn a conservative phrase correction from the latest session log:

```powershell
python -m voicetype memory learn --from-last --corrected "corrected final text"
```

If VoiceType prints `No text recognized`, check the diagnostic line before it:

```text
[VoiceType] Captured 0.12s, 44 bytes: C:\Users\...\voicetype-abc.wav
[VoiceType] No text recognized. status=empty_transcript
```

- Very short duration or a tiny WAV file means the recording toggle happened too quickly or no microphone samples arrived.
- `status=empty_transcript` means Whisper accepted the request but returned no segments.
- `status=asr_failed` means the Whisper API returned a failed transcription response.
- `error=...` shows the Whisper server error when it provides one.

## Temporary Audio Retention

VoiceType writes recorded WAV files to the Windows temp directory with names like:

```text
C:\Users\Allen\AppData\Local\Temp\voicetype-xxxx.wav
```

These files are kept for the current calendar day. Each time VoiceType starts, it removes `voicetype-*.wav` files whose modified time is earlier than local midnight for the current day. For example, when VoiceType starts on May 15 at 09:00, files from before May 15 00:00 are deleted, while files recorded after May 15 00:00 are retained.

## Session Logs

Each listener segment writes one JSONL record to:

```text
%LOCALAPPDATA%\VoiceType\logs\YYYY-MM-DD.jsonl
```

The log includes the segment start/end time, focused app name, WAV path, duration, byte size, normalization details, Whisper status, recognized text, final text, and whether text was pasted. Short ignored recordings are logged too, with an `ignored_reason`.

Show recent records from today's log:

```powershell
python -m voicetype logs --today
```

Limit the summary:

```powershell
python -m voicetype logs --today --limit 5
```

Print recent records as JSONL for debugging:

```powershell
python -m voicetype logs --today --limit 5 --json
```

Show only the newest record:

```powershell
python -m voicetype logs --last
python -m voicetype logs --last --json
```

Open the log directory:

```powershell
python -m voicetype logs --open-dir
```

## Disable LLM Polish

```powershell
python -m voicetype record --seconds 8 --paste --no-llm
```

The same flag works in listener mode:

```powershell
python -m voicetype listen --no-llm
```
