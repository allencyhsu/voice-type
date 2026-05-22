from dataclasses import dataclass
from pathlib import Path

import requests

from voicetype.memory import CorrectionEntry, CorrectionType
from voicetype.pipeline import DictationPipeline
from voicetype.whisper_client import TranscriptionResult, TranscriptionSegment


@dataclass
class FakeWhisper:
    result: TranscriptionResult

    def transcribe(self, path: Path, *, initial_prompt: str, hotwords: list[str]):
        return self.result


class FakeTimeoutWhisper:
    def transcribe(self, path: Path, *, initial_prompt: str, hotwords: list[str]):
        raise requests.Timeout("ASR timed out")


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


class FakeInjector:
    def __init__(self):
        self.text = None

    def paste(self, text: str) -> None:
        self.text = text


class FakeMemoryStore:
    def __init__(self, entries=None, error: Exception | None = None):
        self.entries = entries or []
        self.error = error

    def load(self):
        if self.error is not None:
            raise self.error
        return self.entries


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

    qwen = FakeQwen()
    pipeline = DictationPipeline(whisper, qwen, injector, enable_llm=True)
    result = pipeline.process_file(audio_path, app_name="Notepad")

    assert result == "polished: hello"
    assert injector.text == "polished: hello"
    assert qwen.app_name == "Notepad"


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


def test_pipeline_result_reports_asr_request_timeout_without_pasting(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"fake")
    injector = FakeInjector()

    pipeline = DictationPipeline(FakeTimeoutWhisper(), FakeQwen(), injector, enable_llm=True)
    result = pipeline.process_file_result(audio_path)

    assert result.status == "asr_error"
    assert result.raw_text == ""
    assert result.final_text == ""
    assert result.error == "ASR timed out"
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
