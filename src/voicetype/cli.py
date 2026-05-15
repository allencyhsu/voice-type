import argparse
from pathlib import Path

from voicetype.audio import record_wav
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

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--seconds", type=float, default=None)
    record_parser.add_argument("--paste", action="store_true")
    record_parser.add_argument("--no-llm", action="store_true")
    record_parser.add_argument("--hotword", action="append", default=[])

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

    audio_file = getattr(args, "audio_file", None)
    if args.command == "record":
        audio_file = record_wav(
            args.seconds or settings.record_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
        )

    pipeline = DictationPipeline(
        whisper,
        qwen,
        TextInjector(),
        enable_llm=enable_llm,
    )
    final_text = pipeline.process_file(
        audio_file,
        hotwords=args.hotword,
        paste=args.paste,
    )
    print(final_text)
