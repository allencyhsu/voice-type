from pathlib import Path

from voicetype.audio import record_wav
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
