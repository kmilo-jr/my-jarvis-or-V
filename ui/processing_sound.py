from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl


class ProcessingSoundController(QObject):
    """Som ambiente discreto enquanto o V está processando.

    O efeito começa com pequeno atraso para não tocar em comandos instantâneos.
    Usa QSoundEffect quando disponível e cai para winsound no Windows.
    """

    def __init__(self, voice_engine=None, config=None, parent=None):
        super().__init__(parent)
        self.voice_engine = voice_engine
        self.config = dict(config or {})
        self.enabled = bool(self.config.get("processing_sound_enabled", True))
        self.delay_ms = max(0, int(self.config.get("processing_sound_delay_ms", 260)))
        self.volume = max(0.0, min(1.0, float(self.config.get("processing_sound_volume", 0.16))))
        base = Path(__file__).resolve().parent.parent
        configured = str(self.config.get("processing_sound_file", "assets/sounds/v_processing.wav"))
        p = Path(configured)
        self.sound_path = p if p.is_absolute() else base / p
        self._active = False
        self._wanted = False
        self._qt_effect = None
        self._backend = "none"

        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.timeout.connect(self._start_now)
        self._prepare_backend()

    def _prepare_backend(self):
        if not self.sound_path.exists():
            return
        try:
            from PySide6.QtMultimedia import QSoundEffect
            fx = QSoundEffect(self)
            fx.setSource(QUrl.fromLocalFile(str(self.sound_path)))
            fx.setLoopCount(QSoundEffect.Infinite)
            fx.setVolume(self.volume)
            self._qt_effect = fx
            self._backend = "qt"
            return
        except Exception:
            pass
        try:
            import winsound  # noqa: F401
            self._backend = "winsound"
        except Exception:
            self._backend = "none"

    @property
    def backend(self) -> str:
        return self._backend

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.stop()

    def schedule(self):
        self._wanted = True
        if not self.enabled or self._active or self._backend == "none":
            return
        self._delay.start(self.delay_ms)

    def _set_external_audio(self, active: bool):
        try:
            fn = getattr(self.voice_engine, "set_external_audio_active", None)
            if fn:
                fn(bool(active))
        except Exception:
            pass

    def _start_now(self):
        if not self.enabled or not self._wanted or self._active:
            return
        try:
            if self._backend == "qt" and self._qt_effect is not None:
                self._qt_effect.play()
            elif self._backend == "winsound":
                import winsound
                winsound.PlaySound(str(self.sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP | winsound.SND_NODEFAULT)
            else:
                return
            self._active = True
            self._set_external_audio(True)
        except Exception:
            self._active = False
            self._set_external_audio(False)

    def stop(self):
        self._wanted = False
        self._delay.stop()
        if not self._active:
            self._set_external_audio(False)
            return
        try:
            if self._backend == "qt" and self._qt_effect is not None:
                self._qt_effect.stop()
            elif self._backend == "winsound":
                import winsound
                winsound.PlaySound(None, winsound.SND_ASYNC)
        except Exception:
            pass
        finally:
            self._active = False
            self._set_external_audio(False)

    def shutdown(self):
        self.stop()
