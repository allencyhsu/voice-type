import json
from datetime import datetime

from voicetype.memory import (
    CorrectionEntry,
    CorrectionMemoryStore,
    CorrectionType,
    default_memory_path,
    select_relevant_corrections,
    select_whisper_hotwords,
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
