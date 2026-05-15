from collections.abc import Callable, Mapping
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from voicetype.audio import AudioNormalization
from voicetype.pipeline import PipelineResult


def default_log_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base_dir / "VoiceType" / "logs"


class SessionLogger:
    def __init__(
        self,
        *,
        log_dir: str | Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.log_dir = Path(log_dir) if log_dir is not None else default_log_dir()
        self._now = now or datetime.now

    @property
    def path(self) -> Path:
        return self.log_dir / f"{self._now():%Y-%m-%d}.jsonl"

    def append(self, record: Mapping[str, Any]) -> Path:
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(record), ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
        return path


def build_listen_session_record(
    *,
    started_at: str | None,
    completed_at: str,
    audio_path: Path,
    audio_seconds: float,
    audio_bytes: int,
    normalization: AudioNormalization | None,
    result: PipelineResult | None,
    pasted: bool,
    ignored_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "event": "listen_segment",
        "started_at": started_at,
        "completed_at": completed_at,
        "audio": {
            "path": audio_path.as_posix(),
            "seconds": audio_seconds,
            "bytes": audio_bytes,
        },
        "normalization": _normalization_dict(normalization),
        "asr": _result_dict(result),
        "pasted": pasted,
        "ignored_reason": ignored_reason,
    }


def _normalization_dict(normalization: AudioNormalization | None) -> dict[str, Any] | None:
    if normalization is None:
        return None
    return {
        "applied": normalization.applied,
        "gain": normalization.gain,
        "peak_before": normalization.peak_before,
        "peak_after": normalization.peak_after,
    }


def _result_dict(result: PipelineResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "status": result.status,
        "raw_text": result.raw_text,
        "final_text": result.final_text,
        "error": result.error,
        "language": result.language,
        "duration": result.duration,
        "transcribe_time": result.transcribe_time,
    }
