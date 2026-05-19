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
            score = 100 if entry.type == CorrectionType.PHRASE else 80
        elif entry.type == CorrectionType.TERM and correct and correct in normalized_raw:
            score = 50
        if score:
            scored.append((score + min(entry.uses, 20), -index, entry))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [entry for _, _, entry in scored[:limit]]
