from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf

OPUS_SUFFIX = ".ogg"
OPUS_FORMAT = "OGG"
OPUS_SUBTYPE = "OPUS"


@dataclass(frozen=True)
class AudioNormalization:
    applied: bool
    gain: float
    peak_before: float
    peak_after: float


@dataclass(frozen=True)
class AudioCleanupResult:
    deleted: list[Path]
    failed: list[tuple[Path, str]]


def record_opus(seconds: float, *, sample_rate: int, channels: int) -> Path:
    frames = int(seconds * sample_rate)
    recording = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="float32")
    sd.wait()
    temp = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=OPUS_SUFFIX, delete=False)
    temp.close()
    path = Path(temp.name)
    normalized, _normalization = normalize_audio_samples(recording)
    write_opus_file(path, normalized, sample_rate)
    return path


def normalize_audio_samples(
    samples,
    *,
    target_peak: float = 0.8,
    max_gain: float = 50.0,
) -> tuple[np.ndarray, AudioNormalization]:
    audio = np.asarray(samples, dtype="float32")
    peak_before = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak_before <= 0:
        return audio, AudioNormalization(applied=False, gain=1.0, peak_before=0.0, peak_after=0.0)

    gain = min(target_peak / peak_before, max_gain)
    if gain <= 1.0:
        return audio, AudioNormalization(
            applied=False,
            gain=1.0,
            peak_before=peak_before,
            peak_after=peak_before,
        )

    normalized = np.clip(audio * gain, -1.0, 1.0)
    peak_after = float(np.max(np.abs(normalized))) if normalized.size else 0.0
    return normalized, AudioNormalization(
        applied=True,
        gain=gain,
        peak_before=peak_before,
        peak_after=peak_after,
    )


def write_opus_file(path: str | Path, audio, sample_rate: int) -> None:
    sf.write(Path(path), audio, sample_rate, format=OPUS_FORMAT, subtype=OPUS_SUBTYPE)


def cleanup_old_temp_audio(
    *,
    temp_dir: str | Path | None = None,
    now: datetime | None = None,
) -> AudioCleanupResult:
    cleanup_dir = Path(temp_dir) if temp_dir is not None else Path(tempfile.gettempdir())
    current_time = now or datetime.now()
    cutoff = current_time.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    deleted: list[Path] = []
    failed: list[tuple[Path, str]] = []

    for pattern in ("voicetype-*.ogg", "voicetype-*.wav"):
        for path in sorted(cleanup_dir.glob(pattern)):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    deleted.append(path)
            except OSError as exc:
                failed.append((path, str(exc)))

    return AudioCleanupResult(deleted=deleted, failed=failed)


class ToggleRecorder:
    def __init__(self, *, sample_rate: int, channels: int) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks = []
        self._stream = None
        self.is_recording = False
        self.last_normalization: AudioNormalization | None = None

    def start(self) -> None:
        if self.is_recording:
            return

        self._chunks = []
        self.last_normalization = None
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._on_audio,
        )
        self._stream.start()
        self.is_recording = True

    def stop_to_opus(self) -> Path:
        if not self.is_recording or self._stream is None:
            raise RuntimeError("Recorder is not running")

        self._stream.stop()
        self._stream.close()
        self._stream = None
        self.is_recording = False

        temp = tempfile.NamedTemporaryFile(prefix="voicetype-", suffix=OPUS_SUFFIX, delete=False)
        temp.close()
        path = Path(temp.name)
        normalized, normalization = normalize_audio_samples(self._recording_array())
        self.last_normalization = normalization
        write_opus_file(path, normalized, self.sample_rate)
        return path

    def cancel(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._stream = None
        self.is_recording = False

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
