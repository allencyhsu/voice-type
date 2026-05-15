from pathlib import Path

from datetime import datetime

from voicetype.audio import ToggleRecorder, cleanup_old_temp_audio, normalize_wav, record_wav
from voicetype.injector import TextInjector


def test_record_wav_writes_sounddevice_audio_to_temp_file(monkeypatch, tmp_path):
    calls = {}

    def fake_rec(frames, *, samplerate, channels, dtype):
        calls["rec"] = {
            "frames": frames,
            "samplerate": samplerate,
            "channels": channels,
            "dtype": dtype,
        }
        return [[0.0]]

    def fake_wait():
        calls["wait"] = True

    def fake_write(path, recording, sample_rate):
        calls["write"] = {
            "path": Path(path),
            "recording": recording,
            "sample_rate": sample_rate,
        }

    monkeypatch.setattr("voicetype.audio.tempfile.NamedTemporaryFile", lambda **kwargs: _FakeTemp(tmp_path / "sample.wav"))
    monkeypatch.setattr("voicetype.audio.sd.rec", fake_rec)
    monkeypatch.setattr("voicetype.audio.sd.wait", fake_wait)
    monkeypatch.setattr("voicetype.audio.sf.write", fake_write)

    path = record_wav(2.0, sample_rate=16000, channels=1)

    assert path == tmp_path / "sample.wav"
    assert calls["rec"] == {
        "frames": 32000,
        "samplerate": 16000,
        "channels": 1,
        "dtype": "float32",
    }
    assert calls["wait"] is True
    assert calls["write"]["path"] == tmp_path / "sample.wav"
    assert calls["write"]["sample_rate"] == 16000


def test_toggle_recorder_starts_and_stops_to_wav(monkeypatch, tmp_path):
    calls = []
    stream = _FakeStream(calls)

    monkeypatch.setattr("voicetype.audio.sd.InputStream", lambda **kwargs: stream.capture_kwargs(kwargs))
    monkeypatch.setattr("voicetype.audio.tempfile.NamedTemporaryFile", lambda **kwargs: _FakeTemp(tmp_path / "toggle.wav"))
    monkeypatch.setattr("voicetype.audio.sf.write", lambda path, recording, sample_rate: calls.append(("write", Path(path), recording, sample_rate)))

    recorder = ToggleRecorder(sample_rate=16000, channels=1)
    recorder.start()
    recorder._capture([[0.1], [0.2]])
    path = recorder.stop_to_wav()

    assert path == tmp_path / "toggle.wav"
    assert recorder.recorded_frames == 2
    assert recorder.duration_seconds == 2 / 16000
    assert stream.kwargs["samplerate"] == 16000
    assert stream.kwargs["channels"] == 1
    assert stream.kwargs["dtype"] == "float32"
    assert calls[0] == "start"
    assert calls[1] == "stop"
    assert calls[2] == "close"
    assert calls[3][0] == "write"
    assert calls[3][1] == tmp_path / "toggle.wav"
    assert calls[3][3] == 16000


def test_toggle_recorder_cancel_closes_active_stream(monkeypatch):
    calls = []
    stream = _FakeStream(calls)

    monkeypatch.setattr("voicetype.audio.sd.InputStream", lambda **kwargs: stream.capture_kwargs(kwargs))

    recorder = ToggleRecorder(sample_rate=16000, channels=1)
    recorder.start()
    recorder.cancel()

    assert recorder.is_recording is False
    assert calls == ["start", "stop", "close"]


def test_text_injector_copies_text_and_pastes(monkeypatch):
    calls = []
    monkeypatch.setattr("voicetype.injector.pyperclip.copy", lambda text: calls.append(("copy", text)))
    monkeypatch.setattr("voicetype.injector.time.sleep", lambda seconds: calls.append(("sleep", seconds)))
    monkeypatch.setattr("voicetype.injector.pyautogui.hotkey", lambda *keys: calls.append(("hotkey", keys)))

    TextInjector().paste("hello")

    assert calls == [
        ("copy", "hello"),
        ("sleep", 0.05),
        ("hotkey", ("ctrl", "v")),
    ]


def test_normalize_wav_boosts_quiet_audio(tmp_path):
    path = tmp_path / "quiet.wav"
    sf_data = [[0.01], [-0.02], [0.0]]
    import soundfile as sf

    sf.write(path, sf_data, 16000)

    result = normalize_wav(path, target_peak=0.8, max_gain=50.0)
    boosted, sample_rate = sf.read(path, dtype="float32", always_2d=True)

    assert sample_rate == 16000
    assert result.applied is True
    assert result.gain > 1
    assert result.peak_before > 0
    assert abs(float(abs(boosted).max()) - 0.8) < 0.01


def test_cleanup_old_temp_audio_removes_files_before_local_midnight(tmp_path):
    old_file = tmp_path / "voicetype-old.wav"
    today_file = tmp_path / "voicetype-today.wav"
    other_file = tmp_path / "not-voicetype.wav"
    for path in (old_file, today_file, other_file):
        path.write_bytes(b"wav")

    old_time = datetime(2026, 5, 14, 23, 59).timestamp()
    today_time = datetime(2026, 5, 15, 0, 1).timestamp()
    other_time = datetime(2026, 5, 14, 1, 0).timestamp()
    old_file.touch()
    today_file.touch()
    other_file.touch()
    import os

    os.utime(old_file, (old_time, old_time))
    os.utime(today_file, (today_time, today_time))
    os.utime(other_file, (other_time, other_time))

    result = cleanup_old_temp_audio(temp_dir=tmp_path, now=datetime(2026, 5, 15, 12, 0))

    assert result.deleted == [old_file]
    assert old_file.exists() is False
    assert today_file.exists() is True
    assert other_file.exists() is True


class _FakeTemp:
    def __init__(self, path: Path) -> None:
        self.name = str(path)

    def close(self) -> None:
        pass


class _FakeStream:
    def __init__(self, calls):
        self.calls = calls
        self.kwargs = {}

    def capture_kwargs(self, kwargs):
        self.kwargs = kwargs
        return self

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def close(self):
        self.calls.append("close")
