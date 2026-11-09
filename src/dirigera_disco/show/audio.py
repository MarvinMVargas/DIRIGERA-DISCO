import threading
import time

import numpy as np

BEAT_COOLDOWN_SECONDS = 0.22


def is_beat(rms: float, previous: float, baseline: float, since_last: float) -> bool:
    """True when loudness jumps above the recent level, once per hit."""
    rise = rms - previous
    return rise > 0.008 and rms > max(0.012, baseline * 1.35) and since_last >= BEAT_COOLDOWN_SECONDS


def brightness_for(rms: float) -> int:
    """Map microphone loudness to a bulb level from 15 to 100."""
    level = min(1.0, max(0.0, rms) * 10)
    stepped = round((15 + level * 85) / 5) * 5
    return int(min(100, max(15, stepped)))


class MicLevel:
    """Latest microphone loudness and a simple onset flag."""

    def __init__(self) -> None:
        self._rms = 0.0
        self._baseline = 0.0
        self._beats = 0
        self._last_beat = 0.0
        self._onset = False
        self._recent: list[float] = []
        self._lock = threading.Lock()
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        def callback(indata, frames, time_info, status) -> None:
            rms = float(np.sqrt(np.mean(np.square(indata))))
            now = time.monotonic()
            with self._lock:
                self._recent.append(rms)
                if len(self._recent) > 16:
                    self._recent.pop(0)
                average = sum(self._recent) / len(self._recent)
                self._onset = rms > average * 1.8 and rms > 0.02
                if is_beat(rms, self._rms, self._baseline, now - self._last_beat):
                    self._beats += 1
                    self._last_beat = now
                self._baseline = self._baseline * 0.92 + rms * 0.08
                self._rms = rms

        self._stream = sd.InputStream(
            channels=1,
            samplerate=44100,
            blocksize=1024,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def rms(self) -> float:
        with self._lock:
            return self._rms

    def onset(self) -> bool:
        with self._lock:
            return self._onset

    def beats(self) -> int:
        with self._lock:
            return self._beats

    def brightness(self) -> int:
        return brightness_for(self.rms())
