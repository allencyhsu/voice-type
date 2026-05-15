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
