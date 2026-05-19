# VoiceType Correction Memory v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local correction memory for confirmed terms and common ASR phrase mistakes, using Qwen as the main correction layer while keeping Faster Whisper hotwords capped to 5 entries of 5 characters each.

**Architecture:** Add a focused `memory.py` module for JSONL persistence, entry validation, selection, and Whisper hotword filtering. Extend `QwenClient` and `DictationPipeline` to carry selected correction memory through the polish request and into session logs. Add a `memory` CLI command group for add/list/remove/learn workflows.

**Tech Stack:** Python 3.11+, dataclasses, JSONL, pathlib, argparse, existing requests/Qwen/Faster Whisper stack, pytest, responses.

---

## File Structure

- Create: `src/voicetype/memory.py` - correction entry dataclass, JSONL store, selector, and Whisper hotword filtering.
- Create: `tests/test_memory.py` - memory store, retrieval, Unicode, malformed-row, and hotword-filter tests.
- Modify: `src/voicetype/whisper_client.py` - call the 5-by-5 hotword filter before POSTing multipart data.
- Modify: `tests/test_whisper_client.py` - assert hotword filtering at the HTTP boundary.
- Modify: `src/voicetype/qwen_client.py` - accept selected correction memory and include it in Qwen user payload.
- Modify: `tests/test_qwen_client.py` - assert correction memory appears in payload and fail-open behavior remains.
- Modify: `src/voicetype/pipeline.py` - retrieve memory, pass it to Qwen, add metadata to `PipelineResult`.
- Modify: `tests/test_pipeline.py` - assert memory selection, Qwen handoff, and fail-open behavior.
- Modify: `src/voicetype/session_log.py` - log memory and Whisper hotword metadata.
- Modify: `tests/test_session_log.py` - assert new log fields.
- Modify: `src/voicetype/cli.py` - add `memory` command group and wire memory store into dictation commands.
- Modify: `tests/test_cli_entrypoint.py` - add CLI parsing/dispatch tests for memory commands.
- Modify: `README.md` and `CODEX_HANDOFF.md` - document correction memory and hotword policy.

---

### Task 1: Correction Memory Store

**Files:**
- Create: `src/voicetype/memory.py`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write failing tests for the memory store**

Create `tests/test_memory.py`:

```python
import json
from datetime import datetime

from voicetype.memory import (
    CorrectionEntry,
    CorrectionMemoryStore,
    CorrectionType,
    default_memory_path,
    select_relevant_corrections,
)


def test_default_memory_path_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_memory_path() == tmp_path / "VoiceType" / "memory" / "corrections.jsonl"


def test_store_appends_and_loads_unicode_entries(tmp_path):
    store = CorrectionMemoryStore(tmp_path / "corrections.jsonl")

    entry = store.add(
        CorrectionType.PHRASE,
        wrong="重新開幾",
        correct="重新開機",
        now=lambda: datetime(2026, 5, 19, 10, 0, 0).astimezone(),
    )

    loaded = store.load()
    assert loaded == [entry]
    assert loaded[0].wrong == "重新開幾"
    assert loaded[0].correct == "重新開機"


def test_store_skips_malformed_rows(tmp_path):
    path = tmp_path / "corrections.jsonl"
    valid = {
        "id": "entry-1",
        "type": "term",
        "wrong": "cue and",
        "correct": "Qwen",
        "scope": "global",
        "created_at": "2026-05-19T10:00:00+08:00",
        "updated_at": "2026-05-19T10:00:00+08:00",
        "uses": 0,
    }
    path.write_text("{bad json}\n" + json.dumps(valid, ensure_ascii=False) + "\n", encoding="utf-8")

    assert CorrectionMemoryStore(path).load() == [CorrectionEntry.from_dict(valid)]


def test_store_remove_rewrites_without_entry(tmp_path):
    store = CorrectionMemoryStore(tmp_path / "corrections.jsonl")
    first = store.add(CorrectionType.TERM, wrong="cue and", correct="Qwen")
    second = store.add(CorrectionType.TERM, wrong="type less", correct="Typeless")

    assert store.remove(first.id) is True
    assert store.load() == [second]
    assert store.remove("missing") is False


def test_select_relevant_corrections_prefers_wrong_phrase_matches():
    entries = [
        CorrectionEntry(
            id="term-1",
            type=CorrectionType.TERM,
            wrong="cue and",
            correct="Qwen",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=2,
        ),
        CorrectionEntry(
            id="phrase-1",
            type=CorrectionType.PHRASE,
            wrong="重新開幾",
            correct="重新開機",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=0,
        ),
    ]

    selected = select_relevant_corrections("請 cue and 幫我重新開幾", entries)

    assert [entry.id for entry in selected] == ["phrase-1", "term-1"]
```

- [ ] **Step 2: Run memory tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_memory.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'voicetype.memory'`.

- [ ] **Step 3: Implement memory store and selector**

Create `src/voicetype/memory.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
import os
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


class CorrectionType(StrEnum):
    TERM = "term"
    PHRASE = "phrase"


@dataclass(frozen=True)
class CorrectionEntry:
    id: str
    type: CorrectionType
    wrong: str
    correct: str
    scope: str
    created_at: str
    updated_at: str
    uses: int = 0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CorrectionEntry":
        entry_type = CorrectionType(str(payload["type"]))
        correct = normalize_text(str(payload["correct"]))
        if not correct:
            raise ValueError("Correction entry requires non-empty correct text")
        return cls(
            id=str(payload["id"]),
            type=entry_type,
            wrong=normalize_text(str(payload.get("wrong", ""))),
            correct=correct,
            scope=str(payload.get("scope", "global")) or "global",
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            uses=int(payload.get("uses", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "wrong": self.wrong,
            "correct": self.correct,
            "scope": self.scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "uses": self.uses,
        }

    def to_prompt_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "type": self.type.value,
            "wrong": self.wrong,
            "correct": self.correct,
        }


def default_memory_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base_dir / "VoiceType" / "memory" / "corrections.jsonl"


class CorrectionMemoryStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_memory_path()

    def load(self) -> list[CorrectionEntry]:
        if not self.path.exists():
            return []
        entries: list[CorrectionEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(CorrectionEntry.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        return entries

    def add(
        self,
        entry_type: CorrectionType | str,
        *,
        wrong: str,
        correct: str,
        scope: str = "global",
        now: Callable[[], datetime] | None = None,
    ) -> CorrectionEntry:
        timestamp = (now or (lambda: datetime.now().astimezone()))().isoformat(timespec="seconds")
        entry = CorrectionEntry(
            id=str(uuid4()),
            type=CorrectionType(str(entry_type)),
            wrong=normalize_text(wrong),
            correct=normalize_text(correct),
            scope=scope or "global",
            created_at=timestamp,
            updated_at=timestamp,
            uses=0,
        )
        if not entry.correct:
            raise ValueError("Correction entry requires --correct")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
        return entry

    def remove(self, entry_id: str) -> bool:
        entries = self.load()
        kept = [entry for entry in entries if entry.id != entry_id]
        if len(kept) == len(entries):
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for entry in kept:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
        return True


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def select_relevant_corrections(
    raw_text: str,
    entries: list[CorrectionEntry],
    *,
    limit: int = 20,
) -> list[CorrectionEntry]:
    normalized_raw = normalize_text(raw_text).casefold()
    scored: list[tuple[int, int, CorrectionEntry]] = []
    for index, entry in enumerate(entries):
        wrong = entry.wrong.casefold()
        correct = entry.correct.casefold()
        score = 0
        if wrong and wrong in normalized_raw:
            score = 100
        elif entry.type == CorrectionType.TERM and correct and correct in normalized_raw:
            score = 50
        if score:
            scored.append((score + min(entry.uses, 20), -index, entry))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [entry for _, _, entry in scored[:limit]]
```

- [ ] **Step 4: Run memory tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_memory.py -v
```

Expected: all tests in `tests/test_memory.py` pass.

- [ ] **Step 5: Commit memory store**

Run:

```powershell
git add src/voicetype/memory.py tests/test_memory.py
git commit -m "feat: add correction memory store"
```

---

### Task 2: Faster Whisper 5-by-5 Hotword Filter

**Files:**
- Modify: `src/voicetype/memory.py`
- Modify: `src/voicetype/whisper_client.py`
- Modify: `tests/test_memory.py`
- Modify: `tests/test_whisper_client.py`

- [ ] **Step 1: Add failing hotword filter tests**

Append to `tests/test_memory.py`:

```python
from voicetype.memory import select_whisper_hotwords


def test_select_whisper_hotwords_enforces_five_by_five_limit():
    hotwords = [
        " Qwen ",
        "Typeless",
        "重新開機",
        "Faster Whisper",
        "Allen",
        "Qwen",
        "語音",
        "",
    ]

    assert select_whisper_hotwords(hotwords) == ["Qwen", "重新開機", "Allen", "語音"]


def test_select_whisper_hotwords_can_include_short_term_memory_only():
    entries = [
        CorrectionEntry(
            id="short",
            type=CorrectionType.TERM,
            wrong="cue and",
            correct="Qwen",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=0,
        ),
        CorrectionEntry(
            id="phrase",
            type=CorrectionType.PHRASE,
            wrong="重新開幾",
            correct="重新開機",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=0,
        ),
        CorrectionEntry(
            id="long",
            type=CorrectionType.TERM,
            wrong="faster whisper",
            correct="Faster Whisper",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=0,
        ),
    ]

    assert select_whisper_hotwords(["Allen"], memory_entries=entries) == ["Allen", "Qwen"]
```

Append to `tests/test_whisper_client.py`:

```python
@responses.activate
def test_transcribe_sends_filtered_hotwords(tmp_path):
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(b"fake wav")
    responses.post(
        "http://example.test/transcribe",
        json={"success": True, "segments": [{"start": 0, "end": 1, "text": "ok"}]},
        status=200,
    )

    client = WhisperClient("http://example.test", timeout_sec=5)
    client.transcribe(
        wav_path,
        hotwords=["Qwen", "Typeless", "重新開機", "Faster Whisper", "Allen", "語音"],
    )

    request_body = responses.calls[0].request.body
    assert b"Qwen" in request_body
    assert "重新開機".encode("utf-8") in request_body
    assert b"Allen" in request_body
    assert b"Typeless" not in request_body
    assert b"Faster Whisper" not in request_body
```

- [ ] **Step 2: Run hotword tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_memory.py::test_select_whisper_hotwords_enforces_five_by_five_limit tests/test_whisper_client.py::test_transcribe_sends_filtered_hotwords -v
```

Expected: FAIL with `ImportError` or assertion failure because `select_whisper_hotwords` is not implemented.

- [ ] **Step 3: Implement hotword filtering**

Append to `src/voicetype/memory.py`:

```python
MAX_WHISPER_HOTWORDS = 5
MAX_WHISPER_HOTWORD_CHARS = 5


def select_whisper_hotwords(
    cli_hotwords: list[str],
    *,
    memory_entries: list[CorrectionEntry] | None = None,
    max_count: int = MAX_WHISPER_HOTWORDS,
    max_chars: int = MAX_WHISPER_HOTWORD_CHARS,
) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        hotword = normalize_text(value)
        key = hotword.casefold()
        if not hotword or key in seen:
            return
        if len(hotword) > max_chars:
            return
        if len(selected) >= max_count:
            return
        seen.add(key)
        selected.append(hotword)

    for hotword in cli_hotwords:
        add_candidate(hotword)

    for entry in memory_entries or []:
        if entry.type != CorrectionType.TERM:
            continue
        add_candidate(entry.correct)

    return selected
```

Modify `src/voicetype/whisper_client.py` imports:

```python
from voicetype.memory import select_whisper_hotwords
```

Modify the `data` construction in `WhisperClient.transcribe()`:

```python
        selected_hotwords = select_whisper_hotwords(hotwords or [])
        data = {
            "initial_prompt": initial_prompt,
            "hotwords": ", ".join(selected_hotwords),
```

- [ ] **Step 4: Run hotword tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_memory.py tests/test_whisper_client.py -v
```

Expected: memory and Whisper tests pass.

- [ ] **Step 5: Commit hotword filter**

Run:

```powershell
git add src/voicetype/memory.py src/voicetype/whisper_client.py tests/test_memory.py tests/test_whisper_client.py
git commit -m "feat: cap Faster Whisper hotwords"
```

---

### Task 3: Qwen Correction Memory Payload

**Files:**
- Modify: `src/voicetype/qwen_client.py`
- Modify: `tests/test_qwen_client.py`

- [ ] **Step 1: Add failing Qwen payload test**

Append to `tests/test_qwen_client.py`:

```python
from voicetype.memory import CorrectionEntry, CorrectionType


@responses.activate
def test_polish_sends_correction_memory_in_user_payload():
    responses.post(
        "http://example.test/v1/chat/completions",
        json={"choices": [{"message": {"content": '{"action":"insert","text":"Qwen is ready."}'}}]},
        status=200,
    )
    memory = [
        CorrectionEntry(
            id="entry-1",
            type=CorrectionType.TERM,
            wrong="cue and",
            correct="Qwen",
            scope="global",
            created_at="2026-05-19T10:00:00+08:00",
            updated_at="2026-05-19T10:00:00+08:00",
            uses=0,
        )
    ]
    client = QwenClient("http://example.test/v1", "qwen3.6-35b", timeout_sec=5)

    client.polish("cue and is ready", app_name="Notepad", correction_memory=memory)

    payload = json.loads(responses.calls[0].request.body)
    user_payload = json.loads(payload["messages"][1]["content"])
    assert user_payload["correction_memory"] == [
        {"id": "entry-1", "type": "term", "wrong": "cue and", "correct": "Qwen"}
    ]
```

- [ ] **Step 2: Run Qwen test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_qwen_client.py::test_polish_sends_correction_memory_in_user_payload -v
```

Expected: FAIL with `TypeError: QwenClient.polish() got an unexpected keyword argument 'correction_memory'`.

- [ ] **Step 3: Update Qwen client**

Modify `src/voicetype/qwen_client.py` imports:

```python
from voicetype.memory import CorrectionEntry
```

Modify `SYSTEM_PROMPT` to include correction memory rules:

```python
- Use correction_memory only when it matches the transcript.
- Prefer exact correction_memory over guessing.
- Do not invent new terms.
- Do not assume the ASR hotword list is exhaustive.
```

Modify `QwenClient.polish()` signature:

```python
    def polish(
        self,
        raw_text: str,
        *,
        app_name: str | None = None,
        hotwords: list[str] | None = None,
        correction_memory: list[CorrectionEntry] | None = None,
    ) -> str:
```

Modify `user_payload`:

```python
        user_payload = {
            "app": app_name or "unknown",
            "mode": "dictation",
            "raw_transcript": raw_text,
            "hotwords": hotwords or [],
            "correction_memory": [
                entry.to_prompt_dict() for entry in correction_memory or []
            ],
            "chinese_script": detect_chinese_script(raw_text),
        }
```

- [ ] **Step 4: Run Qwen tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_qwen_client.py -v
```

Expected: Qwen tests pass.

- [ ] **Step 5: Commit Qwen payload**

Run:

```powershell
git add src/voicetype/qwen_client.py tests/test_qwen_client.py
git commit -m "feat: send correction memory to Qwen"
```

---

### Task 4: Pipeline Memory Selection and Session Logs

**Files:**
- Modify: `src/voicetype/pipeline.py`
- Modify: `src/voicetype/session_log.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_session_log.py`

- [ ] **Step 1: Add failing pipeline tests**

Modify `FakeQwen` in `tests/test_pipeline.py`:

```python
class FakeQwen:
    def __init__(self):
        self.hotwords = None
        self.app_name = None
        self.correction_memory = None

    def polish(
        self,
        raw_text: str,
        *,
        app_name: str | None = None,
        hotwords: list[str] | None = None,
        correction_memory: list | None = None,
    ) -> str:
        self.hotwords = hotwords
        self.app_name = app_name
        self.correction_memory = correction_memory
        return f"polished: {raw_text}"
```

Append to `tests/test_pipeline.py`:

```python
from voicetype.memory import CorrectionEntry, CorrectionType


class FakeMemoryStore:
    def __init__(self, entries=None, error: Exception | None = None):
        self.entries = entries or []
        self.error = error

    def load(self):
        if self.error is not None:
            raise self.error
        return self.entries


def test_pipeline_selects_relevant_correction_memory_for_qwen(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    entry = CorrectionEntry(
        id="entry-1",
        type=CorrectionType.TERM,
        wrong="cue and",
        correct="Qwen",
        scope="global",
        created_at="2026-05-19T10:00:00+08:00",
        updated_at="2026-05-19T10:00:00+08:00",
        uses=0,
    )
    qwen = FakeQwen()
    whisper = FakeWhisper(
        TranscriptionResult(success=True, segments=[TranscriptionSegment(0.0, 1.0, "cue and")])
    )

    pipeline = DictationPipeline(
        whisper,
        qwen,
        FakeInjector(),
        enable_llm=True,
        memory_store=FakeMemoryStore([entry]),
    )
    result = pipeline.process_file_result(audio_path)

    assert qwen.correction_memory == [entry]
    assert result.correction_memory_ids == ["entry-1"]


def test_pipeline_continues_when_memory_load_fails(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    qwen = FakeQwen()
    whisper = FakeWhisper(
        TranscriptionResult(success=True, segments=[TranscriptionSegment(0.0, 1.0, "hello")])
    )

    pipeline = DictationPipeline(
        whisper,
        qwen,
        FakeInjector(),
        enable_llm=True,
        memory_store=FakeMemoryStore(error=OSError("cannot read")),
    )
    result = pipeline.process_file_result(audio_path)

    assert qwen.correction_memory == []
    assert result.correction_memory_error == "cannot read"
```

- [ ] **Step 2: Add failing session log test**

Append to `tests/test_session_log.py`:

```python
def test_build_listen_session_record_includes_memory_metadata():
    record = build_listen_session_record(
        started_at="2026-05-19T10:00:00+08:00",
        completed_at="2026-05-19T10:00:03+08:00",
        audio_path=Path("C:/Temp/voicetype-test.wav"),
        audio_seconds=3.0,
        audio_bytes=1234,
        normalization=None,
        result=PipelineResult(
            status="inserted",
            raw_text="cue and",
            final_text="Qwen",
            correction_memory_ids=["entry-1"],
            correction_memory_count=1,
            whisper_hotwords=["Qwen"],
            whisper_hotword_count_before=3,
            whisper_hotword_count_after=1,
        ),
        pasted=True,
        app_name="notepad",
    )

    assert record["memory"] == {
        "correction_ids": ["entry-1"],
        "correction_count": 1,
        "correction_error": None,
        "whisper_hotwords": ["Qwen"],
        "whisper_hotword_count_before": 3,
        "whisper_hotword_count_after": 1,
    }
```

- [ ] **Step 3: Run pipeline and session log tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_session_log.py -v
```

Expected: FAIL because `DictationPipeline` does not accept `memory_store` and `PipelineResult` has no memory metadata fields.

- [ ] **Step 4: Update pipeline result and memory handoff**

Modify `src/voicetype/pipeline.py` imports:

```python
from voicetype.memory import CorrectionMemoryStore, select_relevant_corrections, select_whisper_hotwords
```

Extend `PipelineResult`:

```python
    correction_memory_ids: list[str] | None = None
    correction_memory_count: int = 0
    correction_memory_error: str | None = None
    whisper_hotwords: list[str] | None = None
    whisper_hotword_count_before: int = 0
    whisper_hotword_count_after: int = 0
```

Modify `DictationPipeline.__init__()`:

```python
        memory_store=None,
    ) -> None:
        self.memory_store = memory_store or CorrectionMemoryStore()
```

Inside `process_file_result()` before transcription:

```python
        input_hotwords = hotwords or []
        whisper_hotwords = select_whisper_hotwords(input_hotwords)
```

Use `whisper_hotwords` for Whisper:

```python
            hotwords=whisper_hotwords,
```

After `raw_text` is known:

```python
        correction_memory_error = None
        correction_memory = []
        try:
            correction_memory = select_relevant_corrections(raw_text, self.memory_store.load())
        except OSError as exc:
            correction_memory_error = str(exc)
```

Pass to Qwen:

```python
            final_text = self.qwen.polish(
                raw_text,
                app_name=app_name,
                hotwords=input_hotwords,
                correction_memory=correction_memory,
            )
```

Populate final `PipelineResult`:

```python
            correction_memory_ids=[entry.id for entry in correction_memory],
            correction_memory_count=len(correction_memory),
            correction_memory_error=correction_memory_error,
            whisper_hotwords=whisper_hotwords,
            whisper_hotword_count_before=len(input_hotwords),
            whisper_hotword_count_after=len(whisper_hotwords),
```

- [ ] **Step 5: Update session log**

Modify `_result_dict()` in `src/voicetype/session_log.py` to include:

```python
        "memory": {
            "correction_ids": result.correction_memory_ids or [],
            "correction_count": result.correction_memory_count,
            "correction_error": result.correction_memory_error,
            "whisper_hotwords": result.whisper_hotwords or [],
            "whisper_hotword_count_before": result.whisper_hotword_count_before,
            "whisper_hotword_count_after": result.whisper_hotword_count_after,
        },
```

Then modify `build_listen_session_record()` to lift this value to the top level:

```python
    result_dict = _result_dict(result)
    return {
        ...
        "asr": result_dict,
        "memory": result_dict.get("memory") if result_dict else None,
        ...
    }
```

- [ ] **Step 6: Run pipeline and session log tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_session_log.py -v
```

Expected: pipeline and session log tests pass.

- [ ] **Step 7: Commit pipeline and log wiring**

Run:

```powershell
git add src/voicetype/pipeline.py src/voicetype/session_log.py tests/test_pipeline.py tests/test_session_log.py
git commit -m "feat: use correction memory in pipeline"
```

---

### Task 5: Memory CLI Commands

**Files:**
- Modify: `src/voicetype/cli.py`
- Modify: `tests/test_cli_entrypoint.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `tests/test_cli_entrypoint.py`:

```python
from voicetype.cli import build_parser


def test_memory_add_parser_accepts_term_correction():
    parser = build_parser()
    args = parser.parse_args(
        ["memory", "add", "--type", "term", "--wrong", "cue and", "--correct", "Qwen"]
    )

    assert args.command == "memory"
    assert args.memory_command == "add"
    assert args.type == "term"
    assert args.wrong == "cue and"
    assert args.correct == "Qwen"


def test_memory_learn_parser_accepts_from_last_corrected_text():
    parser = build_parser()
    args = parser.parse_args(["memory", "learn", "--from-last", "--corrected", "Qwen is ready"])

    assert args.command == "memory"
    assert args.memory_command == "learn"
    assert args.from_last is True
    assert args.corrected == "Qwen is ready"
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_entrypoint.py::test_memory_add_parser_accepts_term_correction tests/test_cli_entrypoint.py::test_memory_learn_parser_accepts_from_last_corrected_text -v
```

Expected: FAIL because `memory` subcommand does not exist.

- [ ] **Step 3: Add parser commands**

Modify `build_parser()` in `src/voicetype/cli.py` after logs parser:

```python
    memory_parser = subparsers.add_parser("memory")
    memory_parser.set_defaults(command="memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    memory_add = memory_subparsers.add_parser("add")
    memory_add.add_argument("--type", choices=["term", "phrase"], required=True)
    memory_add.add_argument("--wrong", default="")
    memory_add.add_argument("--correct", required=True)

    memory_list = memory_subparsers.add_parser("list")
    memory_list.add_argument("--json", action="store_true")

    memory_remove = memory_subparsers.add_parser("remove")
    memory_remove.add_argument("id")

    memory_learn = memory_subparsers.add_parser("learn")
    memory_learn.add_argument("--from-last", action="store_true", required=True)
    memory_learn.add_argument("--corrected", required=True)
```

Modify imports:

```python
from voicetype.memory import CorrectionMemoryStore, CorrectionType
```

Add command branch in `main()` before `doctor`:

```python
    if args.command == "memory":
        run_memory(args)
        return
```

Add `run_memory()`:

```python
def run_memory(args) -> None:
    store = CorrectionMemoryStore()
    if args.memory_command == "add":
        entry = store.add(CorrectionType(args.type), wrong=args.wrong, correct=args.correct)
        print(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
        return

    if args.memory_command == "list":
        entries = store.load()
        if args.json:
            for entry in entries:
                print(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
            return
        if not entries:
            print("[VoiceType] No correction memory entries.")
            return
        for entry in entries:
            print(f"{entry.id} | {entry.type.value} | {entry.wrong or '-'} -> {entry.correct}")
        return

    if args.memory_command == "remove":
        removed = store.remove(args.id)
        print(f"[VoiceType] Removed correction memory entry: {args.id}" if removed else f"[VoiceType] No correction memory entry found: {args.id}")
        return

    if args.memory_command == "learn":
        record = latest_session_record()
        if record is None:
            print("[VoiceType] No latest session log record found.")
            return
        asr = record.get("asr") or {}
        raw_text = str(asr.get("raw_text") or "")
        if not raw_text.strip():
            print("[VoiceType] Latest session has no raw ASR text.")
            return
        entry = store.add(CorrectionType.PHRASE, wrong=raw_text, correct=args.corrected)
        print(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_entrypoint.py -v
```

Expected: CLI tests pass.

- [ ] **Step 5: Manual memory CLI smoke**

Run with a temporary local app data directory to avoid touching real user memory:

```powershell
$env:LOCALAPPDATA = "$pwd\.tmp-localappdata"
.\.venv\Scripts\python.exe -m voicetype memory add --type term --wrong "cue and" --correct "Qwen"
.\.venv\Scripts\python.exe -m voicetype memory list
Remove-Item Env:\LOCALAPPDATA
```

Expected: first command prints one JSON entry; second command lists the same entry.

- [ ] **Step 6: Commit memory CLI**

Run:

```powershell
git add src/voicetype/cli.py tests/test_cli_entrypoint.py
git commit -m "feat: add correction memory CLI"
```

---

### Task 6: Documentation, Handoff, and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `CODEX_HANDOFF.md`

- [ ] **Step 1: Update README**

Add a "Correction Memory" section to `README.md`:

````markdown
## Correction Memory

VoiceType uses Qwen, not Faster Whisper, as the main correction layer. Faster Whisper receives at most five short hotwords, each no longer than five characters. Longer vocabulary and phrase corrections are stored locally and sent only to Qwen when relevant.

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
````

- [ ] **Step 2: Update handoff**

Update `CODEX_HANDOFF.md`:

```markdown
- Correction Memory v1 stores local term and phrase corrections in `%LOCALAPPDATA%\VoiceType\memory\corrections.jsonl`.
- Faster Whisper hotwords are capped to five entries of five Unicode characters each.
- Phrase corrections and long terms are sent only to Qwen, not Faster Whisper.
- Session logs include selected correction memory IDs and Whisper hotword filtering metadata.
```

- [ ] **Step 3: Run full verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m voicetype memory --help
.\.venv\Scripts\python.exe -m voicetype memory add --help
```

Expected:

- pytest reports all tests passed.
- compileall exits 0.
- memory help commands print usage and exit 0.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add README.md CODEX_HANDOFF.md
git commit -m "docs: document correction memory"
```

---

## Self-Review

Spec coverage:

- Local term and phrase memory is covered by Task 1 and Task 5.
- Qwen correction payload is covered by Task 3.
- Faster Whisper 5-by-5 hotword policy is covered by Task 2.
- Pipeline fail-open behavior is covered by Task 4.
- Session logging metadata is covered by Task 4.
- User-facing docs and handoff updates are covered by Task 6.

Placeholder scan:

- No placeholder markers or unspecified "add tests" steps remain.
- Every task has concrete files, tests, commands, and expected results.

Type consistency:

- `CorrectionEntry`, `CorrectionType`, `CorrectionMemoryStore`, `select_relevant_corrections()`, and `select_whisper_hotwords()` are introduced in Task 1/2 before later tasks use them.
- `QwenClient.polish(..., correction_memory=...)` is introduced before pipeline usage.
- `PipelineResult` memory fields match the session log test names.
