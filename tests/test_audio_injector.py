from pathlib import Path

from voicetype.audio import ToggleRecorder, record_wav
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
    assert stream.kwargs["samplerate"] == 16000
    assert stream.kwargs["channels"] == 1
    assert stream.kwargs["dtype"] == "float32"
    assert calls[0] == "start"
    assert calls[1] == "stop"
    assert calls[2] == "close"
    assert calls[3][0] == "write"
    assert calls[3][1] == tmp_path / "toggle.wav"
    assert calls[3][3] == 16000


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
