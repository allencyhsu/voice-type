from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import requests

from voicetype.memory import CorrectionMemoryStore, select_relevant_corrections, select_whisper_hotwords


class WhisperLike(Protocol):
    def transcribe(self, path: Path, *, initial_prompt: str, hotwords: list[str]):
        raise NotImplementedError


class QwenLike(Protocol):
    def polish(
        self,
        raw_text: str,
        *,
        app_name: str | None = None,
        hotwords: list[str] | None = None,
        correction_memory: list | None = None,
    ) -> str:
        raise NotImplementedError


class InjectorLike(Protocol):
    def paste(self, text: str) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class PipelineResult:
    status: str
    raw_text: str
    final_text: str
    error: str | None = None
    language: str | None = None
    duration: float | None = None
    transcribe_time: float | None = None
    correction_memory_ids: list[str] | None = None
    correction_memory_count: int = 0
    correction_memory_error: str | None = None
    whisper_hotwords: list[str] | None = None
    whisper_hotword_count_before: int = 0
    whisper_hotword_count_after: int = 0


class DictationPipeline:
    def __init__(
        self,
        whisper: WhisperLike,
        qwen: QwenLike | None,
        injector: InjectorLike,
        *,
        enable_llm: bool,
        memory_store=None,
    ) -> None:
        self.whisper = whisper
        self.qwen = qwen
        self.injector = injector
        self.enable_llm = enable_llm
        self.memory_store = memory_store or CorrectionMemoryStore()

    def process_file(
        self,
        audio_path: str | Path,
        *,
        app_name: str | None = None,
        initial_prompt: str = "",
        hotwords: list[str] | None = None,
        paste: bool = True,
    ) -> str:
        return self.process_file_result(
            audio_path,
            app_name=app_name,
            initial_prompt=initial_prompt,
            hotwords=hotwords,
            paste=paste,
        ).final_text

    def process_file_result(
        self,
        audio_path: str | Path,
        *,
        app_name: str | None = None,
        initial_prompt: str = "",
        hotwords: list[str] | None = None,
        paste: bool = True,
    ) -> PipelineResult:
        input_hotwords = hotwords or []
        whisper_hotwords = select_whisper_hotwords(input_hotwords)
        try:
            result = self.whisper.transcribe(
                Path(audio_path),
                initial_prompt=initial_prompt,
                hotwords=whisper_hotwords,
            )
        except requests.RequestException as exc:
            return PipelineResult(
                status="asr_error",
                raw_text="",
                final_text="",
                error=str(exc),
                whisper_hotwords=whisper_hotwords,
                whisper_hotword_count_before=len(input_hotwords),
                whisper_hotword_count_after=len(whisper_hotwords),
            )
        raw_text = result.text if result.success else ""
        if not raw_text:
            return PipelineResult(
                status="empty_transcript" if result.success else "asr_failed",
                raw_text="",
                final_text="",
                error=result.error,
                language=result.language,
                duration=result.duration,
                transcribe_time=result.transcribe_time,
                whisper_hotwords=whisper_hotwords,
                whisper_hotword_count_before=len(input_hotwords),
                whisper_hotword_count_after=len(whisper_hotwords),
            )

        final_text = raw_text
        correction_memory_error = None
        correction_memory = []
        try:
            correction_memory = select_relevant_corrections(raw_text, self.memory_store.load())
        except OSError as exc:
            correction_memory_error = str(exc)

        if self.enable_llm and self.qwen is not None:
            final_text = self.qwen.polish(
                raw_text,
                app_name=app_name,
                hotwords=input_hotwords,
                correction_memory=correction_memory,
            )

        if paste and final_text.strip():
            self.injector.paste(final_text)
        return PipelineResult(
            status="inserted" if paste else "transcribed",
            raw_text=raw_text,
            final_text=final_text,
            language=result.language,
            duration=result.duration,
            transcribe_time=result.transcribe_time,
            correction_memory_ids=[entry.id for entry in correction_memory],
            correction_memory_count=len(correction_memory),
            correction_memory_error=correction_memory_error,
            whisper_hotwords=whisper_hotwords,
            whisper_hotword_count_before=len(input_hotwords),
            whisper_hotword_count_after=len(whisper_hotwords),
        )
