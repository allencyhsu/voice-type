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

## Disable LLM Polish

```powershell
python -m voicetype record --seconds 8 --paste --no-llm
```
