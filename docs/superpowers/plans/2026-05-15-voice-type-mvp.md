# VoiceType MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python Windows voice typing MVP that records or accepts audio, transcribes through the existing Faster Whisper server, optionally polishes through Qwen llama-server, and pastes the final text into the active app.

**Architecture:** The MVP is a Python package with focused modules for settings, ASR HTTP, LLM HTTP, audio recording, text injection, and pipeline orchestration. The Qwen path is fail-open: ASR-only dictation remains usable when the LLM endpoint is offline.

**Tech Stack:** Python 3.11+, `requests`, `pydantic-settings`, `sounddevice`, `soundfile`, `pyperclip`, `pyautogui`, `pytest`, `responses`.

---

## File Structure

- Create: `pyproject.toml` - package metadata, dependencies, pytest config.
- Create: `.gitignore` - Python, temp audio, and editor ignores.
- Create: `src/voicetype/__init__.py` - package marker.
- Create: `src/voicetype/settings.py` - environment-based settings.
- Create: `src/voicetype/whisper_client.py` - Faster Whisper health and transcription API client.
- Create: `src/voicetype/qwen_client.py` - llama-server OpenAI-compatible chat client and JSON parsing.
- Create: `src/voicetype/audio.py` - WAV recording helper.
- Create: `src/voicetype/injector.py` - clipboard paste and typing fallback.
- Create: `src/voicetype/pipeline.py` - dictation orchestration.
- Create: `src/voicetype/cli.py` - command line entrypoint.
- Create: `tests/test_settings.py` - settings tests.
- Create: `tests/test_whisper_client.py` - ASR request and parsing tests.
- Create: `tests/test_qwen_client.py` - LLM success and fail-open tests.
- Create: `tests/test_pipeline.py` - orchestration tests.

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/voicetype/__init__.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Create package metadata**

Create `pyproject.toml`:

```toml
[project]
name = "voice-type"
version = "0.1.0"
description = "Windows voice typing prototype using remote Faster Whisper and Qwen endpoints."
requires-python = ">=3.11"
dependencies = [
    "pydantic-settings>=2.2",
    "requests>=2.32",
    "sounddevice>=0.4.7",
    "soundfile>=0.12.1",
    "pyperclip>=1.8.2",
    "pyautogui>=0.9.54",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "responses>=0.25",
]

[project.scripts]
voicetype = "voicetype.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create ignore file**

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.env
*.wav
*.mp3
*.m4a
dist/
build/
*.egg-info/
```

- [ ] **Step 3: Create package marker**

Create `src/voicetype/__init__.py`:

```python
"""VoiceType Windows voice typing prototype."""
```

- [ ] **Step 4: Write the first failing settings test**

Create `tests/test_settings.py`:

```python
from voicetype.settings import Settings


def test_default_settings_match_voice_type_services():
    settings = Settings()

    assert settings.whisper_url == "http://forge2.tail9d0481.ts.net:8008"
    assert settings.llm_base_url == "http://forge2.tail9d0481.ts.net:8001/v1"
    assert settings.llm_model == "qwen3.6-35b"
    assert settings.enable_llm is True
    assert settings.sample_rate == 16000
    assert settings.channels == 1
```

- [ ] **Step 5: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_settings.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'voicetype.settings'`.

- [ ] **Step 6: Commit scaffold files**

Run:

```powershell
git add pyproject.toml .gitignore src/voicetype/__init__.py tests/test_settings.py
git commit -m "chore: scaffold Python package"
```

---

### Task 2: Settings Module

**Files:**
- Create: `src/voicetype/settings.py`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Implement settings**

Create `src/voicetype/settings.py`:

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOICETYPE_", env_file=".env")

    whisper_url: str = "http://forge2.tail9d0481.ts.net:8008"
    llm_base_url: str = "http://forge2.tail9d0481.ts.net:8001/v1"
    llm_model: str = "qwen3.6-35b"
    asr_timeout_sec: int = 120
    llm_timeout_sec: int = 20
    enable_llm: bool = True
    sample_rate: int = 16000
    channels: int = 1
    record_seconds: float = Field(default=8.0, gt=0)
```

- [ ] **Step 2: Add environment override test**

Append to `tests/test_settings.py`:

```python
def test_settings_read_environment_overrides(monkeypatch):
    monkeypatch.setenv("VOICETYPE_ENABLE_LLM", "false")
    monkeypatch.setenv("VOICETYPE_LLM_MODEL", "custom-model")

    settings = Settings()

    assert settings.enable_llm is False
    assert settings.llm_model == "custom-model"
```

- [ ] **Step 3: Run settings tests**

Run:

```powershell
python -m pytest tests/test_settings.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit settings**

Run:

```powershell
git add src/voicetype/settings.py tests/test_settings.py
git commit -m "feat: add environment settings"
```

---

### Task 3: Faster Whisper Client

**Files:**
- Create: `src/voicetype/whisper_client.py`
- Create: `tests/test_whisper_client.py`

- [ ] **Step 1: Write failing tests for health and transcription**

Create `tests/test_whisper_client.py`:

```python
from pathlib import Path

import responses

from voicetype.whisper_client import WhisperClient, TranscriptionSegment


@responses.activate
def test_health_returns_server_json():
    responses.get(
        "http://example.test/health",
        json={"status": "healthy", "model": "large-v2"},
        status=200,
    )

    client = WhisperClient("http://example.test", timeout_sec=5)

    assert client.health() == {"status": "healthy", "model": "large-v2"}


@responses.activate
def test_transcribe_posts_audio_and_parses_segments(tmp_path):
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"fake wav")
    responses.post(
        "http://example.test/transcribe",
        json={
            "success": True,
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "hello"},
                {"start": 1.0, "end": 2.0, "text": " world"},
            ],
            "language": "en",
            "language_probability": 0.99,
            "duration": 2.0,
            "transcribe_time": 0.5,
        },
        status=200,
    )

    client = WhisperClient("http://example.test", timeout_sec=5)
    result = client.transcribe(wav_path, initial_prompt="prompt", hotwords=["Qwen"])

    assert result.success is True
    assert result.text == "hello world"
    assert result.segments == [
        TranscriptionSegment(start=0.0, end=1.0, text="hello"),
        TranscriptionSegment(start=1.0, end=2.0, text=" world"),
    ]
    request = responses.calls[0].request
    assert request.url == "http://example.test/transcribe"
    assert b'name="hotwords"' in request.body
    assert b"Qwen" in request.body
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_whisper_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'voicetype.whisper_client'`.

- [ ] **Step 3: Implement Whisper client**

Create `src/voicetype/whisper_client.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


@dataclass(frozen=True)
class TranscriptionSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    success: bool
    segments: list[TranscriptionSegment]
    language: str | None = None
    language_probability: float | None = None
    duration: float | None = None
    transcribe_time: float | None = None
    error: str | None = None

    @property
    def text(self) -> str:
        return "".join(segment.text for segment in self.segments).strip()


class WhisperClient:
    def __init__(self, base_url: str, timeout_sec: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def health(self) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/health", timeout=5)
        response.raise_for_status()
        return response.json()

    def transcribe(
        self,
        file_path: str | Path,
        *,
        initial_prompt: str = "",
        hotwords: list[str] | None = None,
    ) -> TranscriptionResult:
        path = Path(file_path)
        data = {
            "initial_prompt": initial_prompt,
            "hotwords": ", ".join(hotwords or []),
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

        with path.open("rb") as audio_file:
            files = {"file": (path.name, audio_file)}
            response = requests.post(
                f"{self.base_url}/transcribe",
                files=files,
                data=data,
                timeout=self.timeout_sec,
            )
        response.raise_for_status()
        payload = response.json()
        segments = [
            TranscriptionSegment(
                start=float(segment["start"]),
                end=float(segment["end"]),
                text=str(segment["text"]),
            )
            for segment in payload.get("segments", [])
        ]
        return TranscriptionResult(
            success=bool(payload.get("success")),
            segments=segments,
            language=payload.get("language"),
            language_probability=payload.get("language_probability"),
            duration=payload.get("duration"),
            transcribe_time=payload.get("transcribe_time"),
            error=payload.get("error"),
        )
```

- [ ] **Step 4: Run Whisper tests**

Run:

```powershell
python -m pytest tests/test_whisper_client.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit Whisper client**

Run:

```powershell
git add src/voicetype/whisper_client.py tests/test_whisper_client.py
git commit -m "feat: add Faster Whisper client"
```

---

### Task 4: Qwen Client with Fail-Open Parsing

**Files:**
- Create: `src/voicetype/qwen_client.py`
- Create: `tests/test_qwen_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_qwen_client.py`:

```python
import responses

from voicetype.qwen_client import QwenClient


@responses.activate
def test_polish_returns_text_from_json_response():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"action":"insert","text":"Clean final text."}'
                    }
                }
            ]
        },
        status=200,
    )

    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    assert client.polish("clean final text", app_name="Notepad") == "Clean final text."


@responses.activate
def test_polish_fails_open_to_raw_text_on_server_error():
    responses.post("http://example.test/v1/chat/completions", status=500)
    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    assert client.polish("raw text", app_name="Notepad") == "raw text"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_qwen_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'voicetype.qwen_client'`.

- [ ] **Step 3: Implement Qwen client**

Create `src/voicetype/qwen_client.py`:

```python
import json
import re
from typing import Any

import requests


SYSTEM_PROMPT = """You are a local dictation cleanup engine. Return only JSON.
Rules:
- Preserve the user's intended meaning.
- Do not add facts.
- Remove filler words, repeated starts, and explicit self-corrections.
- Preserve mixed Chinese and English.
- Preserve technical terms and configured hotwords.
- Match the target application tone when app context is available.
- Return only JSON with action and text."""


class QwenClient:
    def __init__(self, base_url: str, model: str, timeout_sec: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec

    def health(self) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/models", timeout=5)
        response.raise_for_status()
        return response.json()

    def polish(self, raw_text: str, *, app_name: str | None = None) -> str:
        if not raw_text.strip():
            return raw_text

        user_payload = {
            "app": app_name or "unknown",
            "mode": "dictation",
            "raw_transcript": raw_text,
        }
        request_body = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=request_body,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = _parse_json_object(content)
            text = parsed.get("text")
            return text if isinstance(text, str) and text.strip() else raw_text
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            return raw_text


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response")
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON was not an object")
    return parsed
```

- [ ] **Step 4: Run Qwen tests**

Run:

```powershell
python -m pytest tests/test_qwen_client.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit Qwen client**

Run:

```powershell
git add src/voicetype/qwen_client.py tests/test_qwen_client.py
git commit -m "feat: add Qwen polish client"
```

---

### Task 5: Pipeline and CLI

**Files:**
- Create: `src/voicetype/pipeline.py`
- Create: `src/voicetype/cli.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests**

Create `tests/test_pipeline.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from voicetype.pipeline import DictationPipeline
from voicetype.whisper_client import TranscriptionResult, TranscriptionSegment


@dataclass
class FakeWhisper:
    result: TranscriptionResult

    def transcribe(self, path: Path, *, initial_prompt: str, hotwords: list[str]):
        return self.result


class FakeQwen:
    def polish(self, raw_text: str, *, app_name: str | None = None) -> str:
        return f"polished: {raw_text}"


class FakeInjector:
    def __init__(self):
        self.text = None

    def paste(self, text: str) -> None:
        self.text = text


def test_pipeline_pastes_polished_text_when_llm_enabled(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    injector = FakeInjector()
    whisper = FakeWhisper(
        TranscriptionResult(
            success=True,
            segments=[TranscriptionSegment(0.0, 1.0, "hello")],
        )
    )

    pipeline = DictationPipeline(whisper, FakeQwen(), injector, enable_llm=True)
    result = pipeline.process_file(audio_path, app_name="Notepad")

    assert result == "polished: hello"
    assert injector.text == "polished: hello"


def test_pipeline_does_not_paste_on_failed_asr(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    injector = FakeInjector()
    whisper = FakeWhisper(TranscriptionResult(success=False, segments=[]))

    pipeline = DictationPipeline(whisper, FakeQwen(), injector, enable_llm=True)
    result = pipeline.process_file(audio_path)

    assert result == ""
    assert injector.text is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_pipeline.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'voicetype.pipeline'`.

- [ ] **Step 3: Implement pipeline**

Create `src/voicetype/pipeline.py`:

```python
from pathlib import Path
from typing import Protocol


class WhisperLike(Protocol):
    def transcribe(self, path: Path, *, initial_prompt: str, hotwords: list[str]):
        raise NotImplementedError


class QwenLike(Protocol):
    def polish(self, raw_text: str, *, app_name: str | None = None) -> str:
        raise NotImplementedError


class InjectorLike(Protocol):
    def paste(self, text: str) -> None:
        raise NotImplementedError


class DictationPipeline:
    def __init__(
        self,
        whisper: WhisperLike,
        qwen: QwenLike | None,
        injector: InjectorLike,
        *,
        enable_llm: bool,
    ) -> None:
        self.whisper = whisper
        self.qwen = qwen
        self.injector = injector
        self.enable_llm = enable_llm

    def process_file(
        self,
        audio_path: str | Path,
        *,
        app_name: str | None = None,
        initial_prompt: str = "",
        hotwords: list[str] | None = None,
        paste: bool = True,
    ) -> str:
        result = self.whisper.transcribe(
            Path(audio_path),
            initial_prompt=initial_prompt,
            hotwords=hotwords or [],
        )
        raw_text = result.text if result.success else ""
        if not raw_text:
            return ""

        final_text = raw_text
        if self.enable_llm and self.qwen is not None:
            final_text = self.qwen.polish(raw_text, app_name=app_name)

        if paste and final_text.strip():
            self.injector.paste(final_text)
        return final_text
```

- [ ] **Step 4: Implement CLI**

Create `src/voicetype/cli.py`:

```python
import argparse
from pathlib import Path

from voicetype.injector import TextInjector
from voicetype.pipeline import DictationPipeline
from voicetype.qwen_client import QwenClient
from voicetype.settings import Settings
from voicetype.whisper_client import WhisperClient


def main() -> None:
    parser = argparse.ArgumentParser(description="VoiceType dictation client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.set_defaults(command="doctor")

    transcribe_parser = subparsers.add_parser("transcribe")
    transcribe_parser.add_argument("audio_file", type=Path)
    transcribe_parser.add_argument("--paste", action="store_true")
    transcribe_parser.add_argument("--no-llm", action="store_true")
    transcribe_parser.add_argument("--hotword", action="append", default=[])

    args = parser.parse_args()
    settings = Settings()
    whisper = WhisperClient(settings.whisper_url, timeout_sec=settings.asr_timeout_sec)

    if args.command == "doctor":
        print(whisper.health())
        qwen = QwenClient(settings.llm_base_url, settings.llm_model, settings.llm_timeout_sec)
        try:
            print(qwen.health())
        except Exception as exc:
            print(f"LLM unavailable: {exc}")
        return

    qwen = None
    enable_llm = settings.enable_llm and not args.no_llm
    if enable_llm:
        qwen = QwenClient(settings.llm_base_url, settings.llm_model, settings.llm_timeout_sec)

    pipeline = DictationPipeline(
        whisper,
        qwen,
        TextInjector(),
        enable_llm=enable_llm,
    )
    final_text = pipeline.process_file(
        args.audio_file,
        hotwords=args.hotword,
        paste=args.paste,
    )
    print(final_text)
```

- [ ] **Step 5: Run pipeline tests**

Run:

```powershell
python -m pytest tests/test_pipeline.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit pipeline and CLI**

Run:

```powershell
git add src/voicetype/pipeline.py src/voicetype/cli.py tests/test_pipeline.py
git commit -m "feat: add dictation pipeline and CLI"
```

---

### Task 6: Audio Recording and Text Injection

**Files:**
- Create: `src/voicetype/audio.py`
- Create: `src/voicetype/injector.py`
- Modify: `src/voicetype/cli.py`

- [ ] **Step 1: Create audio recorder**

Create `src/voicetype/audio.py`:

```python
from pathlib import Path
import tempfile

import sounddevice as sd
import soundfile as sf


def record_wav(seconds: float, *, sample_rate: int, channels: int) -> Path:
    frames = int(seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="float32")
    sd.wait()
    temp = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=".wav", delete=False)
    temp.close()
    path = Path(temp.name)
    sf.write(path, recording, sample_rate)
    return path
```

- [ ] **Step 2: Create text injector**

Create `src/voicetype/injector.py`:

```python
import time

import pyautogui
import pyperclip


class TextInjector:
    def paste(self, text: str) -> None:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
```

- [ ] **Step 3: Add record command to CLI**

Modify `src/voicetype/cli.py` by adding this parser after the `transcribe` parser:

```python
    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--seconds", type=float, default=None)
    record_parser.add_argument("--paste", action="store_true")
    record_parser.add_argument("--no-llm", action="store_true")
    record_parser.add_argument("--hotword", action="append", default=[])
```

Add this import near the top:

```python
from voicetype.audio import record_wav
```

Add this command branch before creating the final pipeline input:

```python
    audio_file = getattr(args, "audio_file", None)
    if args.command == "record":
        audio_file = record_wav(
            args.seconds or settings.record_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
        )
```

Replace the final `pipeline.process_file(args.audio_file, hotwords=args.hotword, paste=args.paste)` call with:

```python
    final_text = pipeline.process_file(
        audio_file,
        hotwords=args.hotword,
        paste=args.paste,
    )
```

- [ ] **Step 4: Run all tests**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Manual doctor check**

Run:

```powershell
python -m voicetype doctor
```

Expected:

```text
{'status': 'healthy', 'model': 'large-v2'}
LLM unavailable: connection to http://forge2.tail9d0481.ts.net:8001/v1/models failed
```

The exact exception text may vary. The acceptable result is that the command prints the Whisper health response and then either prints Qwen model information or a single `LLM unavailable:` line.

- [ ] **Step 6: Commit audio and injection**

Run:

```powershell
git add src/voicetype/audio.py src/voicetype/injector.py src/voicetype/cli.py
git commit -m "feat: add recording and paste injection"
```

---

### Task 7: README Usage Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README with MVP usage**

Replace `README.md`:

````markdown
# VoiceType

Windows voice typing prototype using a remote Faster Whisper transcription server and a remote Qwen/llama-server polishing endpoint.

## Services

- Faster Whisper: `http://forge2.tail9d0481.ts.net:8008`
- Faster Whisper model: `large-v2`
- Qwen llama-server: `http://forge2.tail9d0481.ts.net:8001`
- Qwen OpenAI-compatible base URL: `http://forge2.tail9d0481.ts.net:8001/v1`

## Setup

```powershell
python -m venv .venv
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
````

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit docs**

Run:

```powershell
git add README.md
git commit -m "docs: add MVP usage"
```

---

## Self-Review

Spec coverage:

- Faster Whisper endpoint and request shape are covered by Task 3.
- Qwen llama-server OpenAI-compatible endpoint and fail-open behavior are covered by Task 4.
- ASR-only fallback is covered by Task 4 and Task 5 tests.
- Recording and text insertion are covered by Task 6.
- CLI verification and README usage are covered by Task 6 and Task 7.

Placeholder scan:

- No prohibited placeholder phrases or unspecified test steps remain.

Type consistency:

- `WhisperClient.transcribe()`, `QwenClient.polish()`, `TextInjector.paste()`, and `DictationPipeline.process_file()` signatures are consistent across tasks and tests.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-15-voice-type-mvp.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
