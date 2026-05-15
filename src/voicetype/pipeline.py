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
