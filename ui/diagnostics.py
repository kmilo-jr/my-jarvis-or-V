"""On-demand checks; network probes never run on the GUI thread."""
import threading

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit


class DiagnosticsDialog(QDialog):
    checked = Signal(str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._checking = False
        self.setWindowTitle("Diagnóstico do V")
        self.resize(620, 450)
        self.setStyleSheet("""
            QDialog { background: #101923; }
            QLabel, QTextEdit { color: #e6f1f6; font: 11pt 'Segoe UI'; }
            QTextEdit { background: #0b121a; border: 1px solid #405466; padding: 8px; }
            QPushButton { color: #e6f1f6; background: #243848; border: 1px solid #52738a;
                          border-radius: 5px; padding: 8px; font: 10pt 'Segoe UI'; }
            QPushButton:hover { background: #34536a; }
            QPushButton:disabled { color: #91a1af; }
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Verificação sob demanda • não altera suas configurações"))
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report)
        self.refresh_button = QPushButton("Verificar novamente")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        mic = QPushButton("Ativar / reconectar microfone")
        mic.clicked.connect(self.reconnect_microphone)
        layout.addWidget(mic)
        self.mic_button = mic
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(100)
        self._reconnect_timer.timeout.connect(self._finish_reconnect)
        self.checked.connect(self._show_result)

    def reconnect_microphone(self):
        w = self.window
        self.mic_button.setEnabled(False)
        self._reconnect_attempts = 0
        if w.voice_thread is not None and w.voice_thread.isRunning():
            w.stop_continuous_voice()
            self.report.append("Aguardando a captura atual terminar para reconectar…")
            self._reconnect_timer.start()
            return
        self._finish_reconnect()

    def _finish_reconnect(self):
        w = self.window
        if w.voice_thread is not None and w.voice_thread.isRunning():
            self._reconnect_attempts += 1
            if self._reconnect_attempts >= 100:
                self._reconnect_timer.stop()
                self.mic_button.setEnabled(True)
                self.report.append("A captura ainda está terminando. Tente reconectar em instantes.")
            return
        self._reconnect_timer.stop()
        self.mic_button.setEnabled(True)
        w._load_mics()
        w.start_continuous_voice()
        self.refresh()

    def closeEvent(self, event):
        self._reconnect_timer.stop()
        self.mic_button.setEnabled(True)
        super().closeEvent(event)

    def refresh(self):
        if self._checking:
            return
        self._checking = True
        self.refresh_button.setEnabled(False)
        self.report.setPlainText("Verificando microfone, IA e Spotify…")
        w = self.window
        device = w.mic_combo.currentData()
        voice_on = w.voice_enabled
        voice_error = w._last_voice_error
        tts_on = w.tts_toggle.isChecked()
        provider = getattr(w, "remote_diagnostics_provider", None)
        remote = provider() if provider else None

        def check():
            lines = []
            try:
                mic = w.voice_engine.validate_input_device(device)
                lines.append(f"Microfone: {mic.get('name', 'padrão')} • {'escuta ativa' if voice_on else 'escuta desativada'}")
            except Exception as exc:
                lines.append(f"Microfone: indisponível ({type(exc).__name__}). Confira a conexão e use reconectar.")
            if voice_error:
                lines.append("A última sessão de voz falhou. Consulte a conversa para detalhes e tente reconectar.")
            lines.append("Whisper: " + ("carregado" if w.voice_engine._model is not None else "ainda não carregado; ative a voz contínua"))
            lines.append(f"Saída de voz: {'ativada' if tts_on else 'desativada'} • perfil {w.voice_engine.config.get('tts_profile', 'edge_tts_728')}")
            if w.voice_engine.last_tts_error:
                lines.append("Última falha de áudio: " + w.voice_engine.last_tts_error)
            metrics = dict(getattr(w.voice_engine, 'last_tts_metrics', {}) or {})
            if 'device_underflows' in metrics:
                lines.append(f"Última fala: {metrics['device_underflows']} falha(s) de alimentação do dispositivo; "
                             f"{metrics.get('buffer_gap_ms', 0):.0f} ms de espera por áudio. "
                             "Esses indicadores ajudam a distinguir interrupções de reprodução de sons gerados pela voz.")
            lines.append("A reprodução e a qualidade do áudio precisam de um teste audível.")
            try:
                brain = getattr(w.orchestrator, 'brain', None)
                result = brain.status() if brain else {}
                lines.append("IA: " + (f"online • {result.get('provider', '')}" if result.get('online') else "indisponível; confira conexão e configuração da IA"))
            except Exception as exc:
                lines.append(f"IA: verificação falhou ({type(exc).__name__})")
            try:
                from spotify_bridge import health
                code, result = health()
                age = result.get('extension_age_s')
                connected = code == 200 and result.get('extension_seen') and age is not None and age < 15
                lines.append("Spotify: " + ("extensão conectada" if connected else "sem conexão recente; abra o Spotify e confira o Spicetify Bridge"))
            except Exception as exc:
                lines.append(f"Spotify: verificação falhou ({type(exc).__name__})")
            if remote is None:
                lines.append("Remote: estado indisponível neste inicializador; use a interface Dual.")
            else:
                lines.append("Remote local: " + ("servidor iniciado" if remote.get('server') else "servidor não iniciado"))
            try:
                self.checked.emit("\n\n".join(lines))
            except RuntimeError:
                pass  # Window closed during a network probe.

        threading.Thread(target=check, name="V-Diagnostics", daemon=True).start()

    def _show_result(self, report):
        self.report.setPlainText(report)
        self._checking = False
        self.refresh_button.setEnabled(True)
