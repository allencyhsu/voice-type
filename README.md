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

The terminal prints status messages:

```text
[VoiceType] Listening...
[VoiceType] Processing...
[VoiceType] Ignored short recording (0.31s < 0.70s).
[VoiceType] Inserted text.
```

Use this mode without paste when you only want to inspect the final text:

```powershell
python -m voicetype listen --no-paste
```

Use this mode to isolate microphone and Whisper behavior without Qwen or paste:

```powershell
python -m voicetype listen --no-paste --no-llm
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

## Disable LLM Polish

```powershell
python -m voicetype record --seconds 8 --paste --no-llm
```

The same flag works in listener mode:

```powershell
python -m voicetype listen --no-llm
```
