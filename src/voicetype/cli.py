import argparse
from collections.abc import Callable
from datetime import date, datetime
import json
import os
import threading
from pathlib import Path
from typing import Any

from voicetype.active_window import get_active_app_name
from voicetype.audio import AudioNormalization, cleanup_old_temp_audio, ToggleRecorder, record_opus
from voicetype.hotkey import RightCtrlToggleListener
from voicetype.injector import TextInjector
from voicetype.memory import CorrectionMemoryStore, CorrectionType
from voicetype.notifier import create_notifier
from voicetype.output_audio import (
    OutputMuteGuard,
    create_output_mute_guard,
    try_mute_for_recording,
    try_restore_output,
)
from voicetype.pipeline import DictationPipeline, PipelineResult
from voicetype.qwen_client import QwenClient
from voicetype.session_log import (
    SessionLogger,
    build_listen_session_record,
    default_log_dir,
    latest_session_record,
    log_path_for,
    read_session_records,
)
from voicetype.settings import Settings
from voicetype.whisper_client import WhisperClient


def record_opus_with_output_muted(
    seconds: float,
    *,
    sample_rate: int,
    channels: int,
    output_guard: OutputMuteGuard | None = None,
    record_func: Callable[..., Path] = record_opus,
) -> Path:
    guard = output_guard or create_output_mute_guard()
    try_mute_for_recording(guard)
    try:
        return record_func(seconds, sample_rate=sample_rate, channels=channels)
    finally:
        try_restore_output(guard)


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
    listen_parser.add_argument("--min-seconds", type=float, default=None)
    listen_parser.add_argument("--notify", choices=["overlay", "console", "toast", "off"], default=None)

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("--today", action="store_true", default=True)
    logs_parser.add_argument("--limit", type=int, default=10)
    logs_parser.add_argument("--last", action="store_true")
    logs_parser.add_argument("--json", action="store_true")
    logs_parser.add_argument("--open-dir", action="store_true")

    memory_parser = subparsers.add_parser("memory")
    memory_parser.set_defaults(command="memory")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)

    memory_add = memory_subparsers.add_parser("add")
    memory_add.add_argument("--type", choices=["term", "phrase"], required=True)
    memory_add.add_argument("--wrong", default="")
    memory_add.add_argument("--correct", required=True)

    memory_list = memory_subparsers.add_parser("list")
    memory_list.add_argument("--json", action="store_true")

    memory_remove = memory_subparsers.add_parser("remove")
    memory_remove.add_argument("id")

    memory_learn = memory_subparsers.add_parser("learn")
    memory_learn.add_argument("--from-last", action="store_true", required=True)
    memory_learn.add_argument("--corrected", required=True)

    tray_parser = subparsers.add_parser("tray")
    tray_parser.set_defaults(command="tray")

    return parser


def main() -> None:
    cleanup = cleanup_old_temp_audio()
    if cleanup.deleted:
        print(f"[VoiceType] Cleaned {len(cleanup.deleted)} old temp audio file(s).")
    if cleanup.failed:
        print(f"[VoiceType] Could not clean {len(cleanup.failed)} temp audio file(s).")

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "logs":
        run_logs(args)
        return

    if args.command == "memory":
        run_memory(args)
        return

    if args.command == "tray":
        from voicetype.tray import run_tray_app

        run_tray_app()
        return

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
        audio_file = record_opus_with_output_muted(
            args.seconds or settings.record_seconds,
            sample_rate=settings.sample_rate,
            channels=settings.channels,
        )

    final_text = pipeline.process_file(
        audio_file,
        hotwords=args.hotword,
        paste=args.paste,
    )
    print(final_text)


def run_listen(args, settings: Settings, pipeline: DictationPipeline) -> None:
    recorder = ToggleRecorder(sample_rate=settings.sample_rate, channels=settings.channels)
    output_guard = create_output_mute_guard()
    notifier = create_notifier(args.notify or settings.notify)
    session_logger = SessionLogger()
    lock = threading.Lock()
    min_seconds = args.min_seconds or settings.min_record_seconds
    recording_started_at = {"value": None}

    print("VoiceType ready. Press right Ctrl to start listening; press right Ctrl again to stop.")
    print("Press Ctrl+C in this terminal to quit.")
    update_listener_status(args, "Ready")

    def toggle() -> None:
        with lock:
            if not recorder.is_recording:
                recorder.start()
                try_mute_for_recording(output_guard)
                recording_started_at["value"] = current_timestamp()
                notifier.notify("Listening...")
                update_listener_status(args, "Listening")
                return

            notifier.notify("Processing...")
            update_listener_status(args, "Processing")
            try:
                audio_path = recorder.stop_to_opus()
            finally:
                try_restore_output(output_guard)
            completed_at = current_timestamp()
            segment_started_at = recording_started_at["value"]
            recording_started_at["value"] = None
            recorded_seconds = recorder.duration_seconds
            audio_bytes = audio_path.stat().st_size
            app_name = get_active_app_name()
            if not should_process_recording(recorded_seconds, min_seconds=min_seconds):
                ignored_reason = f"short_recording:{recorded_seconds:.2f}s<{min_seconds:.2f}s"
                append_session_record(
                    session_logger,
                    build_listen_session_record(
                        started_at=segment_started_at,
                        completed_at=completed_at,
                        audio_path=audio_path,
                        audio_seconds=recorded_seconds,
                        audio_bytes=audio_bytes,
                        normalization=None,
                        result=None,
                        pasted=False,
                        app_name=app_name,
                        ignored_reason=ignored_reason,
                    ),
                )
                notifier.notify(f"Ignored short recording ({recorded_seconds:.2f}s < {min_seconds:.2f}s).")
                update_listener_status(args, "Ready")
                return

            normalization = recorder.last_normalization or AudioNormalization(
                applied=False,
                gain=1.0,
                peak_before=0.0,
                peak_after=0.0,
            )
            print(f"[VoiceType] Captured {recorded_seconds:.2f}s, {audio_bytes} bytes: {audio_path}")
            if normalization.applied:
                print(
                    "[VoiceType] Normalized audio "
                    f"gain={normalization.gain:.1f}x "
                    f"peak={normalization.peak_before:.4f}->{normalization.peak_after:.4f}"
                )

        result = pipeline.process_file_result(
            audio_path,
            app_name=app_name,
            hotwords=args.hotword,
            paste=not args.no_paste,
        )
        append_session_record(
            session_logger,
            build_listen_session_record(
                started_at=segment_started_at,
                completed_at=current_timestamp(),
                audio_path=audio_path,
                audio_seconds=recorded_seconds,
                audio_bytes=audio_path.stat().st_size,
                normalization=normalization,
                result=result,
                pasted=not args.no_paste and bool(result.final_text.strip()),
                app_name=app_name,
            ),
        )
        if args.notify != "console":
            notifier.notify(describe_pipeline_status(result, paste_enabled=not args.no_paste))
        print(describe_pipeline_result(result, paste_enabled=not args.no_paste))
        update_listener_status(args, "Ready")

    listener = RightCtrlToggleListener(toggle)
    listener_holder = getattr(args, "listener_holder", None)
    if listener_holder is not None:
        listener_holder["stop"] = listener.stop
    try:
        listener.run()
    except KeyboardInterrupt:
        print("\n[VoiceType] Stopped.")
    finally:
        if recorder.is_recording:
            recorder.cancel()
            try_restore_output(output_guard)
        update_listener_status(args, "Stopped")
        if listener_holder is not None:
            listener_holder.pop("stop", None)


def run_logs(args) -> None:
    log_dir = default_log_dir()
    if args.open_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        open_log_dir(log_dir)

    day = date.today()
    path = log_path_for(day, log_dir=log_dir)
    records = read_session_records(day=day, log_dir=log_dir)

    if args.last:
        record = latest_session_record(day=day, log_dir=log_dir)
        if record is None:
            print(f"[VoiceType] No session log found for today: {path}")
            return
        if args.json:
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            return
        print(format_log_record(record))
        return

    if args.json:
        for record in select_recent_records(records, limit=args.limit):
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        if not records:
            print(f"[VoiceType] No session log found for today: {path}")
        return

    if not records:
        print(f"[VoiceType] No session log found for today: {path}")
        return

    print(f"[VoiceType] Session log: {path}")
    for line in format_log_summary(records, limit=args.limit):
        print(line)


def run_memory(args) -> None:
    store = CorrectionMemoryStore()
    if args.memory_command == "add":
        entry = store.add(CorrectionType(args.type), wrong=args.wrong, correct=args.correct)
        print(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
        return

    if args.memory_command == "list":
        entries = store.load()
        if args.json:
            for entry in entries:
                print(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))
            return
        if not entries:
            print("[VoiceType] No correction memory entries.")
            return
        for entry in entries:
            print(f"{entry.id} | {entry.type.value} | {entry.wrong or '-'} -> {entry.correct}")
        return

    if args.memory_command == "remove":
        removed = store.remove(args.id)
        if removed:
            print(f"[VoiceType] Removed correction memory entry: {args.id}")
            return
        print(f"[VoiceType] No correction memory entry found: {args.id}")
        return

    if args.memory_command == "learn":
        record = latest_session_record()
        if record is None:
            print("[VoiceType] No latest session log record found.")
            return
        asr = record.get("asr") or {}
        raw_text = str(asr.get("raw_text") or "")
        if not raw_text.strip():
            print("[VoiceType] Latest session has no raw ASR text.")
            return
        entry = store.add(CorrectionType.PHRASE, wrong=raw_text, correct=args.corrected)
        print(json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")))


def open_log_dir(log_dir: Path) -> None:
    try:
        os.startfile(log_dir)
    except AttributeError:
        print(f"[VoiceType] Log directory: {log_dir}")


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


def describe_pipeline_status(result: PipelineResult, *, paste_enabled: bool = True) -> str:
    if result.final_text:
        if paste_enabled:
            return "Inserted text."
        return "Transcribed text."
    return "No text recognized."


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_session_record(session_logger: SessionLogger, record: dict) -> None:
    try:
        session_logger.append(record)
    except OSError as exc:
        print(f"[VoiceType] Could not write session log: {exc}")


def update_listener_status(args, status: str) -> None:
    status_callback = getattr(args, "status_callback", None)
    if status_callback is None:
        return
    try:
        status_callback(status)
    except Exception as exc:
        print(f"[VoiceType] Could not update listener status: {exc}")


def select_recent_records(records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    return list(reversed(records[-limit:]))


def format_log_summary(records: list[dict[str, Any]], *, limit: int) -> list[str]:
    recent = select_recent_records(records, limit=limit)
    if not recent:
        return ["[VoiceType] No session records found."]
    return [format_log_record(record) for record in recent]


def format_log_record(record: dict[str, Any]) -> str:
    audio = record.get("audio") or {}
    asr = record.get("asr") or {}
    seconds = audio.get("seconds")
    status = asr.get("status") or record.get("ignored_reason") or "unknown"
    language = asr.get("language") or "-"
    transcribe_time = asr.get("transcribe_time")
    pasted = "yes" if record.get("pasted") else "no"
    app_name = record.get("app_name") or "unknown"
    text = summarize_text(asr.get("final_text") or asr.get("raw_text") or record.get("ignored_reason") or "")
    path = audio.get("path") or "-"

    seconds_text = f"{seconds:.2f}s" if isinstance(seconds, int | float) else "-s"
    asr_text = f"asr={transcribe_time:.2f}s" if isinstance(transcribe_time, int | float) else "asr=-"
    return (
        f"{record.get('completed_at', '-')} | app={app_name} | {seconds_text} | {status} | {language} | "
        f"{asr_text} | pasted={pasted} | {text} | {path}"
    )


def summarize_text(text: str, *, max_length: int = 80) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= max_length:
        return clean or "-"
    return f"{clean[: max_length - 3]}..."


def should_process_recording(recorded_seconds: float, *, min_seconds: float) -> bool:
    return recorded_seconds >= min_seconds
