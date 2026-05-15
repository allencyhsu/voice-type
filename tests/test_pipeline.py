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
    def __init__(self):
        self.hotwords = None

    def polish(
        self,
        raw_text: str,
        *,
        app_name: str | None = None,
        hotwords: list[str] | None = None,
    ) -> str:
        self.hotwords = hotwords
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


def test_pipeline_passes_hotwords_to_qwen(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    qwen = FakeQwen()
    whisper = FakeWhisper(
        TranscriptionResult(
            success=True,
            segments=[TranscriptionSegment(0.0, 1.0, "typeless")],
        )
    )

    pipeline = DictationPipeline(whisper, qwen, FakeInjector(), enable_llm=True)
    pipeline.process_file(audio_path, hotwords=["Typeless"])

    assert qwen.hotwords == ["Typeless"]


def test_pipeline_does_not_paste_on_failed_asr(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    injector = FakeInjector()
    whisper = FakeWhisper(TranscriptionResult(success=False, segments=[]))

    pipeline = DictationPipeline(whisper, FakeQwen(), injector, enable_llm=True)
    result = pipeline.process_file(audio_path)

    assert result == ""
    assert injector.text is None


def test_pipeline_result_reports_failed_asr_reason(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    whisper = FakeWhisper(TranscriptionResult(success=False, segments=[], error="no speech"))
    injector = FakeInjector()

    pipeline = DictationPipeline(whisper, FakeQwen(), injector, enable_llm=True)
    result = pipeline.process_file_result(audio_path)

    assert result.status == "asr_failed"
    assert result.raw_text == ""
    assert result.final_text == ""
    assert result.error == "no speech"
    assert injector.text is None


def test_pipeline_result_reports_empty_transcript_reason(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    whisper = FakeWhisper(TranscriptionResult(success=True, segments=[]))
    injector = FakeInjector()

    pipeline = DictationPipeline(whisper, FakeQwen(), injector, enable_llm=True)
    result = pipeline.process_file_result(audio_path)

    assert result.status == "empty_transcript"
    assert result.error is None
    assert injector.text is None
