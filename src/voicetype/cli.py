import argparse
import threading
from pathlib import Path

from voicetype.audio import ToggleRecorder, normalize_wav, record_wav
from voicetype.hotkey import RightCtrlToggleListener
from voicetype.injector import TextInjector
from voicetype.pipeline import DictationPipeline, PipelineResult
from voicetype.qwen_client import QwenClient
from voicetype.settings import Settings
from voicetype.whisper_client import WhisperClient


def build_parser() -> argparse.ArgumentParser:
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

    listen_parser = subparsers.add_parser("listen")
    listen_parser.add_argument("--no-paste", action="store_true")
    listen_parser.add_argument("--no-llm", action="store_true")
    listen_parser.add_argument("--hotword", action="append", default=[])

    return parser


def main() -> None:
    parser = build_parser()
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

    injector = TextInjector()
    pipeline = DictationPipeline(
        whisper,
        qwen,
        injector,
        enable_llm=enable_llm,
    )

    if args.command == "listen":
        run_listen(args, settings, pipeline)
        return

    audio_file = getattr(args, "audio_file", None)
    if args.command == "record":
        audio_file = record_wav(
            args.seconds or settings.record_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
        )
        normalize_wav(audio_file)

    final_text = pipeline.process_file(
        audio_file,
        hotwords=args.hotword,
        paste=args.paste,
    )
    print(final_text)


def run_listen(args, settings: Settings, pipeline: DictationPipeline) -> None:
    recorder = ToggleRecorder(sample_rate=settings.sample_rate, channels=settings.channels)
    lock = threading.Lock()

    print("VoiceType ready. Press right Ctrl to start listening; press right Ctrl again to stop.")
    print("Press Ctrl+C in this terminal to quit.")

    def toggle() -> None:
        with lock:
            if not recorder.is_recording:
                recorder.start()
                print("[VoiceType] Listening...")
                return

            print("[VoiceType] Processing...")
            audio_path = recorder.stop_to_wav()
            recorded_seconds = recorder.duration_seconds
            normalization = normalize_wav(audio_path)
            audio_bytes = audio_path.stat().st_size
            print(f"[VoiceType] Captured {recorded_seconds:.2f}s, {audio_bytes} bytes: {audio_path}")
            if normalization.applied:
                print(
                    "[VoiceType] Normalized audio "
                    f"gain={normalization.gain:.1f}x "
                    f"peak={normalization.peak_before:.4f}->{normalization.peak_after:.4f}"
                )

        result = pipeline.process_file_result(
            audio_path,
            hotwords=args.hotword,
            paste=not args.no_paste,
        )
        print(describe_pipeline_result(result, paste_enabled=not args.no_paste))

    listener = RightCtrlToggleListener(toggle)
    try:
        listener.run()
    except KeyboardInterrupt:
        print("\n[VoiceType] Stopped.")


def describe_pipeline_result(result: PipelineResult, *, paste_enabled: bool = True) -> str:
    details = []
    if result.language:
        details.append(f"language={result.language}")
    if result.duration is not None:
        details.append(f"audio={result.duration:.2f}s")
    if result.transcribe_time is not None:
        details.append(f"asr={result.transcribe_time:.2f}s")
    if result.error:
        details.append(f"error={result.error}")

    suffix = f" ({', '.join(details)})" if details else ""
    if result.final_text:
        if paste_enabled:
            return f"[VoiceType] Inserted text. status={result.status}{suffix}"
        return result.final_text
    return f"[VoiceType] No text recognized. status={result.status}{suffix}"
