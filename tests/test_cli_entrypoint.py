import voicetype.__main__ as entrypoint
from voicetype.cli import (
    build_parser,
    describe_pipeline_result,
    describe_pipeline_status,
    format_log_summary,
    select_recent_records,
    should_process_recording,
)
from voicetype.pipeline import PipelineResult


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


def test_listen_parser_defaults_to_overlay_notify_mode():
    parser = build_parser()

    args = parser.parse_args(["listen"])

    assert args.notify == "overlay"


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
                "audio": {"seconds": 4.2, "path": "C:/Temp/voicetype-test.wav"},
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
        "2026-05-15T09:30:04+08:00 | app=notepad | 4.20s | inserted | zh | asr=0.30s | pasted=yes | hello world | C:/Temp/voicetype-test.wav"
    ]


def test_format_log_summary_explains_missing_records():
    assert format_log_summary([], limit=10) == ["[VoiceType] No session records found."]
