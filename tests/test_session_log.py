import json
from datetime import date, datetime
from pathlib import Path

from voicetype.audio import AudioNormalization
from voicetype.pipeline import PipelineResult
from voicetype.session_log import (
    SessionLogger,
    build_listen_session_record,
    default_log_dir,
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
    )

    assert record["event"] == "listen_segment"
    assert record["audio"]["path"] == "C:/Temp/voicetype-test.wav"
    assert record["audio"]["bytes"] == 12345
    assert record["normalization"]["applied"] is True
    assert record["asr"]["status"] == "inserted"
    assert record["asr"]["language"] == "zh"
    assert record["pasted"] is True
