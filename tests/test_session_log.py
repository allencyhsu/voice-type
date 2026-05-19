import json
from datetime import date, datetime
from pathlib import Path

from voicetype.audio import AudioNormalization
from voicetype.pipeline import PipelineResult
from voicetype.session_log import (
    SessionLogger,
    build_listen_session_record,
    default_log_dir,
    latest_session_record,
    log_path_for,
    read_session_records,
)


def test_default_log_dir_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_log_dir() == tmp_path / "VoiceType" / "logs"


def test_session_logger_appends_jsonl_records(tmp_path):
    now = datetime(2026, 5, 15, 9, 30, 0)
    logger = SessionLogger(log_dir=tmp_path, now=lambda: now)

    logger.append({"event": "listen_segment", "final_text": "測試"})

    log_path = tmp_path / "2026-05-15.jsonl"
    assert json.loads(log_path.read_text(encoding="utf-8").strip()) == {
        "event": "listen_segment",
        "final_text": "測試",
    }


def test_log_path_for_uses_requested_day(tmp_path):
    assert log_path_for(date(2026, 5, 15), log_dir=tmp_path) == tmp_path / "2026-05-15.jsonl"


def test_read_session_records_returns_jsonl_records(tmp_path):
    log_path = tmp_path / "2026-05-15.jsonl"
    log_path.write_text(
        '{"event":"listen_segment","asr":{"status":"inserted"}}\n'
        '\n'
        '{"event":"listen_segment","asr":{"status":"empty_transcript"}}\n',
        encoding="utf-8",
    )

    records = read_session_records(day=date(2026, 5, 15), log_dir=tmp_path)

    assert [record["asr"]["status"] for record in records] == ["inserted", "empty_transcript"]


def test_read_session_records_returns_empty_list_when_log_missing(tmp_path):
    records = read_session_records(day=date(2026, 5, 15), log_dir=tmp_path)

    assert records == []


def test_latest_session_record_returns_most_recent_record(tmp_path):
    log_path = tmp_path / "2026-05-15.jsonl"
    log_path.write_text(
        '{"completed_at":"2026-05-15T09:00:00+08:00"}\n'
        '{"completed_at":"2026-05-15T09:10:00+08:00"}\n',
        encoding="utf-8",
    )

    record = latest_session_record(day=date(2026, 5, 15), log_dir=tmp_path)

    assert record == {"completed_at": "2026-05-15T09:10:00+08:00"}


def test_latest_session_record_returns_none_when_log_missing(tmp_path):
    assert latest_session_record(day=date(2026, 5, 15), log_dir=tmp_path) is None


def test_build_listen_session_record_keeps_audio_and_result_details():
    record = build_listen_session_record(
        started_at="2026-05-15T09:30:00+08:00",
        completed_at="2026-05-15T09:30:04+08:00",
        audio_path=Path("C:/Temp/voicetype-test.wav"),
        audio_seconds=4.2,
        audio_bytes=12345,
        normalization=AudioNormalization(
            applied=True,
            gain=50.0,
            peak_before=0.01,
            peak_after=0.5,
        ),
        result=PipelineResult(
            status="inserted",
            raw_text="raw",
            final_text="final",
            language="zh",
            duration=4.1,
            transcribe_time=0.3,
        ),
        pasted=True,
        app_name="notepad",
    )

    assert record["event"] == "listen_segment"
    assert record["app_name"] == "notepad"
    assert record["audio"]["path"] == "C:/Temp/voicetype-test.wav"
    assert record["audio"]["bytes"] == 12345
    assert record["normalization"]["applied"] is True
    assert record["asr"]["status"] == "inserted"
    assert record["asr"]["language"] == "zh"
    assert record["pasted"] is True


def test_build_listen_session_record_includes_memory_metadata():
    record = build_listen_session_record(
        started_at="2026-05-19T10:00:00+08:00",
        completed_at="2026-05-19T10:00:03+08:00",
        audio_path=Path("C:/Temp/voicetype-test.wav"),
        audio_seconds=3.0,
        audio_bytes=1234,
        normalization=None,
        result=PipelineResult(
            status="inserted",
            raw_text="cue and",
            final_text="Qwen",
            correction_memory_ids=["entry-1"],
            correction_memory_count=1,
            whisper_hotwords=["Qwen"],
            whisper_hotword_count_before=3,
            whisper_hotword_count_after=1,
        ),
        pasted=True,
        app_name="notepad",
    )

    assert record["memory"] == {
        "correction_ids": ["entry-1"],
        "correction_count": 1,
        "correction_error": None,
        "whisper_hotwords": ["Qwen"],
        "whisper_hotword_count_before": 3,
        "whisper_hotword_count_after": 1,
    }
