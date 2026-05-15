# VoiceType MVP Design Spec

## Summary

VoiceType is a Windows voice typing prototype. The first version is a tray-friendly local Windows client that records short speech, sends the audio to an existing Faster Whisper server, optionally sends the transcript to an existing Qwen llama-server endpoint for cleanup, and inserts the final text into the currently focused application.

The MVP intentionally avoids writing a Windows IME, kernel driver, or always-listening agent. It uses application-level Windows APIs, a conservative clipboard paste path, and fail-open behavior when the LLM is unavailable.

## Goals

- Capture speech on demand from a Windows hotkey or CLI-triggered session.
- Send captured audio to `http://forge2.tail9d0481.ts.net:8008/transcribe`.
- Use the same Faster Whisper request shape as `u:\Projects\podcast-etl\fwhisper_meeting.py`.
- Use model `large-v2` on the Faster Whisper server.
- Optionally polish the raw transcript through Qwen 3.6 via llama-server at `http://forge2.tail9d0481.ts.net:8001`.
- Insert the final text into the active Windows app.
- Keep the ASR-only path usable when the Qwen endpoint is unavailable.
- Keep all project configuration explicit and easy to override with environment variables.

## Non-Goals

- No custom Windows IME.
- No keyboard driver, input filter driver, or elevated system service.
- No always-on background recording in the MVP.
- No real-time partial transcript insertion into target apps.
- No cloud API dependency.
- No multi-user sync, account system, or hosted backend.

## Target User Flow

1. User places the cursor in any text field.
2. User starts a dictation session.
3. VoiceType records audio into a temporary WAV file.
4. VoiceType uploads the WAV file to the Faster Whisper server.
5. VoiceType concatenates returned segments into raw transcript text.
6. VoiceType sends raw text to Qwen for cleanup if the LLM endpoint is available and polish mode is enabled.
7. VoiceType pastes the final text into the focused application.
8. VoiceType shows useful status and error messages in logs or an overlay.

## System Architecture

```text
Windows client
  Settings
  AudioRecorder
  WhisperClient
  QwenClient
  TextInjector
  DictationPipeline

Remote inference services
  Faster Whisper server
    GET  /health
    POST /transcribe

  Qwen llama-server
    GET  /v1/models
    POST /v1/chat/completions
```

The Windows client owns interaction, audio capture, retries, fallbacks, and text insertion. The remote services own transcription and language cleanup.

## Recommended MVP Technology

The first implementation should be a Python prototype. This keeps the feedback loop short and matches the existing Faster Whisper client script style.

Recommended packages:

- `requests` for HTTP.
- `sounddevice` and `soundfile` for recording WAV files.
- `pyperclip` for clipboard insertion.
- `pyautogui` for paste hotkey fallback.
- `pydantic-settings` for environment-based settings.
- `pytest` and `responses` or `requests-mock` for tests.

A later productized version can move the shell to Tauri/Rust or .NET while keeping the ASR and Qwen HTTP contracts unchanged.

## Faster Whisper Contract

Health check:

```http
GET http://forge2.tail9d0481.ts.net:8008/health
```

Expected healthy response:

```json
{
  "status": "healthy",
  "model": "large-v2"
}
```

Transcription:

```http
POST http://forge2.tail9d0481.ts.net:8008/transcribe
Content-Type: multipart/form-data
```

Multipart file field:

```text
file = recorded WAV file
```

Form fields:

```python
{
    "initial_prompt": INITIAL_PROMPT,
    "hotwords": ", ".join(hotwords),
    "temperature": 0.0,
    "beam_size": 5,
    "best_of": 5,
    "repetition_penalty": 1.1,
    "no_repeat_ngram_size": 3,
    "condition_on_previous_text": False,
    "vad_filter": True,
    "min_silence_duration_ms": 500,
    "min_speech_duration_ms": 100,
    "max_speech_duration_s": 30.0,
    "speech_pad_ms": 500,
    "vad_threshold": 0.5,
    "no_speech_threshold": 0.8,
    "log_prob_threshold": -1.0,
    "compression_ratio_threshold": 2.4,
}
```

Expected response shape:

```json
{
  "success": true,
  "segments": [
    {"start": 0.0, "end": 1.25, "text": "recognized text"}
  ],
  "language": "zh",
  "language_probability": 0.99,
  "duration": 1.25,
  "transcribe_time": 0.42
}
```

If `success` is false, VoiceType must treat transcription as failed and must not paste empty text.

## Qwen llama-server Contract

Base URL:

```text
http://forge2.tail9d0481.ts.net:8001
```

Primary endpoint:

```http
POST /v1/chat/completions
```

Model setting:

```text
qwen3.6-35b
```

The Qwen path must be optional. If the server is unavailable, returns an error, times out, or returns invalid JSON, VoiceType must paste the raw Whisper transcript when transcript text exists.

Recommended request:

```json
{
  "model": "qwen3.6-35b",
  "temperature": 0.1,
  "messages": [
    {
      "role": "system",
      "content": "You are a local dictation cleanup engine. Return only JSON."
    },
    {
      "role": "user",
      "content": "{\"app\":\"Notepad\",\"mode\":\"dictation\",\"raw_transcript\":\"recognized text\"}"
    }
  ]
}
```

Recommended model output:

```json
{"action":"insert","text":"final text"}
```

If the model returns non-JSON text, the client may extract the first JSON object. If extraction fails, the client must use the raw transcript.

## Prompt Rules

The Qwen prompt must enforce these rules:

- Preserve the user's intended meaning.
- Do not add facts.
- Remove filler words, repeated starts, and explicit self-corrections.
- Preserve mixed Chinese and English.
- Preserve technical terms and configured hotwords.
- Match the target application tone when app context is available.
- Return only JSON with `action` and `text`.

## Configuration

Environment variables:

```text
VOICETYPE_WHISPER_URL=http://forge2.tail9d0481.ts.net:8008
VOICETYPE_LLM_BASE_URL=http://forge2.tail9d0481.ts.net:8001/v1
VOICETYPE_LLM_MODEL=qwen3.6-35b
VOICETYPE_ASR_TIMEOUT_SEC=120
VOICETYPE_LLM_TIMEOUT_SEC=20
VOICETYPE_ENABLE_LLM=true
VOICETYPE_SAMPLE_RATE=16000
VOICETYPE_CHANNELS=1
```

## Error Handling

- Whisper health failure: show or log an error and do not start transcription.
- Whisper request failure: keep the recording path for debugging and do not paste.
- Whisper success with no text: do not paste.
- Qwen failure: paste raw Whisper text if available.
- Clipboard failure: log error and attempt keyboard typing fallback only for short text.
- Target application blocks paste: leave the final text in clipboard and report that paste failed.

## Security and Privacy

The MVP sends audio and transcript text to services on the user's Tailscale network. It should not send data to external cloud APIs. Temporary audio files should be stored in the OS temp directory and deleted by default after successful insertion unless debug retention is enabled.

## Testing Strategy

- Unit test settings defaults and environment overrides.
- Unit test Whisper request form data and response parsing.
- Unit test Qwen prompt and fail-open behavior.
- Unit test transcript concatenation.
- Unit test text injection calls through mocked clipboard and keyboard APIs.
- Add one manual integration script that records or uploads a small WAV file to the real Whisper server.

## MVP Acceptance Criteria

- `python -m pytest` passes.
- `python -m voicetype doctor` confirms the Faster Whisper server is healthy and reports model `large-v2`.
- `python -m voicetype transcribe path\to\sample.wav` prints a non-empty transcript for valid speech audio.
- With Qwen unavailable, `python -m voicetype transcribe path\to\sample.wav --paste` still inserts raw transcript text.
- With Qwen available, polish mode returns JSON and inserts the `text` value.
- No empty text is pasted after a failed ASR response.
