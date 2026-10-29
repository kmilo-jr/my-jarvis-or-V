from __future__ import annotations
from app_paths import ROOT

from collections import deque, OrderedDict
import os
import math
import queue
import tempfile
import subprocess
import re
import threading
import time
import wave
from pathlib import Path
from typing import Callable

from .endpoint import AdaptiveEndpointDetector
from vlog import get_logger

log = get_logger(__name__)


class VoiceEngine:
    """Camada de voz independente do Action Core.

    Objetivo do 0.5:
      * nunca alterar o motor de ações que já funciona por texto;
      * capturar uma FRASE completa em vez de blocos cegos;
      * calibrar o ruído do ambiente automaticamente;
      * preservar o começo da fala com pre-roll;
      * reamostrar para 16 kHz antes do faster-whisper;
      * usar um modelo multilíngue mais preciso por padrão.
    """

    WHISPER_RATE = 16000

    def __init__(self, config: dict):
        self.config = config or {}
        self._model = None
        self._recognition_backend = {}
        self._model_lock = threading.Lock()
        self._transcription_lock = threading.Lock()
        self._ambient_profiles: dict[str, dict] = {}
        self._tts_queue: queue.Queue = queue.Queue(maxsize=20)
        self._tts_thread: threading.Thread | None = None
        self._tts_lock = threading.Lock()
        self._tts_speaking = threading.Event()
        self._external_audio = threading.Event()
        self._tts_epoch = 0
        self._speech_generation = threading.Event()
        self._active_cancel = self._speech_generation
        self._speech_lock = threading.Lock()
        self.last_tts_error = ""
        self.tts_status = "Pronto"
        self._qwen = None
        self._qwen_lock = threading.Lock()
        self._qwen_warmup = threading.Event()
        self._last_tts_end = 0.0
        self._piper_voice = None
        self._piper_loaded_model = None
        self._piper_lock = threading.Lock()
        self._piper_warmup_lock = threading.Lock()
        self._piper_warmup_active = threading.Event()
        # XTTS-v2 keeps the reference speaker embedding in memory after the
        # first synthesis.  Loading it lazily avoids delaying the interface
        # startup while still making subsequent replies local and consistent.
        self._xtts = None
        self._xtts_loaded_model = None
        self._xtts_loaded_reference = None
        self._xtts_lock = threading.Lock()
        self._xtts_inference_lock = threading.RLock()
        self._xtts_warmup_lock = threading.Lock()
        self._xtts_warmup_active = threading.Event()
        self._xtts_voice_cache: dict[tuple, dict] = {}
        self._xtts_voice_cache_lock = threading.Lock()
        self._xtts_audio_cache = OrderedDict()
        self._xtts_audio_cache_lock = threading.Lock()
        self.last_input_metrics: dict[str, float] = {}
        self.last_tts_metrics: dict[str, float | str] = {}
        self._eleven_session = None
        self._tts_audio_cache = OrderedDict()
        self._tts_cache_lock = threading.Lock()

        # Visual speech envelope consumed by the second interface.  This stays
        # independent from the audio backend (ElevenLabs / Edge / Piper / SAPI)
        # so the face can react consistently no matter which voice is selected.
        self._visual_speech_lock = threading.Lock()
        self._visual_speech_started = 0.0
        self._visual_speech_seed = 0.0
        self._visual_speech_text = ""

    # ------------------------------------------------------------------
    # Estado / TTS guard
    # ------------------------------------------------------------------
    def is_speaking(self) -> bool:
        # Inclui efeitos da interface (ex.: som de processamento) para que o
        # microfone contínuo não transcreva o próprio V.
        return self._tts_speaking.is_set() or self._external_audio.is_set()

    def has_pending_speech(self) -> bool:
        return not self._tts_queue.empty()

    def set_external_audio_active(self, active: bool):
        if active:
            self._external_audio.set()
        else:
            self._external_audio.clear()

    def voice_input_allowed(self) -> bool:
        cooldown = float(self.config.get("post_tts_cooldown", 1.0))
        return (not self._external_audio.is_set()) and (self.config.get("barge_in_enabled", False) or not self.is_speaking()) and (time.monotonic() - self._last_tts_end >= cooldown)

    def _begin_visual_speech(self, text: str):
        """Start a deterministic speech-energy envelope for UI animation.

        Playback start/end still come from the real TTS guard.  Inside that
        window we synthesize syllable-like energy instead of using one fixed
        sine wave, which looks much closer to real speech and works for every
        TTS backend without recording the system output.
        """
        clean = self._prepare_spoken_text(text)
        # Stable per-utterance seed; avoids Python's randomized hash().
        seed = sum((i + 1) * ord(ch) for i, ch in enumerate(clean[:240])) % 10007
        with self._visual_speech_lock:
            self._visual_speech_text = clean
            self._visual_speech_seed = float(seed) / 10007.0
            self._visual_speech_started = time.monotonic()

    def _end_visual_speech(self):
        # Keep the start time/text for a short visual release.  is_speaking()
        # is the authoritative gate, so get_speech_visual_level returns zero
        # once playback has finished and the widget performs the smooth decay.
        pass

    def get_speech_visual_level(self) -> float:
        """Return 0..1 speech energy for the animated V face.

        The envelope is tied to actual TTS playback state and uses several
        non-harmonic cadences to mimic syllables, consonant hits and pauses.
        It deliberately does not deform facial geometry.
        """
        if not self._tts_speaking.is_set():
            return 0.0
        with self._visual_speech_lock:
            started = self._visual_speech_started
            seed = self._visual_speech_seed
            text = self._visual_speech_text
        if started <= 0.0:
            return 0.0
        t = max(0.0, time.monotonic() - started)

        # Word/syllable gates with slightly irregular timing.
        cadence = (
            0.48
            + 0.24 * math.sin(t * (10.7 + seed * 1.8) + seed * 5.1)
            + 0.17 * math.sin(t * (17.9 + seed * 2.3) + 1.7)
            + 0.11 * math.sin(t * (27.1 + seed * 3.1) + seed * 9.0)
        )
        cadence = max(0.0, min(1.0, cadence))

        # A soft syllable gate prevents the old continuous rubber-band look.
        syllable = 0.5 + 0.5 * math.sin(t * (7.1 + seed * 0.9) + seed * 3.0)
        gate = 0.30 + 0.70 * (syllable ** 1.7)

        # Punctuation density makes long, punctuated replies breathe a little
        # more than short confirmations while remaining backend-agnostic.
        punct = sum(text.count(ch) for ch in ',.;:!?')
        breath = 0.92 - min(0.12, punct * 0.006)
        level = cadence * gate * breath
        return max(0.06, min(1.0, level))

    # ------------------------------------------------------------------
    # Dispositivos
    # ------------------------------------------------------------------
    def input_devices(self):
        import sounddevice as sd

        hostapis = sd.query_hostapis()
        out = []
        for idx, dev in enumerate(sd.query_devices()):
            if int(dev.get("max_input_channels", 0)) <= 0:
                continue
            rate = int(dev.get("default_samplerate") or 44100)
            host_name = ""
            try:
                host_name = hostapis[int(dev.get("hostapi", 0))].get("name", "")
            except Exception as exc:
                log.warning("nome do host de áudio indisponível (%s): %s", idx, type(exc).__name__)
            name = str(dev.get("name", f"Microfone {idx}"))
            if host_name:
                name = f"{name} · {host_name}"
            out.append((idx, name, rate))
        return out

    def _device_info(self, device_index=None):
        import sounddevice as sd
        if device_index is None:
            info = sd.query_devices(kind="input")
        else:
            info = sd.query_devices(device_index, "input")
        rate = int(float(info.get("default_samplerate") or 44100))
        return info, rate

    def _profile_key(self, device_index=None) -> str:
        info, rate = self._device_info(device_index)
        return f"{device_index!r}:{info.get('name', 'default')}:{rate}"

    # ------------------------------------------------------------------
    # DSP utilitário
    # ------------------------------------------------------------------
    @staticmethod
    def _rms(x) -> float:
        import numpy as np
        if x is None or getattr(x, "size", 0) == 0:
            return 0.0
        arr = np.asarray(x, dtype=np.float32).reshape(-1)
        return float(np.sqrt(np.mean(np.square(arr), dtype=np.float64)))

    @staticmethod
    def _peak(x) -> float:
        import numpy as np
        if x is None or getattr(x, "size", 0) == 0:
            return 0.0
        return float(np.max(np.abs(np.asarray(x, dtype=np.float32))))

    def _prepare_audio(self, x, native_rate: int):
        import numpy as np

        x = np.asarray(x, dtype=np.float32).reshape(-1)
        meta = {"native_rate": int(native_rate)}
        if x.size == 0:
            meta.update(reason="empty", peak=0.0, rms=0.0)
            return x, meta

        meta['clipping_percent'] = round(float(np.mean(np.abs(x) >= 0.98)) * 100, 2)

        # DC offset prejudica RMS e alguns codecs/drivers P2/USB.
        x = x - float(np.mean(x))
        peak = self._peak(x)
        rms = self._rms(x)
        meta.update(peak=round(peak, 6), rms=round(rms, 6))

        silence_peak = float(self.config.get("silence_peak", 0.0015))
        silence_rms = float(self.config.get("silence_rms", 0.0003))
        if peak < silence_peak and rms < silence_rms:
            meta["reason"] = "silence"
            return x, meta

        # Normaliza somente sinais baixos. Evita esmagar dinâmica e clipping.
        target_rms = float(self.config.get("target_rms", 0.075))
        max_gain = float(self.config.get("max_gain", 5.0))
        gain = 1.0
        if 0.00001 < rms < target_rms:
            gain = min(max_gain, target_rms / rms)
            # Proteção adicional pelo pico.
            if peak > 0.00001:
                gain = min(gain, 0.92 / peak)
            gain = max(1.0, gain)
            x = np.clip(x * gain, -1.0, 1.0).astype(np.float32)
        meta["gain"] = round(float(gain), 2)

        if native_rate != self.WHISPER_RATE and x.size > 1:
            # Remove frequencies above the destination Nyquist limit before
            # decimation; interpolation alone folds hiss into the speech band.
            if native_rate > self.WHISPER_RATE:
                taps = 127
                positions = np.arange(taps) - (taps - 1) / 2
                cutoff = 0.45 * self.WHISPER_RATE / native_rate
                kernel = 2 * cutoff * np.sinc(2 * cutoff * positions) * np.hamming(taps)
                kernel /= kernel.sum()
                x = np.convolve(np.pad(x, (taps // 2, taps // 2), mode="edge"), kernel, mode="valid").astype(np.float32)
            duration = x.size / float(native_rate)
            new_size = max(1, int(round(duration * self.WHISPER_RATE)))
            old_t = np.arange(x.size, dtype=np.float64) / float(native_rate)
            new_t = np.arange(new_size, dtype=np.float64) / float(self.WHISPER_RATE)
            x = np.interp(new_t, old_t, x).astype(np.float32)
        meta["whisper_rate"] = self.WHISPER_RATE
        meta["samples"] = int(x.size)
        return x, meta

    # ------------------------------------------------------------------
    # Calibração do ambiente
    # ------------------------------------------------------------------
    def calibrate_ambient(self, device_index=None, seconds=None, stop_event=None, stage_callback=None):
        """Mede apenas o ambiente e deriva limiares de fala.

        A calibração é curta e é refeita quando a voz contínua é ativada. O
        objetivo é adaptar ao microfone/ganho/ventoinha atuais, não criar uma
        biometria do usuário.
        """
        import numpy as np
        import sounddevice as sd

        seconds = float(seconds or self.config.get("calibration_seconds", 1.2))
        info, rate = self._device_info(device_index)
        sd.check_input_settings(device=device_index, channels=1, samplerate=rate, dtype="float32")
        if stage_callback:
            stage_callback("CALIBRATING")

        # Em 1.2s o bloqueio é curto; checamos cancelamento antes/depois.
        if stop_event is not None and stop_event.is_set():
            return {"cancelled": True}
        audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="float32", device=device_index, blocking=True)
        if stop_event is not None and stop_event.is_set():
            return {"cancelled": True}

        x = np.asarray(audio, dtype=np.float32).reshape(-1)
        if x.size:
            x = x - float(np.mean(x))

        frame_ms = int(self.config.get("energy_frame_ms", 40))
        frame_n = max(32, int(rate * frame_ms / 1000.0))
        levels = []
        for i in range(0, max(0, x.size - frame_n + 1), frame_n):
            levels.append(self._rms(x[i:i + frame_n]))
        if not levels:
            levels = [self._rms(x)]

        levels_np = np.asarray(levels, dtype=np.float64)
        # p60 é mais robusto que média quando há um clique/tecla durante calibração.
        noise_rms = float(np.percentile(levels_np, 60))
        noise_p90 = float(np.percentile(levels_np, 90))

        start_floor = float(self.config.get("speech_start_floor_rms", 0.0045))
        end_floor = float(self.config.get("speech_end_floor_rms", 0.0030))
        start_mult = float(self.config.get("speech_start_noise_mult", 3.2))
        end_mult = float(self.config.get("speech_end_noise_mult", 2.0))
        max_start = float(self.config.get("speech_start_max_rms", 0.08))
        max_end = float(self.config.get("speech_end_max_rms", 0.05))

        reference_noise = max(noise_rms, noise_p90 * 0.75)
        start_threshold = min(max_start, max(start_floor, reference_noise * start_mult))
        end_threshold = min(max_end, max(end_floor, reference_noise * end_mult))
        if end_threshold >= start_threshold:
            end_threshold = max(end_floor, start_threshold * 0.72)

        profile = {
            "device": str(info.get("name", "microfone padrão")),
            "native_rate": rate,
            "noise_rms": round(noise_rms, 6),
            "noise_p90": round(noise_p90, 6),
            "start_threshold": round(start_threshold, 6),
            "end_threshold": round(end_threshold, 6),
        }
        self._ambient_profiles[self._profile_key(device_index)] = profile
        return profile

    def get_ambient_profile(self, device_index=None):
        return self._ambient_profiles.get(self._profile_key(device_index))

    def invalidate_ambient(self, device_index=None):
        """Força nova calibração do microfone sem reiniciar o V."""
        if device_index is None:
            self._ambient_profiles.clear()
            return
        try:
            self._ambient_profiles.pop(self._profile_key(device_index), None)
        except Exception as exc:
            log.warning("falha ao invalidar perfil de áudio: %s", type(exc).__name__)
            self._ambient_profiles.clear()

    def validate_input_device(self, device_index=None):
        """Valida o dispositivo e retorna dados simples para a interface."""
        import sounddevice as sd
        info, rate = self._device_info(device_index)
        sd.check_input_settings(device=device_index, channels=1, samplerate=rate, dtype="float32")
        return {
            "index": device_index,
            "name": str(info.get("name", "Microfone padrão")),
            "rate": int(rate),
            "channels": int(info.get("max_input_channels", 0) or 0),
        }

    # ------------------------------------------------------------------
    # Captura de FRASE / Voice Input 2.0
    # ------------------------------------------------------------------
    def capture_phrase(self, device_index=None, stop_event=None, stage_callback=None):
        """Captura uma frase completa com pre-roll e endpoint adaptativo.

        Voice Input 2.0 usa blocos menores e dois frames de confirmação para
        reagir rápido sem disparar por um clique isolado. Frases curtas fecham
        mais cedo; frases longas ganham uma pausa um pouco maior para permitir
        respiração natural. O modo antigo continua disponível por configuração.
        """
        import numpy as np
        import sounddevice as sd

        capture_started = time.perf_counter()
        info, rate = self._device_info(device_index)
        key = self._profile_key(device_index)
        profile = self._ambient_profiles.get(key)
        if not profile:
            profile = self.calibrate_ambient(device_index, stop_event=stop_event, stage_callback=stage_callback)
        if profile.get("cancelled"):
            return np.asarray([], dtype=np.float32), {"reason": "cancelled"}

        v2 = bool(self.config.get("voice_input_v2_enabled", True))
        if v2:
            block_ms = int(self.config.get("v2_stream_block_ms", 30))
            pre_roll_s = float(self.config.get("v2_pre_roll_seconds", 0.50))
            start_blocks = int(self.config.get("v2_speech_start_blocks", 2))
            short_end_s = float(self.config.get("v2_short_end_silence_seconds", 0.38))
            long_end_s = float(self.config.get("v2_long_end_silence_seconds", 0.65))
            long_after_s = float(self.config.get("v2_long_phrase_after_seconds", 1.00))
            trailing_pad_s = float(self.config.get("v2_trailing_pad_seconds", 0.12))
        else:
            block_ms = int(self.config.get("stream_block_ms", 50))
            pre_roll_s = float(self.config.get("pre_roll_seconds", 0.62))
            start_blocks = int(self.config.get("speech_start_blocks", 1))
            legacy_end = float(self.config.get("phrase_end_silence_seconds", 0.62))
            short_end_s = legacy_end
            long_end_s = legacy_end
            long_after_s = 999.0
            trailing_pad_s = legacy_end

        blocksize = max(128, int(rate * block_ms / 1000.0))
        max_phrase_s = float(self.config.get("max_phrase_seconds", 12.0))
        min_phrase_s = float(self.config.get("min_phrase_seconds", 0.30))
        max_wait_s = float(self.config.get("listen_wait_seconds", 45.0))

        q: queue.Queue = queue.Queue(maxsize=120)
        pre_roll = deque(maxlen=max(2, int(pre_roll_s * rate / blocksize) + 1))
        frames = []
        speech_started_at = None
        start_monotonic = time.monotonic()
        max_rms = 0.0
        audio_lost = threading.Event()
        epoch_before = self._tts_epoch

        noise_ema = max(float(profile.get("noise_rms", 0.0)), 1e-6)
        start_floor = float(self.config.get("speech_start_floor_rms", 0.0038))
        end_floor = float(self.config.get("speech_end_floor_rms", 0.0026))
        start_mult = float(self.config.get("speech_start_noise_mult", 2.6))
        end_mult = float(self.config.get("speech_end_noise_mult", 1.75))
        max_start = float(self.config.get("speech_start_max_rms", 0.08))
        max_end = float(self.config.get("speech_end_max_rms", 0.05))

        detector = AdaptiveEndpointDetector(
            block_seconds=blocksize / float(rate),
            start_blocks=start_blocks,
            min_phrase_seconds=min_phrase_s,
            short_end_silence_seconds=short_end_s,
            long_end_silence_seconds=long_end_s,
            long_phrase_after_seconds=long_after_s,
        )

        def thresholds():
            st = min(max_start, max(start_floor, noise_ema * start_mult))
            et = min(max_end, max(end_floor, noise_ema * end_mult))
            if et >= st:
                et = max(end_floor, st * 0.72)
            return st, et

        def callback(indata, _frames, _time_info, status):
            if getattr(status, 'input_overflow', False):
                audio_lost.set()
            try:
                q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                audio_lost.set()
                try:
                    q.get_nowait()
                    q.put_nowait(indata[:, 0].copy())
                except Exception:
                    pass

        if stage_callback:
            stage_callback("LISTENING")
        sd.check_input_settings(device=device_index, channels=1, samplerate=rate, dtype="float32")

        with sd.InputStream(device=device_index, channels=1, samplerate=rate, dtype="float32", blocksize=blocksize, callback=callback):
            while True:
                if stop_event is not None and stop_event.is_set():
                    return np.asarray([], dtype=np.float32), {"reason": "cancelled"}
                if audio_lost.is_set():
                    return np.asarray([], dtype=np.float32), {"reason": "audio_overflow", "needs_repeat": True}
                if self._tts_epoch != epoch_before and not self.config.get("barge_in_enabled", False):
                    return np.asarray([], dtype=np.float32), {"reason": "tts_overlap"}
                if self._external_audio.is_set() or (self.is_speaking() and not self.config.get("barge_in_enabled", False)):
                    return np.asarray([], dtype=np.float32), {"reason": "tts_overlap"}
                if (not detector.speaking) and time.monotonic() - start_monotonic >= max_wait_s:
                    return np.asarray([], dtype=np.float32), {"reason": "listen_timeout"}

                try:
                    block = q.get(timeout=0.12)
                except queue.Empty:
                    continue

                block = np.asarray(block, dtype=np.float32)
                block = block - float(np.mean(block))
                level = self._rms(block)
                max_rms = max(max_rms, level)
                start_thr, end_thr = thresholds()

                if not detector.speaking:
                    pre_roll.append(block)
                    # Noise floor adapts slowly only before speech.
                    if level < start_thr * 0.80:
                        noise_ema = noise_ema * 0.988 + level * 0.012
                    event = detector.push(hot=level >= start_thr, quiet=level <= end_thr)
                    if event.started:
                        speech_started_at = time.monotonic() - start_blocks * blocksize / float(rate)
                        frames.extend(list(pre_roll))
                        pre_roll.clear()
                        if stage_callback:
                            stage_callback("HEARING SPEECH")
                else:
                    frames.append(block)
                    event = detector.push(hot=level >= start_thr, quiet=level <= end_thr)
                    speech_duration = detector.speech_time
                    if speech_duration >= max_phrase_s or event.ended:
                        break

        if audio_lost.is_set():
            return np.asarray([], dtype=np.float32), {'reason': 'audio_overflow', 'needs_repeat': True}

        raw = np.concatenate(frames).astype(np.float32) if frames else np.asarray([], dtype=np.float32)
        if raw.size == 0:
            return raw, {"reason": "no_speech"}

        # Voice 2.0 does not make Whisper process the full endpoint hangover. Keep
        # only a small natural pad after the final speech block.
        trimmed_s = 0.0
        if v2 and detector.quiet_time > trailing_pad_s:
            trimmed_s = max(0.0, detector.quiet_time - trailing_pad_s)
            trim_n = min(raw.size - 1, int(trimmed_s * rate))
            if trim_n > 0:
                raw = raw[:-trim_n]

        prepared, meta = self._prepare_audio(raw, rate)
        meta.update({
            "device": str(info.get("name", "microfone padrão")),
            "voice_input": "v2" if v2 else "legacy",
            "speech_started_at": speech_started_at,
            "captured_seconds": round(raw.size / float(rate), 2),
            "max_block_rms": round(max_rms, 6),
            "noise_rms": round(noise_ema, 6),
            "start_threshold": round(thresholds()[0], 6),
            "end_threshold": round(thresholds()[1], 6),
            "capture_total_ms": round((time.perf_counter()-capture_started)*1000.0, 1),
            "start_confirm_ms": round(start_blocks * block_ms, 1),
            "phrase_end_silence_ms": round(detector.required_silence * 1000.0, 1),
            "trailing_silence_trimmed_ms": round(trimmed_s * 1000.0, 1),
        })
        return prepared, meta

    # ------------------------------------------------------------------
    # Whisper
    # ------------------------------------------------------------------
    def preload_model(self, stage_callback=None):
        if self._model is None and stage_callback:
            stage_callback("LOADING WHISPER")
        return self._get_model()

    def transcribe(self, audio, meta=None, stage_callback=None):
        # Mic test and continuous listening can request inference concurrently.
        with self._transcription_lock:
            return self._transcribe(audio, meta, stage_callback)

    def _transcribe(self, audio, meta=None, stage_callback=None):
        transcribe_started = time.perf_counter()
        meta = dict(meta or {})
        if meta.get("reason") in {"silence", "empty", "cancelled", "tts_overlap", "no_speech", "listen_timeout", "audio_overflow"}:
            return "", meta
        if getattr(audio, "size", 0) == 0:
            meta["reason"] = "empty"
            return "", meta

        if stage_callback:
            stage_callback("TRANSCRIBING")
        model = self._get_model()

        silero_enabled = bool(self.config.get("voice_input_v2_enabled", True)) and bool(self.config.get("v2_silero_filter_enabled", True))
        kwargs = dict(
            language=self.config.get("language", "pt"),
            beam_size=int(self.config.get("beam_size", 3)),
            vad_filter=silero_enabled,
            condition_on_previous_text=False,
            temperature=0.0,
        )
        if silero_enabled:
            kwargs["vad_parameters"] = dict(
                threshold=float(self.config.get("v2_silero_threshold", 0.45)),
                neg_threshold=float(self.config.get("v2_silero_neg_threshold", 0.30)),
                min_speech_duration_ms=int(self.config.get("v2_silero_min_speech_ms", 80)),
                min_silence_duration_ms=int(self.config.get("v2_silero_min_silence_ms", 180)),
                speech_pad_ms=int(self.config.get("v2_silero_speech_pad_ms", 120)),
            )
        prompt = str(self.config.get("initial_prompt", "")).strip()
        if prompt:
            kwargs["initial_prompt"] = prompt

        try:
            segments, info = model.transcribe(audio, **kwargs)
            segments = list(segments)
            meta["silero_vad"] = "on" if silero_enabled else "off"
        except Exception as exc:
            # If ONNX/Silero is unavailable, Voice Input 2.0 falls back instead
            # of taking the whole assistant down.
            detail = f"{type(exc).__name__}: {exc}"
            from .recognition_backend import gpu_failure, load_model
            if (self._recognition_backend.get('device') == 'cuda' and gpu_failure(exc)
                    and self.config.get('recognition_cpu_fallback', True)):
                with self._model_lock:
                    self._model = None
                    model, self._recognition_backend = load_model(self.config, force_cpu=True)
                    self._model = model
                self._recognition_backend['fallback'] = type(exc).__name__
                segments, info = model.transcribe(audio, **kwargs)
                segments = list(segments)
                meta['silero_vad'] = 'on' if silero_enabled else 'off'
            elif silero_enabled and any(k in detail.lower() for k in ("onnx", "silero", "vad")):
                retry = dict(kwargs)
                retry["vad_filter"] = False
                retry.pop("vad_parameters", None)
                segments, info = model.transcribe(audio, **retry)
                segments = list(segments)
                kwargs = retry
                meta["silero_vad"] = "fallback"
                meta["silero_error"] = detail[:240]
            else:
                raise
        from .recognition import assess_segments
        assessment = assess_segments(segments, self.config)
        score = assessment['score']
        meta["recognition_retry"] = False
        # Retain the normal beam search; spend extra work only on uncertain
        # speech, never on empty/VAD-rejected audio (which invites hallucination).
        retry_beam = max(int(kwargs["beam_size"]), int(self.config.get("recognition_retry_beam_size", 5)))
        if (self.config.get("recognition_retry_enabled", True) and score is not None
                and score < float(self.config.get("recognition_retry_logprob", -0.8))
                and retry_beam > kwargs["beam_size"]
                and 'no_speech' not in assessment['issues']
                and any(s.text.strip() and float(getattr(s, "no_speech_prob", 0)) < 0.6 for s in segments)):
            meta["recognition_retry"] = True
            try:
                retry_segments, retry_info = model.transcribe(audio, **dict(kwargs, beam_size=retry_beam))
                retry_segments = list(retry_segments)
                retry_assessment = assess_segments(retry_segments, self.config)
                retry_score = retry_assessment['score']
                if retry_score is not None and retry_score > score and not retry_assessment['issues']:
                    segments, info, score = retry_segments, retry_info, retry_score
                    assessment = retry_assessment
            except Exception as exc:
                meta["recognition_retry_error"] = type(exc).__name__
        meta["recognition_logprob"] = round(score, 3) if score is not None else None
        meta['recognition_issues'] = assessment['issues']
        meta['recognition_backend'] = dict(self._recognition_backend)
        text = assessment['text'] if not assessment['issues'] else ''
        text = self._apply_term_hints(text)
        meta["language"] = getattr(info, "language", None)
        meta["language_probability"] = round(float(getattr(info, "language_probability", 0.0) or 0.0), 3)
        meta["reason"] = "uncertain_speech" if assessment['issues'] else "ok" if text else "no_text"
        meta['needs_repeat'] = bool(assessment['issues'] and 'no_speech' not in assessment['issues'])
        meta["transcription_ms"] = round((time.perf_counter()-transcribe_started)*1000.0, 1)
        self.last_input_metrics = {k: meta.get(k) for k in ("capture_total_ms", "phrase_end_silence_ms", "transcription_ms", "reason", "recognition_logprob", "recognition_retry", "recognition_issues") if meta.get(k) is not None}
        return text, meta

    def listen_and_transcribe(self, device_index=None, stop_event=None, stage_callback=None):
        audio, meta = self.capture_phrase(device_index, stop_event=stop_event, stage_callback=stage_callback)
        if meta.get("reason") in {"cancelled", "tts_overlap", "no_speech", "listen_timeout", "silence", "empty", "audio_overflow"}:
            return "", meta
        if stop_event is not None and stop_event.is_set():
            return '', dict(meta, reason='cancelled')
        text, meta = self.transcribe(audio, meta, stage_callback=stage_callback)
        if stop_event is not None and stop_event.is_set():
            return '', dict(meta, reason='cancelled')
        return text, meta

    def record_and_transcribe(self, device_index=None, seconds=None, stage_callback=None):
        """Modo diagnóstico: grava uma janela conhecida e transcreve."""
        import numpy as np
        import sounddevice as sd

        seconds = float(seconds or self.config.get("record_seconds", 4.0))
        info, rate = self._device_info(device_index)
        sd.check_input_settings(device=device_index, channels=1, samplerate=rate, dtype="float32")
        if stage_callback:
            stage_callback("LISTENING")
        epoch_before = self._tts_epoch
        audio = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype="float32", device=device_index, blocking=True)
        if self._tts_epoch != epoch_before:
            return "", {"reason": "tts_overlap", "native_rate": rate}
        prepared, meta = self._prepare_audio(np.asarray(audio, dtype=np.float32).reshape(-1), rate)
        meta["device"] = str(info.get("name", "microfone padrão"))
        if meta.get("reason") in {"silence", "empty"}:
            return "", meta
        return self.transcribe(prepared, meta, stage_callback=stage_callback)

    def test_microphone(self, device_index=None, seconds=3.5):
        return self.record_and_transcribe(device_index, seconds=seconds)

    def _get_model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from .recognition_backend import load_model
                    self._model, self._recognition_backend = load_model(self.config)
        return self._model

    def _apply_term_hints(self, text: str) -> str:
        """Corrige somente termos de domínio conhecidos do assistente.

        Não tenta 'corrigir português'. Isso evita mudar o que o usuário disse.
        O dicionário é editável em config/default.json.
        """
        out = str(text or "").strip()
        hints = self.config.get("term_replacements", {}) or {}
        for wrong, right in hints.items():
            try:
                out = re.sub(rf"(?i)(?<!\w){re.escape(str(wrong))}(?!\w)", str(right), out)
            except Exception as exc:
                log.warning("termo de substituição inválido ignorado: %s", type(exc).__name__)
                continue
        return out

    # ------------------------------------------------------------------
    # TTS
    # ------------------------------------------------------------------
    def speak_tracked(self, text: str, *, profile=None):
        receipt = {'state': 'queued', 'error': ''}
        if profile is not None:
            if profile not in {'qwen_local', 'piper'}:
                raise ValueError('Perfil de narração não suportado.')
            receipt['profile'] = profile
        self.speak(text, receipt=receipt)
        return receipt

    def _speech_profile(self, receipt):
        override = (receipt or {}).get('profile')
        if override in {'qwen_local', 'piper'}:
            return override
        return str(self.config.get('tts_profile', 'edge_tts_728')).lower()

    @staticmethod
    def _discard_speech_item(item, state='cancelled'):
        if item is not None and len(item) == 3:
            item[2].update(state=state)

    def speak(self, text: str, *, receipt=None):
        text = self._prepare_spoken_text(text)
        if not text or not bool(self.config.get("tts_enabled", True)):
            if receipt is not None:
                receipt.update(state='failed', error='Respostas por voz desabilitadas ou texto vazio.')
            return
        self.tts_status = "Carregando voz local" if self._xtts_warmup_active.is_set() or self._qwen_warmup.is_set() else "Preparando áudio"
        self._ensure_tts_thread()
        with self._speech_lock:
            item = (text, self._speech_generation) if receipt is None else (text, self._speech_generation, receipt)
            try:
                self._tts_queue.put_nowait(item)
            except queue.Full:
                log.warning("fila TTS cheia; descartando a fala mais antiga para não travar")
                try:
                    self._discard_speech_item(self._tts_queue.get_nowait(), 'dropped')
                except queue.Empty:
                    pass
                self._tts_queue.put_nowait(item)

    def stop_speaking(self):
        """Cancel current audio and queued speech, preserving future requests."""
        with self._speech_lock:
            self._speech_generation.set()
            self._speech_generation = threading.Event()
            while True:
                try:
                    self._discard_speech_item(self._tts_queue.get_nowait())
                except queue.Empty:
                    break

    @staticmethod
    def _prepare_spoken_text(text: str) -> str:
        """Limpa marcas visuais antes do TTS sem reescrever a resposta do cérebro."""
        out = str(text or "")
        # Markdown/formatacao que soa estranha quando lida em voz alta.
        out = re.sub(r"```.*?```", " ", out, flags=re.S)
        out = re.sub(r"`([^`]+)`", r"\1", out)
        out = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", out)
        out = re.sub(r"(?m)^\s*#{1,6}\s+", "", out)
        out = re.sub(r"(?m)^\s*\d+[.)]\s+", "", out)
        out = re.sub(r"\*\*([^*]+)\*\*", r"\1", out)
        out = re.sub(r"(?m)^\s*[-•]+\s+", "", out)
        out = re.sub(r"https?://\S+", "link", out)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    def _split_tts_chunks(self, text: str) -> list[str]:
        """Divide respostas longas em unidades de fala naturais.

        O primeiro trecho fica curto para reduzir o tempo ate a primeira palavra; os
        seguintes sao sintetizados em paralelo enquanto o trecho atual toca.
        """
        text = self._prepare_spoken_text(text)
        if not text:
            return []
        if not bool(self.config.get("tts_chunking", True)):
            return [text]
        max_chars = max(80, int(self.config.get("tts_chunk_max_chars", 240)))
        first_chars = min(max_chars, max(60, int(self.config.get("tts_first_chunk_chars", 100))))
        if str(self.config.get("tts_xtts_voice", "v_prime") or "").lower() in {"v_alt", "alt", "second", "2"}:
            first_chars = min(max_chars, max(48, int(self.config.get("tts_xtts_first_chunk_chars_alt", first_chars))))
        min_chars = max(8, int(self.config.get("tts_chunk_min_chars", 24)))

        # Primeiro respeita final de frase; depois quebra frase muito longa em pausas
        # de virgula/ponto e virgula para nao gerar um bloco enorme no Edge.
        sentences = [x.strip() for x in re.split(r"(?<=[.!?…])\s+", text) if x.strip()]
        parts: list[str] = []
        for sentence in sentences or [text]:
            if len(sentence) <= max_chars:
                parts.append(sentence)
                continue
            clauses = [x.strip() for x in re.split(r"(?<=[,;:])\s+", sentence) if x.strip()]
            current = ""
            for clause in clauses:
                candidate = (current + " " + clause).strip()
                if current and len(candidate) > max_chars:
                    parts.append(current)
                    current = clause
                else:
                    current = candidate
            if current:
                parts.append(current)

        # A long clause without punctuation must not hold up the first audio.
        bounded = []
        for part in parts:
            current = ""
            for word in part.split():
                limit = first_chars if not bounded else max_chars
                if current and len(current) + 1 + len(word) > limit:
                    bounded.append(current)
                    current = ""
                current = (current + " " + word).strip()
            if current:
                bounded.append(current)

        # Junta pedacos pequenos para evitar fala picotada.
        merged: list[str] = []
        for part in bounded:
            limit = first_chars if len(merged) == 1 else max_chars
            if merged and (len(merged) > 1 or len(part) < min_chars) and len(merged[-1]) + 1 + len(part) <= limit:
                merged[-1] = (merged[-1] + " " + part).strip()
            else:
                merged.append(part)
        return merged or [text]

    def _edge_prosody(self, text: str) -> tuple[str, str, str]:
        base_rate = str(self.config.get("tts_edge_rate", "+10%"))
        base_pitch = str(self.config.get("tts_edge_pitch", "-10Hz"))
        volume = str(self.config.get("tts_edge_volume", "+0%"))
        if not bool(self.config.get("tts_dynamic_prosody", True)):
            return base_rate, base_pitch, volume
        stripped = str(text or "").strip()
        if stripped.endswith("?"):
            return (str(self.config.get("tts_question_rate", "+11%")),
                    str(self.config.get("tts_question_pitch", "-6Hz")), volume)
        if len(stripped) <= 58:
            return (str(self.config.get("tts_short_rate", "+14%")),
                    str(self.config.get("tts_short_pitch", "-8Hz")), volume)
        if len(stripped) >= 240:
            return (str(self.config.get("tts_long_rate", "+9%")),
                    str(self.config.get("tts_long_pitch", "-10Hz")), volume)
        return base_rate, base_pitch, volume

    def _ensure_tts_thread(self):
        with self._tts_lock:
            if self._tts_thread and self._tts_thread.is_alive():
                return
            self._tts_thread = threading.Thread(target=self._tts_loop, name="V-TTS", daemon=True)
            self._tts_thread.start()

    def warmup_tts(self):
        """Preload the selected local speech engine without blocking the interface."""
        profile = str(self.config.get("tts_profile", "") or "").lower()
        if profile in {"piper", "piper_faber", "faber", "offline"}:
            with self._piper_warmup_lock:
                if self._piper_warmup_active.is_set():
                    return True
                self._piper_warmup_active.set()
            def prepare_piper():
                try:
                    self.tts_status = "Preparando voz local"
                    if self._load_piper_voice() is None:
                        self.last_tts_error = self.last_tts_error or "Não foi possível carregar a voz local Piper"
                        self.tts_status = "Falha ao carregar voz local"
                    else:
                        self.tts_status = "Voz pronta"
                        self.last_tts_error = ""
                finally:
                    self._piper_warmup_active.clear()
            threading.Thread(target=prepare_piper, daemon=True, name="V-Piper-Warmup").start()
            return True
        if profile == "qwen_local":
            backend = self._get_qwen()
            if self._qwen_warmup.is_set():
                return True
            self._qwen_warmup.set()
            def prepare_qwen():
                try:
                    self.tts_status = "Preparando V Alt"
                    backend.prepare(self._resolve_qwen_reference())
                    self.tts_status = "Voz pronta"
                    self.last_tts_error = ""
                except Exception as exc:
                    self.last_tts_error = str(exc)
                    self.tts_status = "Falha na voz: " + str(exc)
                finally:
                    self._qwen_warmup.clear()
            threading.Thread(target=prepare_qwen, daemon=True, name="V-Qwen-Warmup").start()
            return True
        if profile not in {"xtts_local", "xtts", "v_prime", "v_prime_local", "local_clone"}:
            return False
        if not bool(self.config.get("tts_xtts_enabled", True)):
            return False
        with self._xtts_warmup_lock:
            if self._xtts_warmup_active.is_set():
                return True
            # Set before starting the thread so speech can wait for preparation.
            self._xtts_warmup_active.set()
        def worker():
            try:
                self.tts_status = "Carregando voz local"
                engine = self._load_xtts()
                if engine is not None:
                    if self._get_xtts_voice(engine, self._resolve_xtts_reference()) is not None:
                        self.last_tts_error = ""
            finally:
                self._xtts_warmup_active.clear()
                self.tts_status = "Voz pronta" if self._xtts is not None else "Falha ao carregar voz: " + self.last_tts_error
        threading.Thread(target=worker, name="V-XTTS-Warmup", daemon=True).start()
        return True

    def _play_mp3_windows(self, filename: str) -> bool:
        """Play MP3 or WAV with cancellable Windows MCI playback."""
        if self._active_cancel.is_set():
            return True
        import ctypes
        alias = "v_audio_" + str(threading.get_ident())
        mci = ctypes.windll.winmm.mciSendStringW
        def command(value):
            result = ctypes.create_unicode_buffer(256)
            error = mci(value, result, len(result), None)
            if error:
                raise RuntimeError(f"MCI playback error {error}")
            return result.value
        try:
            command(f'open "{filename}" alias {alias}')
            command(f'set {alias} time format milliseconds')
            duration = float(command(f'status {alias} length') or 0) / 1000.0
            command(f'play {alias}')
            self.tts_status = "Falando"
            deadline = time.monotonic() + max(120, duration + 10)
            while not self._active_cancel.wait(0.03):
                if command(f'status {alias} mode') == 'stopped':
                    return True
                if time.monotonic() >= deadline:
                    raise TimeoutError("Audio playback timed out")
            return True
        except Exception as exc:
            self.last_tts_error = type(exc).__name__
            log.warning("falha na reprodução MCI: %s", type(exc).__name__)
            return False
        finally:
            mci(f'close {alias}', None, 0, None)

    def _resolve_xtts_reference(self) -> Path:
        """Resolve the local sample used as the V speaker reference."""
        voice_key = str(self.config.get("tts_xtts_voice", "v_prime") or "").strip().lower()
        reference_key = "tts_xtts_reference_alt" if voice_key in {"v_alt", "alt", "second", "2"} else "tts_xtts_reference"
        raw = str(self.config.get(
            reference_key,
            "assets/voice/v_alt_reference_short.wav" if reference_key.endswith("_alt") else "assets/voice/v_prime_reference.mp3",
        ) or "").strip()
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT / path
        return path

    def _load_xtts(self):
        """Load XTTS-v2 once, selecting CUDA only when it is really usable."""
        reference = self._resolve_xtts_reference()
        if not reference.exists():
            self.last_tts_error = "xtts_reference_missing"
            return None
        model_name = str(self.config.get(
            "tts_xtts_model",
            "tts_models/multilingual/multi-dataset/xtts_v2",
        ) or "").strip()
        if not model_name:
            self.last_tts_error = "xtts_model_missing"
            return None
        with self._xtts_lock:
            if (
                self._xtts is not None
                and self._xtts_loaded_model == model_name
            ):
                # A troca de amostra só muda os latentes do locutor; o
                # modelo XTTS pesado continua na GPU e não é recarregado.
                self._xtts_loaded_reference = str(reference)
                return self._xtts
            try:
                import torch
                requested = str(self.config.get("tts_xtts_device", "auto") or "auto").lower()
                use_cuda = requested == "cuda" or (requested == "auto" and bool(torch.cuda.is_available()))
                if use_cuda:
                    # Small CPU tensor operations feed the GPU; a large CPU
                    # thread pool adds overhead to each generated audio token.
                    torch.set_num_threads(max(1, int(self.config.get("tts_xtts_cpu_threads", 4))))
                from TTS.api import TTS

                # Coqui 0.27 delegates torchaudio decoding to torchcodec.
                # Some Windows installations do not ship the matching
                # torchcodec DLL, even though libsndfile can read the same
                # WAV/MP3 reference.  Install a small soundfile loader into
                # XTTS so voice cloning remains local and self-contained.
                try:
                    import numpy as np
                    import soundfile as sf
                    import torch.nn.functional as F
                    import TTS.tts.models.xtts as xtts_module

                    if not getattr(xtts_module, "_v_soundfile_loader", False):
                        def _v_load_audio(audiopath, sampling_rate):
                            data, source_rate = sf.read(str(audiopath), dtype="float32", always_2d=True)
                            audio = torch.from_numpy(np.asarray(data, dtype=np.float32).T)
                            if audio.size(0) != 1:
                                audio = audio.mean(dim=0, keepdim=True)
                            if int(source_rate) != int(sampling_rate):
                                target_len = max(1, int(round(audio.shape[-1] * float(sampling_rate) / float(source_rate))))
                                audio = F.interpolate(
                                    audio.unsqueeze(0), size=target_len, mode="linear", align_corners=False
                                ).squeeze(0)
                            return audio.clamp(-1.0, 1.0)

                        xtts_module.load_audio = _v_load_audio
                        xtts_module._v_soundfile_loader = True
                except Exception as exc:
                    # Let the normal Coqui loader handle environments where
                    # soundfile is unavailable and torchcodec is functional.
                    log.warning("loader soundfile do XTTS indisponível: %s", type(exc).__name__)

                # Coqui's API downloads the model on first use and keeps it in
                # memory.  A CPU-only environment remains fully supported.
                engine = TTS(model_name=model_name, progress_bar=False, gpu=use_cuda)
                # The vocoder is inference-only. Materialize its normalized
                # weights once instead of recomputing them on every PCM block.
                from torch.nn.utils.parametrize import is_parametrized, remove_parametrizations
                decoder = engine.synthesizer.tts_model.hifigan_decoder.waveform_decoder
                for layer in list(decoder.modules()):
                    if is_parametrized(layer, "weight"):
                        remove_parametrizations(layer, "weight", leave_parametrized=True)
                self._xtts = engine
                self._xtts_loaded_model = model_name
                self._xtts_loaded_reference = str(reference)
                self.last_tts_metrics = {
                    "engine": "xtts_v2",
                    "device": "cuda" if use_cuda else "cpu",
                    "reference": reference.name,
                }
                return engine
            except Exception as exc:
                self._xtts = None
                self._xtts_loaded_model = None
                self._xtts_loaded_reference = None
                self.last_tts_error = type(exc).__name__
                log.warning("falha ao carregar XTTS: %s", type(exc).__name__)
                return None

    def _synthesize_xtts_file(self, text: str) -> str | None:
        """Synthesize one chunk with the locally cloned V voice."""
        reference = self._resolve_xtts_reference()
        if not reference.exists():
            self.last_tts_error = "xtts_reference_missing: " + str(reference)
            return None
        stat = reference.stat()
        # Include every XTTS setting, sample identity and modification time so
        # no cached audio can carry another voice or an outdated speed.
        cache_key = (text, str(reference.resolve()), stat.st_mtime_ns, stat.st_size,
                     tuple(sorted((k, repr(v)) for k, v in self.config.items() if k.startswith("tts_xtts_"))))
        with self._xtts_audio_cache_lock:
            cached = self._xtts_audio_cache.get(cache_key)
            if cached is not None:
                self._xtts_audio_cache.move_to_end(cache_key)
        if cached is not None:
            fd, path = tempfile.mkstemp(prefix="v_xtts_cached_", suffix=".wav")
            with os.fdopen(fd, "wb") as out:
                out.write(cached)
            self.last_tts_metrics = {"engine": "xtts_v2", "cache_hit": True,
                                     "reference": reference.name, "synthesis_ms": 0.0}
            return path
        engine = self._load_xtts()
        if engine is None:
            return None
        language = str(self.config.get("tts_xtts_language", "pt") or "pt").strip()
        speaker = str(self.config.get("tts_xtts_speaker", "V Prime") or "").strip()
        fd, path = tempfile.mkstemp(prefix="v_xtts_", suffix=".wav")
        os.close(fd)
        try:
            started = time.perf_counter()
            voice = self._get_xtts_voice(engine, reference)
            kwargs = {
                "text": str(text),
                "language": language,
                "speaker_wav": [str(reference)],
                "file_path": path,
            }
            voice_key = str(self.config.get("tts_xtts_voice", "v_prime") or "").lower()
            speed_key = "tts_xtts_speed_alt" if voice_key in {"v_alt", "alt", "second", "2"} else "tts_xtts_speed"
            speed = max(0.8, min(1.25, float(self.config.get(speed_key, 1.0))))
            kwargs["speed"] = speed

            # Run the XTTS model directly with cached speaker latents. The
            # public API recomputes the reference embedding for every chunk.
            model = getattr(getattr(engine, "synthesizer", None), "tts_model", None)
            if model is None or not voice:
                engine.tts_to_file(**kwargs)
            else:
                with self._xtts_inference_lock:
                    result = model.inference(
                        str(text), language,
                        voice["gpt_conditioning_latents"],
                        voice["speaker_embedding"],
                        speed=speed,
                    )
                import soundfile as sf
                sample_rate = int(getattr(getattr(engine, "synthesizer", None), "output_sample_rate", 24000) or 24000)
                sf.write(path, result["wav"], sample_rate, subtype="PCM_16")
            if not Path(path).exists() or Path(path).stat().st_size < 256:
                raise RuntimeError("xtts_empty_audio")
            self._polish_xtts_file(path)
            content = Path(path).read_bytes()
            if len(content) <= 2_000_000:
                with self._xtts_audio_cache_lock:
                    self._xtts_audio_cache[cache_key] = content
                    while (len(self._xtts_audio_cache) > 16 or
                           sum(len(x) for x in self._xtts_audio_cache.values()) > 8_000_000):
                        self._xtts_audio_cache.popitem(last=False)
            self.last_tts_metrics = {
                "engine": "xtts_v2",
                "synthesis_ms": round((time.perf_counter() - started) * 1000.0, 1),
                "reference": reference.name,
                "speed": speed,
            }
            return path
        except Exception as exc:
            self.last_tts_error = type(exc).__name__
            log.warning("falha ao sintetizar trecho XTTS: %s", type(exc).__name__)
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def _get_xtts_voice(self, engine, reference: Path):
        """Cache speaker latents so every sentence skips reference analysis."""
        try:
            conditioning = {
                "max_ref_length": int(self.config.get("tts_xtts_max_ref_seconds", 12)),
                "gpt_cond_len": int(self.config.get("tts_xtts_condition_seconds", 6)),
                "gpt_cond_chunk_len": int(self.config.get("tts_xtts_condition_chunk_seconds", 6)),
            }
            stat = reference.stat()
            key = (id(engine), str(reference.resolve()), stat.st_mtime_ns, stat.st_size, tuple(conditioning.values()))
            model = getattr(getattr(engine, "synthesizer", None), "tts_model", None)
            if model is None:
                return None
            with self._xtts_voice_cache_lock:
                cached = self._xtts_voice_cache.get(key)
                if cached is not None:
                    return cached
                with self._xtts_inference_lock:
                    voice = model.clone_voice([str(reference)], None, None, **conditioning)
                self._xtts_voice_cache[key] = voice
            return voice
        except Exception as exc:
            self.last_tts_error = type(exc).__name__
            log.warning("falha ao preparar timbre XTTS: %s", type(exc).__name__)
            return None

    def _polish_xtts_file(self, path: str) -> None:
        """Apply a restrained final pass without changing the speaker timbre."""
        if not bool(self.config.get("tts_xtts_polish_enabled", True)):
            return
        try:
            import numpy as np
            import soundfile as sf

            audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
            if audio is None or getattr(audio, "size", 0) == 0:
                return
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1, dtype=np.float32)
            audio = np.asarray(audio, dtype=np.float32)

            # Remove only edge silence. Internal pauses remain untouched.
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            threshold = max(0.0001, peak * 0.005)
            active = np.flatnonzero(np.abs(audio) >= threshold)
            if active.size:
                pad = int(max(100.0, float(self.config.get("tts_xtts_trim_pad_ms", 100))) * sample_rate / 1000.0)
                start = max(0, int(active[0]) - pad)
                end = min(audio.size, int(active[-1]) + pad + 1)
                audio = audio[start:end]

            # Gentle high-pass for room/codec rumble; two poles keep the voice
            # body intact while cleaning the bottom end.
            highpass_hz = float(self.config.get("tts_xtts_highpass_hz", 65.0))
            if highpass_hz > 0.0 and sample_rate > highpass_hz * 2.2:
                from scipy.signal import butter, sosfilt
                sos = butter(2, highpass_hz, btype="highpass", fs=sample_rate, output="sos")
                audio = sosfilt(sos, audio).astype(np.float32)

            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            target_peak = max(0.5, min(0.98, float(self.config.get("tts_xtts_target_peak", 0.92))))
            if peak > 0.00001:
                audio = np.clip(audio * (target_peak / peak), -0.98, 0.98).astype(np.float32)
            sf.write(path, audio, int(sample_rate), subtype="PCM_16")
        except Exception as exc:
            # The polish is optional; a codec/filter problem must not silence
            # a successful XTTS synthesis.
            log.warning("polimento de áudio XTTS ignorado: %s", type(exc).__name__)
            return

    def _get_qwen(self):
        with self._qwen_lock:
            if self._qwen is None:
                from .qwen_backend import QwenBackend
                self._qwen = QwenBackend(self.config)
                self._qwen.game_mode = bool(getattr(self, '_game_mode', False))
            return self._qwen

    def _resolve_qwen_reference(self):
        path = Path(self.config.get("tts_qwen_reference", "assets/voice/v_alt_reference_short.wav"))
        return path if path.is_absolute() else ROOT / path

    def _speak_qwen(self, text):
        import soundfile as sf
        cancel = self._active_cancel
        backend = self._get_qwen()
        reference = self._resolve_qwen_reference()
        started = time.perf_counter()
        metrics = {'engine': 'qwen3_0.6b', 'reference': reference.name}
        self.last_tts_metrics = metrics
        def audio_chunks():
            from .briefing_cache import cache_path, valid_audio, store_audio, GREETINGS
            for sentence in ([text] if text in GREETINGS else self._split_qwen_response(text)):
                if cancel.is_set():
                    return
                if 'first_audio_ms' not in metrics:
                    self.tts_status = 'Carregando V Alt' if self._qwen_warmup.is_set() else 'Gerando voz local — aguarde'
                saved = cache_path(sentence, reference, self.config)
                persistent_hit = saved is not None and valid_audio(saved)
                path = str(saved) if persistent_hit else backend.synthesize(sentence, reference, cancel)
                if not path:
                    return
                metrics['persistent_greeting_hit'] = persistent_hit
                if not persistent_hit and isinstance(backend.last_metrics, dict):
                    metrics['reference_mode'] = backend.last_metrics.get('reference_mode', 'speaker')
                    metrics['gpu_priority'] = backend.last_metrics.get('gpu_priority', {'applied': False, 'status': 'unknown'})
                    metrics['compute_backend'] = backend.last_metrics.get('compute_backend', 'unknown')
                    metrics['cpu_threads'] = backend.last_metrics.get('cpu_threads')
                    metrics['cached_phrases'] = metrics.get('cached_phrases', 0) + int(bool(backend.last_metrics.get('cache_hit')))
                try:
                    if saved is not None and not persistent_hit and not cancel.is_set():
                        try:
                            store_audio(path, saved)
                        except OSError:
                            pass  # A read-only cache must not prevent speech.
                    audio, rate = sf.read(path, dtype='float32', always_2d=True)
                    if rate != 24000 or audio.shape[1] != 1:
                        raise ValueError('Formato de áudio Qwen inesperado')
                    from .qwen_audio import shorten_phrase_silence
                    original_frames = len(audio)
                    audio = shorten_phrase_silence(audio, rate)
                    metrics['trimmed_silence_ms'] = round(
                          metrics.get('trimmed_silence_ms', 0) +
                          (original_frames - len(audio)) * 1000 / rate, 1)
                    if self.config.get('tts_robot_enabled', False):
                        try:
                            from .robot_effect import process_audio
                            effect_started = time.perf_counter()
                            audio = process_audio(audio, rate, self.config.get('tts_robot_intensity', .35))
                            metrics['robot_effect_ms'] = round((time.perf_counter() - effect_started) * 1000, 1)
                            metrics.pop('robot_effect_error', None)
                        except Exception as exc:
                            metrics['robot_effect_error'] = str(exc)
                    yield audio
                finally:
                    if not persistent_hit:
                        Path(path).unlink(missing_ok=True)
        # One output device for the whole reply: no MCI close/open pause at
        # sentence boundaries. Generation continues while its callback plays.
        reserve = max(1, min(3, int(self.config.get('tts_qwen_prebuffer_phrases', 1))))
        metrics['prebuffer_phrases'] = reserve
        return bool(self._play_xtts_audio(audio_chunks(), 24000, cancel, started, metrics, reserve=reserve))

    def _split_qwen_response(self, text):
        """Release a substantial opening clause sooner, preserving all words.

        Only the first sentence is shortened and only at natural punctuation.
        Keep later chunks large to avoid paying generation overhead repeatedly.
        """
        parts = self._split_xtts_response(text)
        if not parts or len(parts[0]) <= 100:
            return parts
        first = parts[0]
        for match in re.finditer(r'[,;:]\s+', first):
            end = match.start() + 1
            remaining = len(first[match.end():])
            # Leave enough spoken material to cover generation of the rest.
            # Tiny openers start sooner but introduce multi-second mid-sentence gaps.
            if 60 <= end <= 160 and 25 <= remaining <= end / 1.5:
                return [first[:end], first[match.end():]] + parts[1:]
        return parts

    def _speak_xtts(self, text: str) -> bool:
        if not bool(self.config.get("tts_xtts_enabled", True)):
            return False
        # Wait in the speech worker, not the UI. Loading is not a failure and
        # must not replace the selected sample with an unrelated fallback voice.
        cancel = self._active_cancel
        while self._xtts_warmup_active.is_set():
            if cancel.wait(0.05):
                return True
        if cancel.is_set():
            return True
        self.tts_status = "Preparando áudio"
        # Streaming reserves audio before opening playback. Complete-file mode
        # remains available as a fallback when streaming cannot start.
        if bool(self.config.get("tts_xtts_streaming_enabled", False)):
            streamed = self._speak_xtts_streaming(text)
            if streamed is not None:
                return streamed
        if self.config.get("tts_xtts_response_mode") == "buffered":
            return self._speak_chunks(self._split_tts_chunks(text), self._synthesize_xtts_file,
                                      prebuffer=2)
        return self._speak_chunks([text], self._synthesize_xtts_response)

    def _split_xtts_response(self, text: str) -> list[str]:
        """Keep sentence endings; bound long clauses without a tiny first chunk."""
        text = self._prepare_spoken_text(text)
        parts = []
        for sentence in re.split(r"(?<=[.!?…])\s+", text):
            current = ""
            for word in sentence.split():
                if current and len(current) + len(word) + 1 > 220:
                    parts.append(current)
                    current = ""
                current = (current + " " + word).strip()
            if current:
                parts.append(current)
        return parts

    def _synthesize_xtts_response(self, text: str) -> str | None:
        """Prepare every phrase before playback so slow synthesis cannot cause gaps."""
        cancel = self._active_cancel
        fd, output = tempfile.mkstemp(prefix="v_xtts_response_", suffix=".wav")
        os.close(fd)
        complete = False
        try:
            with wave.open(output, "wb") as joined:
                expected = None
                for chunk in self._split_xtts_response(text):
                    if cancel.is_set():
                        return None
                    path = self._synthesize_xtts_file(chunk)
                    if not path:
                        return None
                    try:
                        if cancel.is_set():
                            return None
                        with wave.open(path, "rb") as audio:
                            fmt = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                            if expected is None:
                                expected = fmt
                                joined.setnchannels(fmt[0])
                                joined.setsampwidth(fmt[1])
                                joined.setframerate(fmt[2])
                            elif fmt != expected:
                                raise ValueError("xtts_audio_format_changed")
                            joined.writeframes(audio.readframes(audio.getnframes()))
                    finally:
                        Path(path).unlink(missing_ok=True)
                if expected is None:
                    return None
            complete = True
            return output
        except Exception as exc:
            self.last_tts_error = type(exc).__name__ + ": " + str(exc)
            log.warning("falha ao montar resposta XTTS: %s", type(exc).__name__)
            return None
        finally:
            if not complete:
                Path(output).unlink(missing_ok=True)

    def _speak_xtts_streaming(self, text: str) -> bool | None:
        """Play XTTS chunks as they are generated to reduce first-word delay."""
        clean = self._prepare_spoken_text(text)
        if not clean:
            return None
        started = time.perf_counter()
        cancel = self._active_cancel
        if cancel.is_set():
            return True
        reference = self._resolve_xtts_reference()
        engine = self._load_xtts()
        if engine is None or not reference.exists():
            return None
        voice = self._get_xtts_voice(engine, reference)
        model = getattr(getattr(engine, "synthesizer", None), "tts_model", None)
        if model is None or not voice:
            return None
        try:
            import numpy as np

            voice_key = str(self.config.get("tts_xtts_voice", "v_prime") or "").lower()
            speed_key = "tts_xtts_speed_alt" if voice_key in {"v_alt", "alt", "second", "2"} else "tts_xtts_speed"
            speed = max(0.8, min(1.25, float(self.config.get(speed_key, 1.0))))
            sample_rate = int(getattr(engine.synthesizer, "output_sample_rate", 24000) or 24000)
            metrics = {"engine": "xtts_v2_stream", "speed": speed, "reference": reference.name}
            # Split long replies into model-sized phrases but keep one output
            # device open for the entire reply. The audio queue stays bounded.
            texts = self._split_xtts_response(clean)

            def chunks():
                sos = filter_state = None
                highpass = float(self.config.get("tts_xtts_highpass_hz", 65.0))
                if self.config.get("tts_xtts_polish_enabled", True) and 0 < highpass < sample_rate / 2:
                    try:
                        from scipy.signal import butter, sosfilt
                        sos = butter(2, highpass, btype="highpass", fs=sample_rate, output="sos")
                        filter_state = np.zeros((len(sos), 2))
                    except ImportError:
                        pass
                with self._xtts_inference_lock:
                    for sentence in texts:
                        if cancel.is_set():
                            return
                        stream = model.inference_stream(
                            sentence,
                            str(self.config.get("tts_xtts_language", "pt") or "pt"),
                            voice["gpt_conditioning_latents"],
                            voice["speaker_embedding"],
                            stream_chunk_size=max(8, int(self.config.get("tts_xtts_stream_chunk_size", 48))),
                            overlap_wav_len=max(256, int(self.config.get("tts_xtts_stream_overlap", 1024))),
                            speed=speed,
                            # Already split locally. Coqui's optional splitter
                            # imports Spacy and can fail only on longer replies.
                            enable_text_splitting=False,
                        )
                        try:
                            for chunk in stream:
                                if cancel.is_set():
                                    return
                                if hasattr(chunk, "detach"):
                                    chunk = chunk.detach().cpu().numpy()
                                audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
                                if not audio.size:
                                    continue
                                if sos is not None:
                                    audio, filter_state = sosfilt(sos, audio, zi=filter_state)
                                yield np.clip(audio, -0.98, 0.98).astype(np.float32).reshape(-1, 1)
                        finally:
                            stream.close()

            result = self._play_xtts_audio(chunks(), sample_rate, cancel, started, metrics)
            metrics["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
            self.last_tts_metrics = metrics
            return result
        except Exception as exc:
            self.last_tts_error = type(exc).__name__
            log.warning("falha no streaming XTTS: %s", type(exc).__name__)
            return None

    def _play_xtts_audio(self, chunks, sample_rate, cancel, started, metrics, reserve=None) -> bool | None:
        """Feed the device from a callback so playback never blocks inference."""
        import sounddevice as sd

        prepared = queue.Queue(maxsize=8)
        generated = threading.Event()
        finished = threading.Event()
        current = None
        offset = 0
        spoken = False
        output = None
        output_started = False
        reserve = max(1, min(8, int(self.config.get("tts_xtts_stream_prebuffer_chunks", 1) if reserve is None else reserve)))
        metrics["buffer_gap_ms"] = 0.0
        metrics["device_underflows"] = 0

        def callback(outdata, frames, timing, status):
            nonlocal current, offset, spoken
            outdata.fill(0)
            if cancel.is_set():
                raise sd.CallbackAbort
            if status.output_underflow:
                metrics["device_underflows"] += 1
            written = 0
            while written < frames:
                if current is None:
                    try:
                        current = prepared.get_nowait()
                        offset = 0
                    except queue.Empty:
                        if generated.is_set():
                            raise sd.CallbackStop
                        if spoken:
                            metrics["buffer_gap_ms"] += (frames - written) * 1000.0 / sample_rate
                        return
                count = min(frames - written, len(current) - offset)
                outdata[written:written + count] = current[offset:offset + count]
                if not spoken:
                    # Include the device's scheduled DAC time when available.
                    device_delay = max(0.0, timing.outputBufferDacTime - timing.currentTime)
                    metrics["first_audio_ms"] = round((time.perf_counter() - started + device_delay) * 1000, 1)
                    spoken = True
                    self.tts_status = "Falando"
                written += count
                offset += count
                if offset == len(current):
                    current = None

        try:
            # Qwen competes with native synthesis on modest PCs. Let the audio
            # driver reserve more time rather than requesting minimum latency.
            device_latency = 'high' if metrics.get('engine') == 'qwen3_0.6b' else 'low'
            metrics['device_latency_mode'] = device_latency
            output = sd.OutputStream(
                samplerate=sample_rate, channels=1, dtype="float32",
                blocksize=max(128, sample_rate // 50), latency=device_latency,
                callback=callback, finished_callback=finished.set,
            )
            generation_error = None
            try:
                for chunk in chunks:
                    if cancel.is_set() or finished.is_set():
                        break
                    while not cancel.is_set() and not finished.is_set():
                        try:
                            prepared.put(chunk, timeout=0.03)
                            break
                        except queue.Full:
                            continue
                    if not output_started and prepared.qsize() >= reserve and not cancel.is_set():
                        output.start()
                        output_started = True
            except Exception as exc:
                generation_error = type(exc).__name__ + ": " + str(exc)
                self.last_tts_error = generation_error
                log.warning("falha ao gerar áudio para reprodução: %s", type(exc).__name__)
            generated.set()
            if not output_started and not prepared.empty() and not cancel.is_set():
                output.start()
                output_started = True
            metrics["generation_ms"] = round((time.perf_counter() - started) * 1000, 1)
            while output_started and not cancel.is_set() and not finished.wait(0.03):
                if not output.active:
                    break
            if spoken and not cancel.is_set() and generation_error is None:
                self.last_tts_error = ""
            return True if spoken or cancel.is_set() else None
        except Exception as exc:
            self.last_tts_error = type(exc).__name__
            log.warning("falha na reprodução de áudio XTTS: %s", type(exc).__name__)
            # Do not replay a sentence whose first words were already heard.
            return True if spoken or cancel.is_set() else None
        finally:
            if output is not None:
                try:
                    output.abort()
                except Exception as exc:
                    log.warning("falha ao abortar saída de áudio: %s", type(exc).__name__)
                try:
                    output.close()
                except Exception as exc:
                    log.warning("falha ao fechar saída de áudio: %s", type(exc).__name__)
            try:
                chunks.close()
            except Exception as exc:
                log.warning("falha ao fechar gerador de áudio: %s", type(exc).__name__)
            metrics["buffer_gap_ms"] = round(metrics["buffer_gap_ms"], 1)

    def _resolve_piper_model(self) -> Path:
        """Retorna o caminho absoluto do modelo Piper configurado."""
        raw = str(self.config.get("tts_piper_model", "models/piper/pt_BR-faber-medium.onnx")).strip()
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        return p

    def _load_piper_voice(self):
        """Carrega o modelo Piper uma única vez e o mantém em memória."""
        model_path = self._resolve_piper_model()
        if not model_path.exists():
            self.last_tts_error = f"Modelo Piper não encontrado: {model_path}"
            log.warning("modelo Piper não encontrado em %s", model_path)
            return None
        with self._piper_lock:
            if self._piper_voice is not None and self._piper_loaded_model == str(model_path):
                return self._piper_voice
            try:
                from piper import PiperVoice
                use_cuda = bool(self.config.get("tts_piper_use_cuda", False))
                self._piper_voice = PiperVoice.load(str(model_path), use_cuda=use_cuda)
                self._piper_loaded_model = str(model_path)
                return self._piper_voice
            except Exception as exc:
                self.last_tts_error = f"Falha ao carregar voz local Piper ({type(exc).__name__})"
                log.warning("falha ao carregar voz Piper (%s): %s", type(exc).__name__, exc)
                self._piper_voice = None
                self._piper_loaded_model = None
                return None

    def _speak_piper(self, text: str) -> bool:
        """Sintetiza localmente com Piper/Faber e reproduz via winsound."""
        voice = self._load_piper_voice()
        if voice is None:
            return False
        fd, path = tempfile.mkstemp(prefix="v_piper_", suffix=".wav")
        os.close(fd)
        try:
            try:
                from piper import SynthesisConfig
                syn = SynthesisConfig(
                    length_scale=float(self.config.get("tts_piper_length_scale", 0.92)),
                    noise_scale=float(self.config.get("tts_piper_noise_scale", 0.667)),
                    noise_w_scale=float(self.config.get("tts_piper_noise_w_scale", 0.8)),
                    volume=float(self.config.get("tts_piper_volume", 1.0)),
                    normalize_audio=True,
                )
            except Exception as exc:
                log.warning("configuração de síntese Piper indisponível, usando padrão: %s", type(exc).__name__)
                syn = None
            with wave.open(path, "wb") as wav_file:
                if syn is None:
                    voice.synthesize_wav(text, wav_file)
                else:
                    voice.synthesize_wav(text, wav_file, syn_config=syn)
            if os.name == "nt":
                return self._play_mp3_windows(path)
            return False
        except Exception as exc:
            self.last_tts_error = f"Falha na síntese Piper ({type(exc).__name__})"
            log.warning("falha na síntese/reprodução Piper (%s): %s", type(exc).__name__, exc)
            return False
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _synthesize_edge_file(self, text: str, rate: str, pitch: str, volume: str) -> str | None:
        try:
            import edge_tts
        except Exception as exc:
            self.last_tts_error = f"Edge TTS indisponível ({type(exc).__name__})"
            log.warning("edge_tts indisponível: %s", type(exc).__name__)
            return None
        fd, path = tempfile.mkstemp(prefix="v_edge_tts_", suffix=".mp3")
        os.close(fd)
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=str(self.config.get("tts_edge_voice", "pt-BR-AntonioNeural")),
                rate=rate,
                pitch=pitch,
                volume=volume,
            )
            communicate.save_sync(path)
            return path
        except Exception as exc:
            self.last_tts_error = f"Falha na síntese Edge TTS ({type(exc).__name__})"
            log.warning("falha na síntese Edge TTS (%s): %s", type(exc).__name__, exc)
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def _eleven_voice_settings(self, text: str) -> dict:
        """Perfil vocal do V: vivo e conversacional sem exagerar o estilo."""
        speed = float(self.config.get("tts_eleven_speed", 1.06))
        stripped = str(text or "").strip()
        if self.config.get("tts_dynamic_prosody", True) and len(stripped) <= 58:
            speed = min(1.2, speed + 0.03)
        elif self.config.get("tts_dynamic_prosody", True) and len(stripped) >= 240:
            speed = max(0.9, speed - 0.02)
        return {
            "stability": float(self.config.get("tts_eleven_stability", 0.48)),
            "similarity_boost": float(self.config.get("tts_eleven_similarity_boost", 0.78)),
            "style": float(self.config.get("tts_eleven_style", 0.0)),
            "speed": speed,
            "use_speaker_boost": bool(self.config.get("tts_eleven_use_speaker_boost", False)),
        }

    def _cached_audio_file(self, key):
        with self._tts_cache_lock:
            content = self._tts_audio_cache.get(key)
            if content is None:
                return None
            self._tts_audio_cache.move_to_end(key)
        fd, path = tempfile.mkstemp(prefix="v_cached_", suffix=".mp3")
        os.close(fd)
        Path(path).write_bytes(content)
        self.last_tts_metrics = {"engine": "elevenlabs", "cache_hit": True, "synthesis_ms": 0.0}
        return path

    def _synthesize_eleven_file(self, text: str) -> str | None:
        """Gera MP3 com a voz personalizada do V via ElevenLabs."""
        try:
            import requests
            from voice.eleven_auth import load_key
            if self._eleven_session is None:
                self._eleven_session = requests.Session()
                self._eleven_session.headers.update({"User-Agent":"V-Assistant/1.4.1"})
        except Exception as exc:
            self.last_tts_error = 'Falha ao preparar ElevenLabs: ' + type(exc).__name__
            log.warning("falha ao preparar cliente ElevenLabs: %s", type(exc).__name__)
            return None
        key = load_key(self.config)
        voice_id = str(self.config.get("tts_eleven_voice_id", "")).strip()
        if not key or not voice_id:
            self.last_tts_error = "Configure a chave e o Voice ID do ElevenLabs"
            return None
        model = str(self.config.get("tts_eleven_model", "eleven_flash_v2_5")).strip()
        fmt = str(self.config.get("tts_eleven_output_format", "mp3_44100_128")).strip()
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
        payload = {
            "text": str(text),
            "model_id": model,
            "voice_settings": self._eleven_voice_settings(text),
        }
        language = str(self.config.get("tts_eleven_language_code", "pt") or "").strip()
        if language and model != "eleven_multilingual_v2":
            payload["language_code"] = language
        import json
        cache_key = (voice_id, fmt, json.dumps(payload, sort_keys=True, ensure_ascii=False))
        if len(text) <= 240:
            cached = self._cached_audio_file(cache_key)
            if cached:
                return cached
        timeout = float(self.config.get("tts_eleven_timeout", 22))
        fd, path = tempfile.mkstemp(prefix="v_eleven_", suffix=".mp3")
        os.close(fd)
        try:
            synth_started=time.perf_counter()
            response = self._eleven_session.post(
                url,
                params={"output_format": fmt},
                headers=headers,
                json=payload,
                timeout=(4.0, timeout),
            )
            if response.status_code != 200 or not response.content:
                status = ""
                try:
                    detail = response.json().get('detail', {})
                    if isinstance(detail, dict):
                        status = str(detail.get('status', ''))[:100]
                except (ValueError, AttributeError):
                    pass
                self.last_tts_error = f"ElevenLabs HTTP {response.status_code}" + (f" ({status})" if status else "")
                log.warning("ElevenLabs HTTP %s%s", response.status_code, f" ({status})" if status else "")
                if status == 'quota_exceeded':
                    self.last_tts_error = ('ElevenLabs: cota de voz esgotada (quota_exceeded). '
                                           'Verifique os créditos da conta ou selecione outra voz em Voz e tarefas.')
                try:
                    os.remove(path)
                except OSError:
                    pass
                return None
            Path(path).write_bytes(response.content)
            if len(text) <= 240 and len(response.content) <= 512000:
                with self._tts_cache_lock:
                    self._tts_audio_cache[cache_key] = response.content
                    self._tts_audio_cache.move_to_end(cache_key)
                    while len(self._tts_audio_cache) > 16:
                        self._tts_audio_cache.popitem(last=False)
            self.last_tts_metrics={"engine":"elevenlabs","synthesis_ms":round((time.perf_counter()-synth_started)*1000.0,1)}
            return path
        except Exception as exc:
            self.last_tts_error = 'Falha na conexão ou geração ElevenLabs: ' + type(exc).__name__
            log.warning("falha de conexão/geração ElevenLabs: %s", type(exc).__name__)
            try:
                os.remove(path)
            except OSError:
                pass
            return None

    def _speak_chunks(self, chunks, synthesize, prebuffer=1):
        """Bounded prefetch with cancellation and ownership of temporary files."""
        if not chunks or self._active_cancel.is_set():
            return self._active_cancel.is_set()
        cancel = self._active_cancel
        abandoned = threading.Event()
        prepared = queue.Queue(maxsize=max(1, int(self.config.get("tts_prefetch_chunks", 2))))
        transfer_lock = threading.Lock()

        def discard(path):
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

        def deliver(path):
            while not abandoned.is_set() and not cancel.is_set():
                with transfer_lock:
                    if abandoned.is_set():
                        break
                    try:
                        prepared.put_nowait(path)
                        return True
                    except queue.Full:
                        pass
                abandoned.wait(0.03)
            discard(path)
            return False

        def producer():
            try:
                for chunk in chunks:
                    if cancel.is_set() or abandoned.is_set():
                        break
                    path = synthesize(chunk)
                    if not deliver(path) or not path:
                        return
            except Exception as exc:
                self.last_tts_error = type(exc).__name__
                log.warning("falha ao preparar áudio TTS em segundo plano: %s", type(exc).__name__)
            finally:
                deliver(None)

        threading.Thread(target=producer, name="V-TTS-Prefetch", daemon=True).start()
        spoken = False
        pending = deque()
        ended = False
        try:
            # Reserve complete phrases before starting. Synthesis of following
            # phrases can overlap playback without waiting for the whole reply.
            while len(pending) < max(1, prebuffer) and not cancel.is_set():
                try:
                    path = prepared.get(timeout=0.05)
                except queue.Empty:
                    continue
                if path is None:
                    ended = True
                    break
                pending.append(path)
            while not cancel.is_set():
                if pending:
                    path = pending.popleft()
                elif ended:
                    return spoken
                else:
                    try:
                        path = prepared.get(timeout=0.05)
                    except queue.Empty:
                        continue
                if path is None:
                    return spoken
                try:
                    if not self._play_mp3_windows(path):
                        return spoken
                    spoken = True
                finally:
                    discard(path)
            return True  # Cancellation is intentional, not a fallback trigger.
        finally:
            while pending:
                discard(pending.popleft())
            with transfer_lock:
                abandoned.set()
                while True:
                    try:
                        discard(prepared.get_nowait())
                    except queue.Empty:
                        break

    def _speak_elevenlabs(self, text: str) -> bool:
        return self._speak_chunks(self._split_tts_chunks(text), self._synthesize_eleven_effect_file)

    def _synthesize_eleven_effect_file(self, text):
        path = self._synthesize_eleven_file(text)
        if not path or not self.config.get('tts_robot_enabled', False):
            return path
        if self._active_cancel.is_set():
            Path(path).unlink(missing_ok=True)
            return None
        try:
            from .robot_effect import process_file
            started = time.perf_counter()
            result = process_file(path, self.config.get('tts_robot_intensity', .35))
            self.last_tts_metrics['robot_effect_ms'] = round((time.perf_counter() - started) * 1000, 1)
            self.last_tts_metrics.pop('robot_effect_error', None)
        except Exception as exc:
            # Optional DSP failure must not silence the user's selected voice.
            self.last_tts_metrics['robot_effect_error'] = str(exc)
            log.warning("efeito de voz robótica ignorado: %s", type(exc).__name__)
            return path
        Path(path).unlink(missing_ok=True)
        return result

    def _speak_edge_tts(self, text: str) -> bool:
        rate, pitch, volume = self._edge_prosody(text)
        return self._speak_chunks(
            self._split_tts_chunks(text),
            lambda chunk: self._synthesize_edge_file(chunk, rate, pitch, volume),
        )

    def _tts_loop(self):
        """Saída de voz: Edge-TTS natural, Piper offline e SAPI5 em cascata."""
        receipt = None
        sapi_disponivel = False
        try:
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                sapi_disponivel = True
            except Exception as exc:
                # Sem COM/SAPI a voz ainda pode sair por Edge, Piper, XTTS ou
                # ElevenLabs; a thread de saida NAO pode morrer por causa disso.
                pythoncom = None
                log.warning(
                    "TTS: COM/SAPI indisponivel (%s); seguindo com os outros motores",
                    type(exc).__name__,
                )
            voice = None  # Only initialize SAPI if a local fallback is needed.
            while True:
                item = self._tts_queue.get()
                if item is None:
                    break
                text, self._active_cancel = item[:2]
                receipt = item[2] if len(item) == 3 else None
                if self._active_cancel.is_set():
                    self._discard_speech_item(item)
                    continue
                if receipt is not None:
                    receipt.update(state='speaking')
                spoken = False
                try:
                    self._tts_epoch += 1
                    speech_started = time.perf_counter()
                    self.last_tts_metrics = {}
                    self._begin_visual_speech(text)
                    self._tts_speaking.set()
                    self.last_tts_error = ""
                    profile = self._speech_profile(receipt)
                    self._active_tts_profile = profile

                    # Voz local personalizada: XTTS-v2 usa a amostra do V e
                    # mantém Edge/Piper como fallback de disponibilidade.
                    if profile == 'piper' and (receipt or {}).get('profile') == 'piper':
                        spoken = self._speak_piper(text)
                        if not spoken and not self._active_cancel.is_set() and not self.last_tts_error:
                            self.last_tts_error = 'A voz do colega Z está indisponível. Os detalhes continuam na tela.'
                        continue
                    elif profile == "qwen_local":
                        spoken = self._speak_qwen(text)
                        # A native failure must be visible, never silently change
                        # the user-approved sample to a system voice.
                        if not spoken and not self._active_cancel.is_set() and not self.last_tts_error:
                            self.last_tts_error = "Não foi possível gerar a V Alt"
                        continue
                    elif profile in {"xtts_local", "xtts", "v_prime", "v_prime_local", "local_clone"}:
                        spoken = self._speak_xtts(text)
                        if (not spoken) and not self._active_cancel.is_set() and bool(self.config.get("tts_xtts_fallback_edge", True)):
                            log.warning("voz XTTS indisponível; usando Edge TTS como fallback: %s", self.last_tts_error or "motivo desconhecido")
                            spoken = self._speak_edge_tts(text)
                        if not spoken and not self._active_cancel.is_set():
                            spoken = self._speak_piper(text)

                    # Voz oficial personalizada: ElevenLabs -> Edge -> Piper -> SAPI5.
                    elif profile in {"elevenlabs_custom", "elevenlabs", "v_custom", "v_voice"}:
                        spoken = self._speak_elevenlabs(text)
                        if not bool(self.config.get("tts_eleven_fallback_edge", True)):
                            if not spoken and not self._active_cancel.is_set() and not self.last_tts_error:
                                self.last_tts_error = "Não foi possível gerar a voz do ElevenLabs"
                            continue
                        if (not spoken) and not self._active_cancel.is_set() and bool(self.config.get("tts_eleven_fallback_edge", True)):
                            log.warning("ElevenLabs indisponível; usando Edge TTS como fallback: %s", self.last_tts_error or "motivo desconhecido")
                            spoken = self._speak_edge_tts(text)
                        if not spoken and not self._active_cancel.is_set():
                            spoken = self._speak_piper(text)

                    # Perfil offline: Piper/Faber -> Edge-TTS -> SAPI5.
                    elif profile in {"piper", "piper_faber", "faber", "offline"}:
                        spoken = self._speak_piper(text)
                        if (not spoken) and not self._active_cancel.is_set() and bool(self.config.get("tts_piper_fallback_edge", True)):
                            # Perfil "offline" cai para a voz online; isso fica explícito no log.
                            log.warning("voz local Piper indisponível; usando Edge TTS (online) como fallback: %s", self.last_tts_error or "motivo desconhecido")
                            spoken = self._speak_edge_tts(text)

                    # Perfil natural recomendado: Edge-TTS -> Piper local -> SAPI5.
                    elif profile in {"edge_tts_728", "edge_tts", "jarvis_ia_sombria", "ia_sombria", "jarvis"}:
                        spoken = self._speak_edge_tts(text)
                        if not spoken and not self._active_cancel.is_set():
                            spoken = self._speak_piper(text)

                    if not spoken and not self._active_cancel.is_set():
                        # Ultimo fallback local do Windows.
                        if not sapi_disponivel:
                            if not self.last_tts_error:
                                self.last_tts_error = "SAPI indisponível (COM não inicializou)"
                            continue
                        log.warning("voz selecionada indisponível; usando SAPI do Windows como último recurso: %s", self.last_tts_error or "motivo desconhecido")
                        if voice is None:
                            voice = win32com.client.Dispatch("SAPI.SpVoice")
                            voice.Volume = int(self.config.get("tts_fallback_volume", 96))
                            self._select_tts_voice(voice)
                        voice.Rate = int(self.config.get("tts_fallback_rate", 2))
                        self.tts_status = "Falando"
                        voice.Speak(text, 1)
                        spoken = True
                        self.last_tts_metrics = {"engine": "windows_sapi", "voice": voice.Voice.GetDescription()}
                        while not voice.WaitUntilDone(30):
                            if self._active_cancel.is_set():
                                voice.Speak("", 3)
                                break
                except Exception as exc:
                    self.last_tts_error = type(exc).__name__ + ": " + str(exc)
                    self.tts_status = "Falha na fala: " + self.last_tts_error
                    log.warning("falha ao falar (motor ativo): %s", type(exc).__name__)
                finally:
                    self._tts_speaking.clear()
                    if spoken and not self._active_cancel.is_set() and self.last_tts_error:
                        # Áudio entregue (inclusive por fallback): o erro de um
                        # motor anterior não pode fazer a UI acusar falha.
                        log.info("TTS entregue após fallback; limpando erro anterior: %s", self.last_tts_error)
                        self.last_tts_error = ""
                    self.tts_status = ("Falha na voz selecionada: " + self.last_tts_error
                                       if self.last_tts_error else "Voz pronta")
                    self._end_visual_speech()
                    self._tts_epoch += 1
                    self._last_tts_end = time.monotonic()
                    if receipt is not None:
                        state = 'cancelled' if self._active_cancel.is_set() else 'done' if spoken and not self.last_tts_error else 'failed'
                        receipt.update(state=state, error=self.last_tts_error)
                    self._save_tts_diagnostic(speech_started)
            if pythoncom is not None:
                pythoncom.CoUninitialize()
        except Exception as exc:
            self.last_tts_error = type(exc).__name__ + ": " + str(exc)
            self.tts_status = "Falha na saída de voz: " + self.last_tts_error
            log.warning("falha na thread de saída de voz: %s", type(exc).__name__)
            if receipt is not None and receipt['state'] in ('queued', 'speaking'):
                receipt.update(state='failed', error=self.last_tts_error)
            while True:
                try:
                    pending = self._tts_queue.get_nowait()
                except queue.Empty:
                    break
                if pending is not None and len(pending) == 3:
                    pending[2].update(state='failed', error=self.last_tts_error)
            return

    def _save_tts_diagnostic(self, started):
        """Keep the actual output result, without recording spoken text or keys."""
        try:
            import json
            path = ROOT / 'logs/tts_last.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {'profile': getattr(self, '_active_tts_profile', self.config.get('tts_profile')), 'error': self.last_tts_error,
                    'recorded_at': __import__('datetime').datetime.now().astimezone().isoformat(),
                    'cancelled': self._active_cancel.is_set(), 'status': self.tts_status,
                    'elapsed_ms': round((time.perf_counter() - started) * 1000, 1),
                    'metrics': self.last_tts_metrics}
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            temp.replace(path)
        except Exception as exc:
            log.warning("não consegui gravar diagnóstico do TTS: %s", type(exc).__name__)

    def _select_tts_voice(self, voice):
        hints = [str(x).lower() for x in self.config.get(
            "tts_voice_hints", ["antonio", "daniel", "male", "masculino", "pt-br", "brazil", "portuguese"]
        )]
        try:
            voices = voice.GetVoices()
            scored = []
            for i in range(voices.Count):
                token = voices.Item(i)
                desc = str(token.GetDescription()).lower()
                token_id = str(getattr(token, "Id", "")).lower()
                blob = desc + " " + token_id
                preferred = str(self.config.get("tts_windows_voice", "") or "").lower()
                if preferred and preferred in blob:
                    voice.Voice = token
                    return
                score = 0
                for idx, hint in enumerate(hints):
                    if hint and hint in blob:
                        score += max(1, 20 - idx)
                # Evita escolher uma voz feminina so porque e pt-BR quando houver masculina instalada.
                if any(x in blob for x in ("antonio", "daniel", "male", "masculino")):
                    score += 40
                if any(x in blob for x in ("pt-br", "brazil", "portuguese")):
                    score += 18
                if score:
                    scored.append((score, token))
            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                voice.Voice = scored[0][1]
        except Exception as exc:
            log.warning("não consegui selecionar voz SAPI: %s", type(exc).__name__)

    def shutdown(self):
        self.stop_speaking()
        if self._qwen is not None:
            self._qwen.close()
        try:
            self._tts_queue.put_nowait(None)
        except Exception as exc:
            log.warning("não consegui encerrar a fila TTS: %s", type(exc).__name__)
