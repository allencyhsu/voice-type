from pathlib import Path
import tempfile

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
