from pathlib import Path
from types import SimpleNamespace

import voicetype.__main__ as entrypoint
import voicetype.cli as cli
from voicetype.cli import (
    build_parser,
    describe_pipeline_result,
    describe_pipeline_status,
    format_log_summary,
    run_listen,
    select_recent_records,
    should_process_recording,
)
from voicetype.pipeline import PipelineResult


class FakeOutputGuard:
    def __init__(self, events):
        self.events = events

    def mute_for_recording(self):
        self.events.append("guard.mute")

    def restore(self):
        self.events.append("guard.restore")


class FakeNotifier:
    def __init__(self, events):
        self.events = events

    def notify(self, message):
        self.events.append(f"notify:{message}")


class FakePipeline:
    def __init__(self, events):
        self.events = events

    def process_file_result(self, audio_path, *, app_name=None, hotwords=None, paste=True):
        self.events.append(f"pipeline.process:{Path(audio_path).name}:{app_name}:{paste}")
        return PipelineResult(status="inserted", raw_text="raw", final_text="final")


class FakeListener:
    def __init__(self, toggle, events, *, interrupt=False):
        self.toggle = toggle
        self.events = events
        self.interrupt = interrupt

    def run(self):
        self.events.append("listener.run")
        self.toggle()
        if self.interrupt:
            raise KeyboardInterrupt
        self.toggle()

    def stop(self):
        self.events.append("listener.stop")


class FakeRecorder:
    def __init__(self, events, opus_path, *, duration_seconds):
        self.events = events
        self.opus_path = opus_path
        self.duration_seconds = duration_seconds
        self.is_recording = False
        self.last_normalization = SimpleNamespace(applied=True, gain=2.0, peak_before=0.4, peak_after=0.8)

    def start(self):
        self.events.append("recorder.start")
        self.is_recording = True

    def stop_to_opus(self):
        self.events.append("recorder.stop")
        self.is_recording = False
        self.opus_path.write_bytes(b"fake opus")
        return self.opus_path

    def cancel(self):
        self.events.append("recorder.cancel")
        self.is_recording = False


class FakeRecorderStopFails(FakeRecorder):
    def stop_to_opus(self):
        self.events.append("recorder.stop")
        self.is_recording = False
        raise RuntimeError("stop failed")


def _listen_args(**overrides):
    values = {
        "notify": "off",
        "min_seconds": None,
        "hotword": [],
        "no_paste": False,
        "status_callback": lambda status: None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _settings(**overrides):
    values = {
        "sample_rate": 16000,
        "channels": 1,
        "min_record_seconds": 0.7,
        "notify": "overlay",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_listen_dependencies(
    monkeypatch,
    events,
    tmp_path,
    *,
    duration_seconds,
    interrupt=False,
    recorder_class=FakeRecorder,
):
    guard = FakeOutputGuard(events)
    recorder = recorder_class(events, tmp_path / "listen.ogg", duration_seconds=duration_seconds)

    monkeypatch.setattr(cli, "create_output_mute_guard", lambda: guard)
    monkeypatch.setattr(cli, "ToggleRecorder", lambda *, sample_rate, channels: recorder)
    monkeypatch.setattr(cli, "create_notifier", lambda notify: FakeNotifier(events))
    monkeypatch.setattr(cli, "RightCtrlToggleListener", lambda toggle: FakeListener(toggle, events, interrupt=interrupt))
    monkeypatch.setattr(cli, "get_active_app_name", lambda: events.append("active_app") or "Notepad")
    monkeypatch.setattr(cli, "append_session_record", lambda session_logger, record: events.append("session.log"))
    monkeypatch.setattr(cli, "current_timestamp", lambda: events.append("timestamp") or "2026-05-21T00:00:00+08:00")

    return recorder


def test_cli_does_not_import_file_normalizer_for_recorded_opus():
    assert not hasattr(cli, "normalize_wav")


def test_run_listen_mutes_between_start_and_stop_then_restores_before_processing(monkeypatch, tmp_path):
    events = []
    _patch_listen_dependencies(monkeypatch, events, tmp_path, duration_seconds=1.25)

    run_listen(_listen_args(), _settings(), FakePipeline(events))

    assert events.index("recorder.start") < events.index("guard.mute") < events.index("recorder.stop")
    assert events.index("recorder.stop") < events.index("guard.restore") < events.index("active_app")
    assert events.index("active_app") < events.index("pipeline.process:listen.ogg:Notepad:True")


def test_run_listen_short_recording_restores_output_and_skips_pipeline(monkeypatch, tmp_path):
    events = []
    _patch_listen_dependencies(monkeypatch, events, tmp_path, duration_seconds=0.25)

    run_listen(_listen_args(), _settings(), FakePipeline(events))

    assert events.index("recorder.stop") < events.index("guard.restore") < events.index("active_app")
    assert "guard.restore" in events
    assert "session.log" in events
    assert not any(event.startswith("pipeline.process") for event in events)


def test_run_listen_keyboard_interrupt_while_recording_cancels_and_restores(monkeypatch, tmp_path):
    events = []
    _patch_listen_dependencies(monkeypatch, events, tmp_path, duration_seconds=1.25, interrupt=True)

    run_listen(_listen_args(), _settings(), FakePipeline(events))

    assert events.index("recorder.start") < events.index("guard.mute")
    assert events.index("guard.mute") < events.index("recorder.cancel") < events.index("guard.restore")
    assert not any(event.startswith("pipeline.process") for event in events)


def test_run_listen_restores_output_when_stop_to_opus_fails_after_recording_clears(
    monkeypatch, tmp_path
):
    events = []
    _patch_listen_dependencies(
        monkeypatch,
        events,
        tmp_path,
        duration_seconds=1.25,
        recorder_class=FakeRecorderStopFails,
    )

    try:
        run_listen(_listen_args(), _settings(), FakePipeline(events))
    except RuntimeError as exc:
        assert str(exc) == "stop failed"
    else:
        raise AssertionError("Expected stop failure to propagate")

    assert events.count("recorder.start") == 1
    assert events.count("recorder.stop") == 1
    assert events.index("recorder.start") < events.index("guard.mute") < events.index("recorder.stop")
    assert events.index("recorder.stop") < events.index("guard.restore")
    assert not any(event.startswith("pipeline.process") for event in events)


def test_record_opus_with_output_muted_mutes_records_and_restores(tmp_path):
    events = []
    opus_path = tmp_path / "recorded.ogg"

    def record_func(seconds, *, sample_rate, channels):
        events.append(f"record:{seconds}:{sample_rate}:{channels}")
        return opus_path

    result = cli.record_opus_with_output_muted(
        1.25,
        sample_rate=16000,
        channels=1,
        output_guard=FakeOutputGuard(events),
        record_func=record_func,
    )

    assert result == opus_path
    assert events == ["guard.mute", "record:1.25:16000:1", "guard.restore"]


def test_record_opus_with_output_muted_restores_and_propagates_recording_errors():
    events = []

    def record_func(seconds, *, sample_rate, channels):
        events.append("record.raises")
        raise RuntimeError("microphone failed")

    try:
        cli.record_opus_with_output_muted(
            1.0,
            sample_rate=16000,
            channels=1,
            output_guard=FakeOutputGuard(events),
            record_func=record_func,
        )
    except RuntimeError as exc:
        assert str(exc) == "microphone failed"
    else:
        raise AssertionError("Expected recording error to propagate")

    assert events == ["guard.mute", "record.raises", "guard.restore"]


def test_python_module_entrypoint_exposes_main():
    assert callable(entrypoint.main)


def test_cli_has_listen_command():
    parser = build_parser()

    args = parser.parse_args(["listen", "--no-llm", "--no-paste"])

    assert args.command == "listen"
    assert args.no_llm is True
    assert args.no_paste is True


def test_listen_parser_accepts_min_seconds_override():
    parser = build_parser()

    args = parser.parse_args(["listen", "--min-seconds", "1.25"])

    assert args.min_seconds == 1.25


def test_listen_parser_accepts_notify_mode():
    parser = build_parser()

    args = parser.parse_args(["listen", "--notify", "overlay"])

    assert args.notify == "overlay"


def test_listen_parser_leaves_notify_unset_for_settings_default():
    parser = build_parser()

    args = parser.parse_args(["listen"])

    assert args.notify is None


def test_run_listen_uses_settings_notify_when_arg_is_unset(monkeypatch, tmp_path):
    events = []
    _patch_listen_dependencies(monkeypatch, events, tmp_path, duration_seconds=1.25)
    monkeypatch.setattr(cli, "create_notifier", lambda notify: events.append(f"notifier:{notify}") or FakeNotifier(events))

    run_listen(_listen_args(notify=None), _settings(notify="toast"), FakePipeline(events))

    assert "notifier:toast" in events


def test_logs_parser_accepts_today_limit_json_and_open_dir():
    parser = build_parser()

    args = parser.parse_args(["logs", "--today", "--limit", "5", "--json", "--open-dir"])

    assert args.command == "logs"
    assert args.today is True
    assert args.limit == 5
    assert args.json is True
    assert args.open_dir is True


def test_logs_parser_accepts_last_flag():
    parser = build_parser()

    args = parser.parse_args(["logs", "--last", "--json"])

    assert args.command == "logs"
    assert args.last is True
    assert args.json is True


def test_cli_has_tray_command():
    parser = build_parser()

    args = parser.parse_args(["tray"])

    assert args.command == "tray"


def test_memory_add_parser_accepts_term_correction():
    parser = build_parser()
    args = parser.parse_args(
        ["memory", "add", "--type", "term", "--wrong", "cue and", "--correct", "Qwen"]
    )

    assert args.command == "memory"
    assert args.memory_command == "add"
    assert args.type == "term"
    assert args.wrong == "cue and"
    assert args.correct == "Qwen"


def test_memory_learn_parser_accepts_from_last_corrected_text():
    parser = build_parser()
    args = parser.parse_args(["memory", "learn", "--from-last", "--corrected", "Qwen is ready"])

    assert args.command == "memory"
    assert args.memory_command == "learn"
    assert args.from_last is True
    assert args.corrected == "Qwen is ready"


def test_should_process_recording_enforces_min_duration():
    assert should_process_recording(0.69, min_seconds=0.7) is False
    assert should_process_recording(0.7, min_seconds=0.7) is True


def test_describe_pipeline_result_explains_empty_transcript():
    message = describe_pipeline_result(
        PipelineResult(
            status="empty_transcript",
            raw_text="",
            final_text="",
            language="zh",
            duration=1.2,
            transcribe_time=0.3,
        )
    )

    assert "No text recognized" in message
    assert "status=empty_transcript" in message
    assert "language=zh" in message


def test_describe_pipeline_status_is_overlay_friendly_for_inserted_text():
    message = describe_pipeline_status(
        PipelineResult(status="inserted", raw_text="raw", final_text="final")
    )

    assert message == "Inserted text."


def test_describe_pipeline_status_is_overlay_friendly_for_empty_transcript():
    message = describe_pipeline_status(
        PipelineResult(status="empty_transcript", raw_text="", final_text="")
    )

    assert message == "No text recognized."


def test_select_recent_records_returns_latest_first_with_limit():
    records = [
        {"completed_at": "1"},
        {"completed_at": "2"},
        {"completed_at": "3"},
    ]

    assert select_recent_records(records, limit=2) == [{"completed_at": "3"}, {"completed_at": "2"}]


def test_format_log_summary_includes_debug_fields():
    lines = format_log_summary(
        [
            {
                "completed_at": "2026-05-15T09:30:04+08:00",
                "audio": {"seconds": 4.2, "path": "C:/Temp/voicetype-test.ogg"},
                "app_name": "notepad",
                "asr": {
                    "status": "inserted",
                    "language": "zh",
                    "transcribe_time": 0.3,
                    "final_text": "hello world",
                },
                "pasted": True,
            }
        ],
        limit=10,
    )

    assert lines == [
        "2026-05-15T09:30:04+08:00 | app=notepad | 4.20s | inserted | zh | asr=0.30s | pasted=yes | hello world | C:/Temp/voicetype-test.ogg"
    ]


def test_format_log_summary_explains_missing_records():
    assert format_log_summary([], limit=10) == ["[VoiceType] No session records found."]
