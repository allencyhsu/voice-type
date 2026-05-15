from dataclasses import dataclass
from pathlib import Path
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf


@dataclass(frozen=True)
class AudioNormalization:
    applied: bool
    gain: float
    peak_before: float
    peak_after: float


def record_wav(seconds: float, *, sample_rate: int, channels: int) -> Path:
    frames = int(seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="float32")
    sd.wait()
    temp = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=".wav", delete=False)
    temp.close()
    path = Path(temp.name)
    sf.write(path, recording, sample_rate)
    return path


def normalize_wav(path: str | Path, *, target_peak: float = 0.8, max_gain: float = 50.0) -> AudioNormalization:
    wav_path = Path(path)
    audio, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    peak_before = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak_before <= 0:
        return AudioNormalization(applied=False, gain=1.0, peak_before=0.0, peak_after=0.0)

    gain = min(target_peak / peak_before, max_gain)
    if gain <= 1.0:
        return AudioNormalization(
            applied=False,
            gain=1.0,
            peak_before=peak_before,
            peak_after=peak_before,
        )

    normalized = np.clip(audio * gain, -1.0, 1.0)
    sf.write(wav_path, normalized, sample_rate)
    peak_after = float(np.max(np.abs(normalized))) if normalized.size else 0.0
    return AudioNormalization(
        applied=True,
        gain=gain,
        peak_before=peak_before,
        peak_after=peak_after,
    )


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

    @property
    def recorded_frames(self) -> int:
        return int(sum(chunk.shape[0] for chunk in self._chunks))

    @property
    def duration_seconds(self) -> float:
        return self.recorded_frames / self.sample_rate

    def _on_audio(self, indata, frames, time_info, status) -> None:
        self._capture(indata)

    def _capture(self, indata) -> None:
        self._chunks.append(np.array(indata, dtype="float32", copy=True))

    def _recording_array(self):
        if not self._chunks:
            return np.zeros((0, self.channels), dtype="float32")
        return np.concatenate(self._chunks, axis=0)
