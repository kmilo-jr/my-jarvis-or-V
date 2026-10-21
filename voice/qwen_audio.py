"""Conservative boundary silence trimming for independently generated phrases."""
import numpy as np


def shorten_phrase_silence(audio, sample_rate):
    """Keep 80 ms before speech and 160 ms after it, without changing speech.

    Only boundary silence is removed. Internal pauses, amplitude and playback
    speed remain untouched. Quiet/empty phrases are deliberately left intact.
    """
    data = np.asarray(audio)
    if sample_rate <= 0 or data.size == 0 or not np.isfinite(data).all():
        return audio
    mono = data if data.ndim == 1 else np.max(np.abs(data), axis=1)
    if np.max(np.abs(mono)) < .01:
        return audio
    frame = max(1, round(sample_rate * .01))
    rms = np.array([np.sqrt(np.mean(mono[i:i + frame].astype(np.float64) ** 2))
                    for i in range(0, len(mono), frame)])
    active = np.flatnonzero(rms > .0005)
    if not active.size:
        return audio
    start = max(0, int(active[0]) * frame - round(sample_rate * .08))
    end = min(len(data), (int(active[-1]) + 1) * frame + round(sample_rate * .16))
    return data[start:end]
