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

The terminal prints status messages:

```text
[VoiceType] Listening...
[VoiceType] Processing...
[VoiceType] Inserted text.
```

Use this mode without paste when you only want to inspect the final text:

```powershell
python -m voicetype listen --no-paste
```

## Disable LLM Polish

```powershell
python -m voicetype record --seconds 8 --paste --no-llm
```

The same flag works in listener mode:

```powershell
python -m voicetype listen --no-llm
```
