from pathlib import Path
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf


def record_wav(seconds: float, *, sample_rate: int, channels: int) -> Path:
    frames = int(seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="float32")
    sd.wait()
    temp = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=".wav", delete=False)
    temp.close()
    path = Path(temp.name)
    sf.write(path, recording, sample_rate)
    return path


class ToggleRecorder:
    def __init__(self, *, sample_rate: int, channels: int) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks = []
        self._stream = None
        self.is_recording = False

    def start(self) -> None:
        if self.is_recording:
            return

        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._on_audio,
        )
        self._stream.start()
        self.is_recording = True

    def stop_to_wav(self) -> Path:
        if not self.is_recording or self._stream is None:
            raise RuntimeError("Recorder is not running")

        self._stream.stop()
        self._stream.close()
        self._stream = None
        self.is_recording = False

        temp = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=".wav", delete=False)
        temp.close()
        path = Path(temp.name)
        sf.write(path, self._recording_array(), self.sample_rate)
        return path

    def _on_audio(self, indata, frames, time_info, status) -> None:
        self._capture(indata)

    def _capture(self, indata) -> None:
        self._chunks.append(np.array(indata, dtype="float32", copy=True))

    def _recording_array(self):
        if not self._chunks:
            return np.zeros((0, self.channels), dtype="float32")
        return np.concatenate(self._chunks, axis=0)
