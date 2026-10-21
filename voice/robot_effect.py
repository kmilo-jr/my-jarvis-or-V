"""Local, duration-preserving robot layer mixed with the original TTS voice."""
import os
import tempfile
from pathlib import Path
from functools import lru_cache

import numpy as np
from scipy.signal import butter, sosfilt, sawtooth


@lru_cache(maxsize=4)
def _filters(rate):
    """Reuse coefficients, never filter state or the user's audio."""
    edges = np.geomspace(90, min(6500, rate * .44), 13)
    return (butter(2, 35, fs=rate, output='sos'),
            tuple(butter(2, [low, high], btype='bandpass', fs=rate, output='sos')
                  for low, high in zip(edges[:-1], edges[1:])),
            butter(2, 330, fs=rate, output='sos'),
            butter(2, [650, 2300], btype='bandpass', fs=rate, output='sos'),
            butter(2, 65, btype='highpass', fs=rate, output='sos'))


def _pitch_layer(x, rate, semitones=-1.4):
    # Two variable delay lines, crossfaded at their resets (no playback slowdown).
    ratio = 2 ** (semitones / 12)
    span = .04 * rate
    t = np.arange(len(x), dtype=np.float64)
    phase = (t * (1 - ratio) / span) % 1
    result = np.zeros_like(x)
    for shift in (0, .5):
        p = (phase + shift) % 1
        weight = np.sin(np.pi * p) ** 2
        result += weight * np.interp(t - (p * span + .003 * rate), t, x, left=0)
    return result


def process_audio(audio, rate, intensity=.35):
    """Return float32 PCM; intensity=0 is exact bypass. Supports mono/stereo."""
    amount = float(intensity)
    if not np.isfinite(amount) or not 0 <= amount <= 1:
        raise ValueError('Intensidade deve estar entre 0 e 1.')
    source = np.asarray(audio, dtype=np.float32)
    if source.ndim not in (1, 2) or not np.all(np.isfinite(source)):
        raise ValueError('Áudio inválido para o efeito.')
    if amount == 0 or source.size == 0:
        return source.copy()
    if rate < 16000:
        raise ValueError('O efeito requer áudio de pelo menos 16 kHz.')
    if source.ndim == 2:
        return np.column_stack([process_audio(source[:, c], rate, amount)
                                for c in range(source.shape[1])])
    x = source.astype(np.float64)
    if np.max(np.abs(x)) < 1e-8:
        return source.copy()
    shifted = _pitch_layer(x, rate)
    t = np.arange(len(x)) / rate
    # Genuine 12-band envelope vocoder, with a harmonic carrier and no idle noise.
    carrier = .65 * sawtooth(2 * np.pi * 83 * t) + .35 * sawtooth(2 * np.pi * 127 * t)
    envelope_filter, bands, bass_filter, mid_filter, high_filter = _filters(rate)
    robot = np.zeros_like(x)
    for band in bands:
        analysis = sosfilt(band, shifted)
        envelope = np.maximum(0, sosfilt(envelope_filter, np.abs(analysis)))
        synth = sosfilt(band, carrier)
        rms = np.sqrt(np.mean(synth * synth))
        robot += envelope * synth / max(rms, .015)
    # Preserve most of the original articulation inside the wet layer as well.
    wet = .65 * shifted + .35 * robot
    bass = sosfilt(bass_filter, wet)
    mids = sosfilt(mid_filter, wet)
    wet = sosfilt(high_filter, wet + .25 * bass + .12 * mids)
    wet = np.tanh(1.65 * wet) / 1.65
    spatial = wet.copy()
    for seconds, gain in ((.019, .15), (.037, -.10), (.061, .08)):
        delay = round(seconds * rate)
        if delay < len(wet):
            spatial[delay:] += gain * wet[:-delay]
    # Leave the same duration, tapering only the wet tail to avoid boundary clicks.
    fade = min(round(.008 * rate), len(wet))
    spatial[-fade:] *= np.linspace(1, 0, fade)
    out = (1 - amount) * x + amount * spatial
    peak = float(np.max(np.abs(out)))
    if peak > .98:
        out *= .98 / peak
    return out.astype(np.float32)


def process_file(path, intensity=.35):
    """Create an independent WAV. Caller owns it; never overwrite source/cache."""
    import soundfile as sf
    audio, rate = sf.read(path, dtype='float32', always_2d=True)
    audio = process_audio(audio, rate, intensity)
    fd, result = tempfile.mkstemp(prefix='v_robot_', suffix='.wav')
    os.close(fd)
    try:
        sf.write(result, audio, rate, subtype='PCM_16')
        return result
    except Exception:
        Path(result).unlink(missing_ok=True)
        raise
