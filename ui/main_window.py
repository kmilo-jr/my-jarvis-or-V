from __future__ import annotations
import datetime
import difflib
import json
from pathlib import Path
import time
import threading
import random
import re
from collections import deque
import psutil
import versao
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt, QRect
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextEdit,
    QLineEdit, QPushButton, QProgressBar, QComboBox, QCheckBox
)
from .theme import APP_STYLE
from .neural_core import NeuralCoreWidget
from .processing_sound import ProcessingSoundController
from core.functional_engine import has_wake_word, strip_wake_word
from voice.conversation import ConversationWindow, action_acknowledgement
from voice.task_feedback import progress_label


class CommandWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    speech = Signal(str)
    def __init__(self, orchestrator, text, confirm_cb=None, briefing_context=None):
        super().__init__(); self.orchestrator = orchestrator; self.text = text; self.confirm_cb = confirm_cb
        self.briefing_context = briefing_context
    @Slot()
    def run(self):
        try:
            if self.briefing_context is not None:
                from core.daily_briefing import explain_card
                from core.functional_engine import FunctionalResult
                item, generation = self.briefing_context
                answer = explain_card(item, getattr(self.orchestrator, 'brain', None))
                self.finished.emit([FunctionalResult(True, True, answer, 'DETALHES DO RESUMO',
                    {'kind': 'briefing_detail', 'generation': generation})])
                return
            result = self.orchestrator.handle(
                self.text, self.confirm_cb,
                progress_callback=lambda s: self.progress.emit(s),
                speech_callback=lambda chunk: self.speech.emit(chunk),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MicTestWorker(QObject):
    finished = Signal(str, object)
    failed = Signal(str)
    def __init__(self, engine, device):
        super().__init__(); self.engine = engine; self.device = device
    @Slot()
    def run(self):
        try:
            text, meta = self.engine.test_microphone(self.device, seconds=3.0)
            self.finished.emit(text, meta)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ContinuousVoiceWorker(QObject):
    heard = Signal(str, object)
    status = Signal(str)
    failed = Signal(str)
    stopped = Signal()
    calibrated = Signal(object)

    def __init__(self, engine, device, seconds=0.0):
        super().__init__()
        self.engine = engine
        self.device = device
        self._stop_event = threading.Event()

    def request_stop(self):
        self._stop_event.set()

    @Slot()
    def run(self):
        try:
            # Carrega o modelo ANTES da primeira frase. Na primeira execução
            # pode haver download; o status deixa isso explícito.
            self.status.emit("LOADING WHISPER")
            self.engine.preload_model(stage_callback=lambda st: self.status.emit(st))
            if self._stop_event.is_set():
                return

            # Calibração curta do ruído. Não é biometria e não altera o Core.
            profile = self.engine.calibrate_ambient(
                self.device,
                stop_event=self._stop_event,
                stage_callback=lambda st: self.status.emit(st),
            )
            if profile.get("cancelled"):
                return
            self.calibrated.emit(profile)

            reconnects = 0
            max_reconnects = int(self.engine.config.get("mic_auto_reconnect_attempts", 3))
            while not self._stop_event.is_set():
                if not self.engine.voice_input_allowed():
                    time.sleep(0.12)
                    continue
                try:
                    text, meta = self.engine.listen_and_transcribe(
                        self.device,
                        stop_event=self._stop_event,
                        stage_callback=lambda st: self.status.emit(st),
                    )
                    reconnects = 0
                except Exception:
                    reconnects += 1
                    if reconnects > max_reconnects:
                        raise
                    self.status.emit("RECONNECTING MIC")
                    self.engine.invalidate_ambient(self.device)
                    time.sleep(0.45)
                    continue
                if self._stop_event.is_set():
                    break
                reason = meta.get("reason")
                if meta.get('needs_repeat'):
                    self.status.emit('REPEAT PLEASE')
                    continue
                if reason in {"cancelled", "tts_overlap", "listen_timeout", "no_speech", "silence", "empty", "no_text"}:
                    self.status.emit("LISTENING")
                    time.sleep(0.05)
                    continue
                if text:
                    self.heard.emit(text, meta)
                self.status.emit("LISTENING")
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.stopped.emit()


def panel():
    f = QFrame(); f.setObjectName("panel"); return f


class MainWindow(QMainWindow):
    def __init__(self, orchestrator, registry, voice_engine, startup_greeting=True):
        super().__init__()
        self.orchestrator = orchestrator; self.registry = registry; self.voice_engine = voice_engine
        try:
            cfg_path = Path(__file__).resolve().parent.parent / "config" / "default.json"
            self.ui_config = json.loads(cfg_path.read_text(encoding="utf-8")).get("ui", {})
        except Exception:
            self.ui_config = {}
        self.processing_sound = ProcessingSoundController(self.voice_engine, self.ui_config, self)
        self.command_thread = None; self._command_worker = None
        self.pending_commands = deque()
        self.voice_thread = None; self._voice_worker = None
        self.mic_test_thread = None; self._mic_test_worker = None
        self._command_started_at = 0.0
        self._first_stream_speech_at = 0.0
        self._active_input_meta = {}
        self.voice_enabled = False
        self._speech_suppressed = False
        self._conversation = ConversationWindow(float(self.voice_engine.config.get("followup_seconds", 8)))
        self._acknowledged = False
        self._command_complete = True
        self._progress_message = ""
        self._command_serial = 0
        from core.initiative import InitiativeStore
        if not hasattr(orchestrator, "initiative_store"):
            orchestrator.initiative_store = InitiativeStore()
        self.initiative = orchestrator.initiative_store
        from core.system_watch import SystemWatch
        if not hasattr(orchestrator, 'system_watch'):
            orchestrator.system_watch = SystemWatch(self.initiative)
        self.system_watch = orchestrator.system_watch
        self._initiative_startup = bool(startup_greeting)
        self._voice_capture_busy = False
        self._initiative_error = ""
        self._active_request = ""
        self._task_stage = ""
        self._task_elapsed = 0.0
        self._last_result_text = ""
        self._last_response_spoken = ""
        self._last_voice_error = ""
        self.mode_switch_callback = None
        self._startup_greeting_enabled = bool(startup_greeting)

        # News Slide Mode. A troca de card acompanha o TTS real do V:
        # o próximo slide só aparece depois que a fala do anterior terminou.
        self._news_slide_items = []
        self._news_slide_index = -1
        self._news_slide_paused = False
        self._news_slide_voice_seen = False
        self._news_slide_wait_started = 0.0
        self._news_slide_current_done = False
        self._news_slide_timer = QTimer(self)
        self._news_slide_timer.setInterval(120)
        self._news_slide_timer.timeout.connect(self._poll_news_slideshow)
        self._active_panel_kind = ""

        self.setWindowTitle(f"{versao.TITULO} // NEWS VISUAL + MARKET DATA + FAST ACTIONS")
        self.resize(1500, 880); self.setMinimumSize(1180, 720); self.setStyleSheet(APP_STYLE)
        self._build_ui(); self._add_session_controls(); self._wire_internal_panel(); self._load_mics(); self._start_timers()
        from .game_mode import GameModeController
        self.game_mode = GameModeController(self, self.session_toolbar)
        self._mode_shortcut = QShortcut(QKeySequence("F6"), self)
        self._mode_shortcut.activated.connect(self.request_mode_switch)
        self.append_v(f"{versao.TITULO} // NEWS VISUAL + MARKET DATA + FAST ACTIONS + SPOTIFY")
        if self._startup_greeting_enabled:
            QTimer.singleShot(700, self._startup_greeting)

    def _add_session_controls(self):
        toolbar = self.addToolBar("Controles do V")
        self.session_toolbar = toolbar
        toolbar.setMovable(False)
        toolbar.addAction('Projetos').triggered.connect(self.show_project_center)
        toolbar.addAction('O que aconteceu?').triggered.connect(self.show_failure_help)
        toolbar.addAction('Notificações').triggered.connect(self.show_notification_center)
        toolbar.addAction('Memórias').triggered.connect(self.show_memory_center)
        toolbar.addAction('Conexões').triggered.connect(self.show_connections_center)
        toolbar.addAction('Editar bom dia').triggered.connect(self.show_briefing_editor)
        briefing_action = toolbar.addAction('Resumo do dia')
        briefing_action.triggered.connect(lambda: self.enqueue_command('resumo do dia', source='text'))
        camera_action = toolbar.addAction('Câmera')
        camera_action.triggered.connect(self.show_camera)
        stop = toolbar.addAction("Interromper fala [Esc]")
        stop.triggered.connect(self.interrupt_speech)
        self._stop_shortcut = QShortcut(QKeySequence("Escape"), self)
        self._stop_shortcut.activated.connect(self.interrupt_speech)
        diagnostics = toolbar.addAction("Diagnóstico [F8]")
        diagnostics.triggered.connect(self.show_diagnostics)
        self._diagnostics_shortcut = QShortcut(QKeySequence("F8"), self)
        self._diagnostics_shortcut.activated.connect(self.show_diagnostics)
        self.barge_in_toggle = QCheckBox("Interromper por voz (use fones)")
        self.barge_in_toggle.setToolTip("Com voz contínua ativa, diga V, para ou V seguido de outro pedido. Use fones para evitar eco.")
        self.barge_in_toggle.setChecked(bool(self.voice_engine.config.get("barge_in_enabled", False)))
        self.barge_in_toggle.toggled.connect(lambda enabled: self.voice_engine.config.update(barge_in_enabled=enabled))
        toolbar.addWidget(self.barge_in_toggle)
        self.followup_toggle = QCheckBox("Conversa contínua")
        self.followup_toggle.setToolTip(f"Após a resposta a um pedido por voz, aceita o próximo pedido por {self._conversation.seconds:g} segundos sem repetir V.")
        self.followup_toggle.setChecked(bool(self.voice_engine.config.get("followup_enabled", True)))
        self.followup_toggle.toggled.connect(self._toggle_followup)
        toolbar.addWidget(self.followup_toggle)
        self.followup_label = QLabel("")
        toolbar.addWidget(self.followup_label)
        routines = toolbar.addAction("Rotinas")
        routines.triggered.connect(self.show_routines)
        initiative = toolbar.addAction("Iniciativa")
        initiative.triggered.connect(self.show_initiative)
        interaction = toolbar.addAction("Voz e tarefas")
        interaction.triggered.connect(self.show_task_interaction)
        self._initiative_timer = QTimer(self)
        self._initiative_timer.setInterval(5000)
        self._initiative_timer.timeout.connect(self._poll_initiative)
        self._initiative_timer.start()
        self._followup_timer = QTimer(self)
        self._followup_timer.setInterval(200)
        self._followup_timer.timeout.connect(self._refresh_followup)
        self._followup_timer.start()

    def show_project_center(self):
        from .project_center import ProjectCenter
        if not hasattr(self, '_project_center'):
            self._project_center = ProjectCenter(self)
        self._project_center.refresh()
        self._project_center.show(); self._project_center.raise_()

    def show_failure_help(self):
        from .failure_help import FailureHelp
        if not hasattr(self, '_failure_help'):
            self._failure_help = FailureHelp(self)
        self._failure_help.refresh()
        self._failure_help.show(); self._failure_help.raise_()

    def show_notification_center(self):
        from .notification_center import NotificationCenter
        if not hasattr(self, '_notification_center'):
            self._notification_center = NotificationCenter(self)
        self._notification_center.show(); self._notification_center.raise_(); self._notification_center.activateWindow()

    def show_notification_toast(self, kind, text):
        """Mostra um aviso visual leve, sem abrir uma janela sobre o trabalho."""
        from .notification_center import NotificationToast
        host = self.centralWidget()
        if host is None:
            return
        if not hasattr(self, '_notification_toasts'):
            self._notification_toasts = []
        # Três avisos no máximo evitam acúmulo e mantêm a animação estável.
        while len(self._notification_toasts) >= 3:
            old = self._notification_toasts.pop(0)
            old.dismiss()
        labels = {'gmail': 'GMAIL', 'messages': 'MENSAGENS', 'alarms': 'ALARME', 'appointments': 'AGENDA', 'reminders': 'LEMBRETE'}
        toast = NotificationToast(host, labels.get(kind, 'V'), text, red=str(getattr(self, 'visual_theme', 'blue')).lower() == 'red')
        toast.closed.connect(self._remove_notification_toast)
        self._notification_toasts.append(toast)
        self._position_notification_toasts()

    def _remove_notification_toast(self, toast):
        if hasattr(self, '_notification_toasts') and toast in self._notification_toasts:
            self._notification_toasts.remove(toast)
        toast.hide(); toast.deleteLater()
        self._position_notification_toasts()

    def _position_notification_toasts(self):
        host = self.centralWidget()
        if host is None or not hasattr(self, '_notification_toasts'):
            return
        right = max(18, host.width() - 386)
        for index, toast in enumerate(self._notification_toasts):
            height = max(82, toast.sizeHint().height())
            target = QRect(right, 22 + index * (height + 10), 366, height)
            if toast.isVisible():
                toast.setGeometry(target)
            else:
                toast.reveal(target)

    def show_memory_center(self):
        from .memory_center import MemoryCenter
        if not hasattr(self, '_memory_center'):
            self._memory_center = MemoryCenter(self)
        self._memory_center.refresh()
        self._memory_center.show(); self._memory_center.raise_()

    def show_briefing_editor(self):
        from .briefing_editor import BriefingEditor
        if not hasattr(self, '_briefing_editor'):
            self._briefing_editor = BriefingEditor(self)
        self._briefing_editor.show(); self._briefing_editor.raise_()

    def show_connections_center(self):
        from .connections_center import ConnectionsCenter
        if not hasattr(self, '_connections_center'):
            self._connections_center = ConnectionsCenter(self)
        self._connections_center.show(); self._connections_center.raise_()

    def show_camera(self):
        if not hasattr(self, '_camera_panel'):
            from .camera_panel import CameraPanel
            self._camera_panel = CameraPanel(getattr(self.orchestrator, 'brain', None), self)
            self._camera_panel.answer.connect(self._camera_answer)
        self._camera_panel.show()
        self._camera_panel.raise_()
        return self._camera_panel

    def _camera_answer(self, text):
        self.append_v(text)
        self._last_response_spoken = text
        if self.tts_toggle.isChecked():
            self.voice_engine.speak(text)

    def show_task_interaction(self):
        from .task_interaction import TaskInteractionDialog
        if not hasattr(self, "_task_dialog") or not self._task_dialog.isVisible():
            self._task_dialog = TaskInteractionDialog(self)
        self._task_dialog.show()
        self._task_dialog.raise_()

    def repeat_last_response(self):
        if not self._last_response_spoken:
            self.statusBar().showMessage("Ainda não há resposta para repetir.", 5000)
            return
        if not self._command_complete:
            self.statusBar().showMessage("Aguarde o pedido atual terminar para repetir a resposta.", 5000)
            return
        if not self.tts_toggle.isChecked():
            self.statusBar().showMessage("Ative Respostas em voz alta para repetir.", 5000)
            return
        self.interrupt_speech()
        self.voice_engine.speak(self._last_response_spoken)
        self.set_state("SPEAKING")
        QTimer.singleShot(180, self._settle_state_after_audio)

    def show_initiative(self):
        from .initiative import InitiativeDialog
        if not hasattr(self, "_initiative_dialog") or not self._initiative_dialog.isVisible():
            self._initiative_dialog = InitiativeDialog(self, self.initiative)
        self._initiative_dialog.show()
        self._initiative_dialog.raise_()

    def _poll_initiative(self):
        try:
            if not hasattr(self.orchestrator, '_live_notifications'):
                from core.live_notifications import LiveNotifications
                self.orchestrator._live_notifications = LiveNotifications(self.initiative)
            self.orchestrator._live_notifications.tick()
            delivery = getattr(self.voice_engine, '_notice_delivery', None)
            if delivery and delivery[1]['state'] not in ('queued', 'speaking'):
                event_id, receipt = delivery
                self.initiative.voice_result(event_id, receipt['state'], receipt.get('error', ''))
                if receipt['state'] in ('failed', 'dropped'):
                    self.statusBar().showMessage('A fala do aviso falhou. Confira o histórico em Iniciativa; haverá até três tentativas.', 15000)
                self.voice_engine._notice_delivery = None
            if self._initiative_startup:
                self.initiative.startup_summary()
                self._initiative_startup = False
            self.initiative.schedule_break()
            try:
                self.system_watch.poll()
            except (OSError, RuntimeError):
                pass  # A missing sensor must not block reminders or alarms.
            busy = bool((self.command_thread is not None and self.command_thread.isRunning())
                        or self.pending_commands or self._voice_capture_busy
                        or bool(getattr(self, '_briefing_panel', None) and self._briefing_panel.active)
                        or self.voice_engine.is_speaking() or self.voice_engine.has_pending_speech()
                        or not self.voice_engine.voice_input_allowed()
                        or self._conversation.pending or self._conversation.deadline > time.monotonic()
                        or (self.mic_test_thread is not None and self.mic_test_thread.isRunning())
                        or self.input.hasFocus() and self.input.text().strip()
                        or getattr(self, "_initiative_dialog", None) and self._initiative_dialog.isVisible())
            game_active = bool(getattr(getattr(self, "game_mode", None), "enabled", False))
            notice = self.initiative.next_notice(busy=busy or game_active)
            if notice:
                text = self._notice_text(notice)
                if notice['kind'] == 'alarms':
                    from PySide6.QtWidgets import QApplication
                    QApplication.beep()
                self.append_v("AVISO • " + text)
                # Initiative events become visible in both places: the normal
                # conversation history and the dedicated notification tab.
                if notice['kind'] in ('gmail', 'messages'):
                    if not hasattr(self, '_notification_center'):
                        from .notification_center import NotificationCenter
                        self._notification_center = NotificationCenter(self)
                    self._notification_center.add_notice(notice['kind'], text, show_center=False)
                    self.show_notification_toast(notice['kind'], text)
                self.statusBar().showMessage(text, 15000)
                self._show_desktop_notice(text)
                self.initiative.delivered(notice['id'], voice_pending=notice.get('voice_requested', notice['voice']))
            # A busy alarm still appears immediately; its voice waits without being lost.
            # The receipt belongs to the shared engine so switching windows keeps it.
            if not getattr(self.voice_engine, '_notice_delivery', None) and self.tts_toggle.isChecked():
                spoken_notice = self.initiative.next_voice_notice(busy=busy, defer_common=game_active)
                if spoken_notice:
                    receipt = self.voice_engine.speak_tracked(self._notice_text(spoken_notice))
                    self.voice_engine._notice_delivery = (spoken_notice['id'], receipt)
                    self.set_state('SPEAKING')
                    QTimer.singleShot(180, self._settle_state_after_audio)
            self._initiative_error = ""
        except Exception as exc:
            error = f"Iniciativa indisponível: {type(exc).__name__}. Abra Iniciativa para conferir."
            if error != self._initiative_error:
                self.statusBar().showMessage(error, 15000)
            self._initiative_error = error

    @staticmethod
    def _notice_text(notice):
        text = notice['title']
        if notice['kind'] in ('reminders', 'alarms', 'appointments'):
            when = datetime.datetime.fromtimestamp(notice['due']).strftime('%d/%m às %H:%M')
            label = {'reminders': 'Lembrete', 'alarms': 'Alarme', 'appointments': 'Compromisso'}[notice['kind']]
            return f'{label} de {when}: {text}'
        return text

    def _show_desktop_notice(self, text):
        from PySide6.QtWidgets import QSystemTrayIcon, QStyle
        if self.isActiveWindow() or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if not hasattr(self, "_notice_tray"):
            self._notice_tray = QSystemTrayIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation), self)
            self._notice_tray.setToolTip("V / Iniciativa")
            self._notice_tray.messageClicked.connect(self._open_from_notice)
            self._notice_tray.activated.connect(lambda reason: self._open_from_notice() if reason == QSystemTrayIcon.Trigger else None)
            self._notice_tray.show()
        self._notice_tray.showMessage("V / Iniciativa", text, QSystemTrayIcon.Information, 10000)

    def _open_from_notice(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _initiative_completion(self, results=None, failed=False):
        try:
            if any(getattr(r, "skill", "") == "MODO TRABALHO" and r.ok for r in (results or [])):
                self.initiative.work_session(True)
            elapsed = time.perf_counter() - self._command_started_at if self._command_started_at else 0
            if elapsed >= 10 and not self.isActiveWindow():
                ok = bool(results) and not failed and all(r.ok for r in results)
                prefix = "Pedido concluído" if ok else "Pedido terminou com pendências"
                self.initiative.add(f"{prefix}: {self._active_request[:170]}. Confira o resultado na conversa.", time.time(), "completions")
        except Exception as exc:
            self.statusBar().showMessage(f"Não consegui registrar o aviso: {type(exc).__name__}.", 10000)

    def show_routines(self):
        from .routines import RoutinesDialog
        if not hasattr(self, "_routines_dialog") or not self._routines_dialog.isVisible():
            self._routines_dialog = RoutinesDialog(self)
        self._routines_dialog.show()
        self._routines_dialog.raise_()

    def _toggle_followup(self, enabled):
        self.voice_engine.config["followup_enabled"] = enabled
        if not enabled:
            self._conversation.cancel()
        self._refresh_followup()

    def _refresh_followup(self):
        remaining = self._conversation.deadline - time.monotonic()
        self.followup_label.setText(f"Pode continuar · {max(1, int(remaining + 0.999))}s" if remaining > 0 and self.voice_enabled else "")

    def show_diagnostics(self):
        from .diagnostics import DiagnosticsDialog
        if not hasattr(self, "_diagnostics_dialog"):
            self._diagnostics_dialog = DiagnosticsDialog(self)
        self._diagnostics_dialog.show()
        self._diagnostics_dialog.raise_()
        self._diagnostics_dialog.refresh()

    def interrupt_speech(self):
        briefing = getattr(self, '_briefing_panel', None)
        if briefing is not None:
            briefing.close_briefing()
        self._conversation.cancel()
        self._speech_suppressed = True
        self._cancel_news_slideshow()
        self.processing_sound.stop()
        self.voice_engine.stop_speaking()
        self.last_action.setText("Fala interrompida. Ações em execução continuam.")
        QTimer.singleShot(100, self._settle_state_after_audio)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root); outer.setContentsMargins(18, 12, 18, 14)
        header = QHBoxLayout(); title = QLabel("V"); title.setObjectName("title")
        brand = QLabel(f"{versao.TITULO.upper()}  //  NEURAL INTERFACE + PROCESS FX"); brand.setObjectName("subtle")
        self.state_label = QLabel("● SYSTEM ONLINE"); self.state_label.setObjectName("statusOnline"); self.clock = QLabel("")
        header.addWidget(title); header.addWidget(brand); header.addStretch(1); header.addWidget(self.state_label); header.addSpacing(20); header.addWidget(self.clock); outer.addLayout(header)
        body = QHBoxLayout(); body.setSpacing(12); outer.addLayout(body, 1)

        left = panel(); ll = QVBoxLayout(left); ll.setContentsMargins(14,14,14,14)
        sec = QLabel("CONVERSA"); sec.setObjectName("section"); ll.addWidget(sec)
        self.chat = QTextEdit(); self.chat.setReadOnly(True); ll.addWidget(self.chat, 1)
        row = QHBoxLayout(); self.input = QLineEdit(); self.input.setPlaceholderText("Digite qualquer coisa — a mensagem sempre aparecerá aqui")
        self.input.returnPressed.connect(self.submit_text)
        self.send_btn = QPushButton("ENVIAR"); self.send_btn.clicked.connect(self.submit_text)
        row.addWidget(self.input, 1); row.addWidget(self.send_btn); ll.addLayout(row); body.addWidget(left, 36)

        center = panel(); cl = QVBoxLayout(center); cl.setContentsMargins(10,10,10,10)
        top = QHBoxLayout(); st = QLabel("NEURAL CORE"); st.setObjectName("section"); self.intent_label = QLabel("READY"); self.intent_label.setObjectName("subtle")
        top.addWidget(st); top.addStretch(1); top.addWidget(self.intent_label); cl.addLayout(top)
        self.neural = NeuralCoreWidget(); cl.addWidget(self.neural, 1)
        motto = QLabel("REMEMBER  •  UNDERSTAND  •  PLAN  •  EXECUTE  •  VERIFY"); motto.setAlignment(Qt.AlignCenter); motto.setObjectName("subtle"); cl.addWidget(motto); body.addWidget(center, 38)

        right = panel(); rl = QVBoxLayout(right); rl.setContentsMargins(14,14,14,14)
        s = QLabel("SISTEMA"); s.setObjectName("section"); rl.addWidget(s)
        self.cpu = QProgressBar(); self.ram = QProgressBar(); self.cpu.setFormat("CPU %p%"); self.ram.setFormat("RAM %p%"); rl.addWidget(self.cpu); rl.addWidget(self.ram)
        rl.addSpacing(10); sk = QLabel("SKILLS ATIVAS"); sk.setObjectName("section"); rl.addWidget(sk)
        names = ", ".join(x.name.upper() for x in self.registry.skills); lab = QLabel(names); lab.setWordWrap(True); lab.setObjectName("subtle"); rl.addWidget(lab)
        rl.addSpacing(12); vc = QLabel("VOICE / WHISPER"); vc.setObjectName("section"); rl.addWidget(vc)
        self.mic_combo = QComboBox(); rl.addWidget(self.mic_combo)
        self.voice_toggle = QPushButton("ATIVAR VOZ CONTÍNUA"); self.voice_toggle.clicked.connect(self.toggle_continuous_voice); rl.addWidget(self.voice_toggle)
        self.voice_status = QLabel("VOICE OFF — ative uma vez e depois apenas diga: V, ..."); self.voice_status.setWordWrap(True); self.voice_status.setObjectName("subtle"); rl.addWidget(self.voice_status)
        rl.addWidget(QLabel("AMOSTRA DA VOZ"))
        self.xtts_voice_combo = QComboBox()
        self.xtts_voice_combo.addItem("V Prime · atual", "v_prime")
        self.xtts_voice_combo.addItem("V Alt · nova amostra", "v_alt")
        from voice.preferences import setup_voice_selector
        setup_voice_selector(self.xtts_voice_combo, self.voice_engine.config)
        self.xtts_voice_combo.currentIndexChanged.connect(self._change_xtts_voice)
        rl.addWidget(self.xtts_voice_combo)
        vr = QHBoxLayout(); self.test_mic = QPushButton("TESTAR MIC"); self.test_mic.clicked.connect(self.start_mic_test)
        self.test_voice = QPushButton("TESTAR VOZ V"); self.test_voice.clicked.connect(self.test_v_voice)
        self.tts_toggle = QCheckBox("RESPOSTA POR VOZ"); self.tts_toggle.setChecked(True); vr.addWidget(self.test_mic); vr.addWidget(self.test_voice); vr.addWidget(self.tts_toggle); rl.addLayout(vr)
        fxr = QHBoxLayout()
        self.process_sound_toggle = QCheckBox("SOM AO PROCESSAR")
        self.process_sound_toggle.setChecked(self.processing_sound.enabled)
        self.process_sound_toggle.toggled.connect(self._toggle_processing_sound)
        self.process_sound_status = QLabel(f"PROCESS FX: {self.processing_sound.backend.upper()}")
        self.process_sound_status.setObjectName("subtle")
        fxr.addWidget(self.process_sound_toggle); fxr.addStretch(1); fxr.addWidget(self.process_sound_status); rl.addLayout(fxr)
        try:
            from spotify_api import SpotifyClient
            sc = SpotifyClient()
            sp_text = "SPOTIFY API: CONFIGURADA" if sc.configured else "SPOTIFY API: FALTA CONFIGURAR"
        except Exception:
            sp_text = "SPOTIFY API: INDISPONIVEL"
        self.spotify_api_status = QLabel(sp_text); self.spotify_api_status.setObjectName("subtle"); rl.addWidget(self.spotify_api_status)
        try:
            bs = getattr(self.orchestrator, "brain", None)
            st = bs.status() if bs and hasattr(bs, "status") else {"online": False}
            ai_text = f"AI BRAIN: ONLINE • {st.get('model','')}" if st.get("online") else "AI BRAIN: OFFLINE • configure Gemini ou Ollama"
        except Exception:
            ai_text = "AI BRAIN: STATUS INDISPONÍVEL"
        self.ai_status = QLabel(ai_text); self.ai_status.setObjectName("subtle"); rl.addWidget(self.ai_status)
        try:
            mem = getattr(self.orchestrator, "memory", None)
            count = mem.count() if mem is not None and hasattr(mem, "count") else len(mem.get_memories()) if mem is not None else 0
            mem_text = f"MEMÓRIA LOCAL: {count} item(ns) • explícita e persistente"
        except Exception:
            mem_text = "MEMÓRIA LOCAL: status indisponível"
        self.memory_status = QLabel(mem_text); self.memory_status.setObjectName("subtle"); rl.addWidget(self.memory_status)
        self.latency_status = QLabel("LATÊNCIA: aguardando medição"); self.latency_status.setObjectName("subtle"); rl.addWidget(self.latency_status)
        build = QLabel(f"BUILD ID: {versao.BUILD}"); build.setObjectName("statusOnline"); rl.addWidget(build)
        hint = QLabel("Sem push-to-talk. Ao ativar, fique em silêncio por ~1 segundo para calibrar o ambiente. Depois fale normalmente: V, ... O V espera sua frase terminar antes de transcrever."); hint.setWordWrap(True); hint.setObjectName("subtle"); rl.addWidget(hint)
        rl.addStretch(1); self.last_action = QLabel("Nenhuma ação executada."); self.last_action.setWordWrap(True); self.last_action.setObjectName("subtle"); rl.addWidget(self.last_action); body.addWidget(right, 26)

    def _load_mics(self):
        try:
            import sounddevice as sd
            self.mic_combo.blockSignals(True)
            self.mic_combo.clear()
            default_idx = None
            try:
                default_pair = sd.default.device
                default_idx = int(default_pair[0]) if default_pair and default_pair[0] is not None and int(default_pair[0]) >= 0 else None
            except Exception:
                default_idx = None

            self.mic_combo.addItem("Automático · microfone padrão do Windows", None)
            preferred = str(self.voice_engine.config.get("preferred_input_device_name", "") or "").strip().lower()
            preferred_row = -1
            default_row = 0
            for idx, name, rate in self.voice_engine.input_devices():
                self.mic_combo.addItem(f"{idx}: {name} ({rate} Hz)", idx)
                row = self.mic_combo.count() - 1
                if default_idx is not None and idx == default_idx:
                    default_row = row
                if preferred and preferred in name.lower():
                    preferred_row = row
            self.mic_combo.setCurrentIndex(preferred_row if preferred_row >= 0 else default_row)
            self.mic_combo.blockSignals(False)
            try:
                self.mic_combo.currentIndexChanged.disconnect(self._mic_selection_changed)
            except Exception:
                pass
            self.mic_combo.currentIndexChanged.connect(self._mic_selection_changed)
        except Exception as exc:
            self.mic_combo.clear(); self.mic_combo.addItem(f"Áudio indisponível: {exc}", None)

    def _mic_selection_changed(self, _index=0):
        try:
            device = self.mic_combo.currentData()
            self.voice_engine.invalidate_ambient()
            name = ""
            if device is not None:
                info, _rate = self.voice_engine._device_info(device)
                name = str(info.get("name", "")).strip()
            cfg_path = Path(__file__).resolve().parent.parent / "config" / "default.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg.setdefault("voice", {})["preferred_input_device_name"] = name
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self.voice_engine.config["preferred_input_device_name"] = name
            if hasattr(self, "voice_status"):
                self.voice_status.setText("MIC selecionado • será recalibrado ao ativar a voz")
        except Exception:
            pass

    def request_mode_switch(self):
        callback = getattr(self, "mode_switch_callback", None)
        if callable(callback):
            callback()
        else:
            self.append_v("Alternância visual disponível no iniciador Dual Interface.")

    def _start_timers(self):
        self.timer = QTimer(self); self.timer.timeout.connect(self._update_system); self.timer.start(1000); self._update_system()

    def _update_system(self):
        self.cpu.setValue(int(psutil.cpu_percent(None))); self.ram.setValue(int(psutil.virtual_memory().percent)); self.clock.setText(datetime.datetime.now().strftime("%H:%M:%S  •  %d/%m/%Y"))

    def _esc(self, t):
        import html; return html.escape(str(t)).replace("\n", "<br>")
    def append_user(self, text):
        self.chat.append(f"<p style='color:#8aaec0'><b>VOCÊ</b><br>{self._esc(text)}</p>"); self.chat.ensureCursorVisible()
    def append_v(self, text):
        self.chat.append(f"<p style='color:#bff6ff'><b>V</b><br>{self._esc(text)}</p>"); self.chat.ensureCursorVisible()
        game = getattr(self, 'game_mode', None)
        if game is not None:
            game.quick_chat.set_reply(str(text))

    def submit_text(self):
        text = self.input.text().strip()
        if not text: return
        self.input.clear()
        self.enqueue_command(text, source="text")

    def request_briefing_details(self, item, generation):
        self.pending_commands.append(('Me explique melhor este assunto', 'text',
                                      {'briefing_context': (dict(item), generation)}, time.perf_counter()))
        self._pump_commands()

    def enqueue_command(self, text, source="text", input_meta=None):
        text = str(text or "").strip()
        if not text: return
        from core.functional_engine import normalize
        request = normalize(strip_wake_word(text))
        if request.rstrip('.!?') in {'o que aconteceu', 'qual foi o erro', 'por que falhou'}:
            self.append_user(text)
            self.show_failure_help()
            self.append_v(self._failure_help.message.text())
            return
        if request in {'abrir projetos', 'meus projetos'}:
            self.append_user(text)
            self.show_project_center()
            return
        from core.vision_commands import vision_command
        camera_action = vision_command(request)
        if camera_action:
            self.append_user(text)
            self.interrupt_speech()
            if camera_action == 'close':
                if hasattr(self, '_camera_panel'):
                    self._camera_panel.close()
                self._camera_answer('Câmera desligada.')
            else:
                camera = self.show_camera()
                if camera_action == 'open':
                    camera.start()
                elif camera_action == 'detect':
                    camera.detect_once()
                elif camera_action == 'describe':
                    camera.describe(request)
            return
        briefing = getattr(self, '_briefing_panel', None)
        if briefing is not None and briefing.handle_command(request):
            self.append_user(text)
            return
        if briefing is not None and briefing.isVisible():
            briefing.close_briefing()
        if request in {"modo jogo", "modo de jogo", "ir ao modo jogo", "ir para o modo jogo", "va para o modo jogo", "vai para o modo jogo", "entre no modo jogo", "entrar no modo jogo", "ative o modo jogo", "ativar modo jogo", "vou jogar", "estou jogando", "parei de jogar", "desative o modo jogo", "sair do modo jogo", "modo normal", "minimizar v", "recolher", "recolher v", "abrir interface"}:
            self.append_user(text)
            if request in {"minimizar v", "recolher v", "recolher"}:
                self.game_mode.minimize()
            elif request == "abrir interface":
                self.game_mode.restore()
            else:
                self.game_mode.set_enabled(request not in {"desative o modo jogo", "sair do modo jogo", "modo normal", "parei de jogar"})
            return
        if request in {"repita a ultima resposta", "repete a ultima resposta"}:
            self.append_user(text)
            self.repeat_last_response()
            return
        if request in {"status da tarefa", "como esta meu pedido", "como esta a tarefa"}:
            self.append_user(text)
            status = self._task_stage or "Ainda não há tarefa em execução."
            self.append_v(status)
            if self.tts_toggle.isChecked() and not self.voice_engine.is_speaking():
                self.voice_engine.speak(status)
            self.show_task_interaction()
            return
        if request in {"limpar fila", "limpe a fila", "cancele os pedidos da fila"}:
            self.append_user(text)
            count = len(self.pending_commands)
            self.pending_commands.clear()
            self.append_v(f"Removi {count} pedido(s) da fila. A ação em execução continua.")
            return
        from voice.commands import is_stop_request
        if is_stop_request(text):
            self.append_user(text)
            self.interrupt_speech()
            return
        if self.voice_engine.is_speaking():
            self.interrupt_speech()
        if self._news_slide_items:
            self._cancel_news_slideshow()
        # A mensagem aparece ANTES de qualquer Planner/Skill/Thread.
        self.append_user(text)
        self.pending_commands.append((text, source, dict(input_meta or {}), time.perf_counter()))
        self.last_action.setText(f"Fila: {len(self.pending_commands)} comando(s) aguardando.")
        self._pump_commands()

    def _pump_commands(self):
        if self.command_thread is not None and self.command_thread.isRunning(): return
        if not self.pending_commands:
            if not self.voice_engine.is_speaking(): self.set_state("READY")
            return
        text, source, input_meta, queued_at = self.pending_commands.popleft()
        self._active_request = text
        office = getattr(getattr(self, 'desktop_shell', None), 'office', None)
        if office is not None:
            office.begin_request(text)
        self._task_stage = "Preparando seu pedido."
        self._task_elapsed = 0.0
        self._conversation.cancel()
        if source == "voice" and self.voice_enabled and self.followup_toggle.isChecked():
            self._conversation.wait_for_reply()
        self._command_serial += 1
        self._command_complete = False
        self._acknowledged = False
        self._progress_message = ""
        self._speech_suppressed = False
        self._command_started_at = time.perf_counter(); self._first_stream_speech_at = 0.0; self._active_input_meta = input_meta
        self.set_state("PROCESSING"); self.last_action.setText(f"Executando: {text}")
        thread = QThread(self); worker = CommandWorker(self.orchestrator, text, None,
            briefing_context=input_meta.get('briefing_context')); worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._command_progress, Qt.QueuedConnection)
        worker.speech.connect(self._stream_speech, Qt.QueuedConnection)
        worker.finished.connect(self._deliver_command_result, Qt.QueuedConnection)
        worker.failed.connect(self._command_failed, Qt.QueuedConnection)
        worker.finished.connect(thread.quit); worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._command_thread_finished); thread.finished.connect(thread.deleteLater)
        self.command_thread = thread; self._command_worker = worker; thread.start()

    @Slot(object)
    def _deliver_command_result(self, results):
        # A registered, non-overridden receiver keeps subclass UI updates on
        # the GUI thread. Plain Python overrides can otherwise run in the worker.
        self._command_done(results)

    @Slot(str)
    def _command_progress(self, msg):
        self._progress_message = msg
        acknowledgement = action_acknowledgement(msg)
        self._task_stage = progress_label(msg)
        self.last_action.setText(self._task_stage)
        if acknowledgement and not self._acknowledged:
            serial = self._command_serial
            QTimer.singleShot(650, lambda: self._speak_action_progress(serial, msg, acknowledgement))

    def _speak_action_progress(self, serial, progress, text):
        if (serial != self._command_serial or self._command_complete or self._acknowledged
                or progress != self._progress_message or self._speech_suppressed
                or not self.voice_engine.config.get("task_progress_voice", True)
                or self._first_stream_speech_at or not self.tts_toggle.isChecked()):
            return
        self._acknowledged = True
        self.processing_sound.stop()
        self.voice_engine.speak(text)

    @Slot(str)
    def _stream_speech(self, chunk):
        chunk=str(chunk or "").strip()
        if self._speech_suppressed or not chunk or not self.tts_toggle.isChecked():
            return
        self.processing_sound.stop()
        self.set_state("SPEAKING")
        if not self._first_stream_speech_at:
            self._first_stream_speech_at=time.perf_counter()
        self.voice_engine.speak(chunk)

    def _wire_internal_panel(self):
        """Conecta controles do HUD somente nas interfaces que possuem painel."""
        panel = getattr(self, "info_panel", None)
        if panel is None:
            return
        try:
            panel.slideManualRequested.connect(self._news_slide_manual_requested)
        except Exception:
            pass
        try:
            panel.slideshowPauseChanged.connect(self._news_slide_pause_changed)
        except Exception:
            pass

    def _position_internal_panel(self):
        """Posiciona o HUD sem cobrir o núcleo e os controles principais."""
        panel = getattr(self, "info_panel", None)
        root = self.centralWidget()
        if panel is None or root is None or not panel.isVisible():
            return
        try:
            kind = str(getattr(self, "_active_panel_kind", "") or "").lower()
            w, h = panel.width(), panel.height()
            rw, rh = max(1, root.width()), max(1, root.height())
            if kind == "news" and not getattr(panel, "_expanded", False):
                # Espaço livre da UI orbital: abaixo do SYSTEM e acima do monitor.
                x = 18
                top_reserved = 145
                bottom_reserved = 250
                available = max(h, rh - top_reserved - bottom_reserved)
                y = top_reserved + max(0, (available - h) // 2)
                y = min(y, max(8, rh - h - bottom_reserved))
                y = max(8, y)
            else:
                x = max(8, (rw - w) // 2)
                y = max(8, (rh - h) // 2)
            panel.move(int(x), int(y))
            panel.raise_()
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        briefing = getattr(self, '_briefing_panel', None)
        if briefing is not None and briefing.isVisible():
            briefing.position()
        if hasattr(self, "info_panel"):
            QTimer.singleShot(0, self._position_internal_panel)

    @staticmethod
    def _news_slide_speech(item, index, total):
        title = re.sub(r"\s+", " ", str((item or {}).get("title", "") or "")).strip()
        source = re.sub(r"\s+", " ", str((item or {}).get("source", "") or "")).strip()
        snippet = re.sub(r"\s+", " ", str((item or {}).get("snippet", "") or "")).strip()

        # O RSS do Google costuma devolver a própria manchete no campo description.
        # Detectamos a duplicata por texto normalizado + similaridade, evitando
        # "título... título..." durante a apresentação.
        if title and snippet:
            import unicodedata
            def norm(x):
                x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode("ascii").lower()
                return re.sub(r"[^a-z0-9]+", " ", x).strip()
            nt, ns = norm(title), norm(snippet)
            duplicate = False
            if ns.startswith(nt):
                residue = ns[len(nt):].strip()
                duplicate = len(residue) < 100
                if not duplicate:
                    snippet = snippet[len(title):].lstrip(" -–—|:")
            else:
                head = ns[:max(len(nt) + 75, 120)]
                ratio = difflib.SequenceMatcher(None, nt, head[:max(1, len(nt))]).ratio() if nt else 0.0
                tt = set(nt.split()); ht = set(head.split())
                overlap = len(tt & ht) / max(1, len(tt))
                duplicate = ratio >= 0.78 or (overlap >= 0.82 and len(ns) <= len(nt) + 115)
            if duplicate:
                snippet = ""

        if len(snippet) > 330:
            snippet = snippet[:327].rsplit(' ', 1)[0].rstrip() + "..."
        from voice.news_speech import news_text
        title, snippet = news_text(title), news_text(snippet)
        # Position and publication remain visible on the slide. Speaking only
        # the news avoids separate generated counter/source announcements.
        if snippet:
            return f"{title}. {snippet}".strip()
        return f"{title}.".strip()

    def _start_news_slideshow(self, items):
        clean = [dict(x) for x in (items or []) if isinstance(x, dict) and str(x.get("title", "")).strip()]
        if not clean:
            return False
        self._news_slide_items = clean
        self._news_slide_index = 0
        self._news_slide_paused = False
        self._news_slide_current_done = False
        panel = getattr(self, "info_panel", None)
        if panel is not None:
            try:
                panel.set_paused(False)
                panel.set_slide_index(0, speaking=True)
            except Exception:
                pass
        self._speak_news_slide(0)
        return True

    def _speak_news_slide(self, index):
        if not self._news_slide_items:
            return
        index = max(0, min(int(index), len(self._news_slide_items) - 1))
        self._news_slide_index = index
        self._news_slide_voice_seen = False
        self._news_slide_wait_started = time.perf_counter()
        self._news_slide_current_done = False
        panel = getattr(self, "info_panel", None)
        if panel is not None:
            try:
                panel.set_slide_index(index, speaking=True)
            except Exception:
                pass
        if self.tts_toggle.isChecked():
            self.processing_sound.stop()
            self.set_state("SPEAKING")
            speech = self._news_slide_speech(self._news_slide_items[index], index, len(self._news_slide_items))
            self.voice_engine.speak(speech)
            self._news_slide_timer.start(120)
        else:
            # Sem TTS ainda há apresentação automática, com tempo proporcional ao texto.
            self.set_state("READY")
            self._news_slide_current_done = True
            self._news_slide_timer.start(6500)

    def _poll_news_slideshow(self):
        if not self._news_slide_items:
            self._news_slide_timer.stop()
            return
        if not self.tts_toggle.isChecked():
            if not self._news_slide_paused:
                self._advance_news_slide()
            return

        speaking = bool(self.voice_engine.is_speaking() or self.voice_engine.has_pending_speech())
        elapsed = time.perf_counter() - self._news_slide_wait_started
        if speaking:
            self._news_slide_voice_seen = True
            return

        # Pequena janela para a thread TTS retirar o texto da fila.
        if not self._news_slide_voice_seen and elapsed < 2.5:
            return

        # Se o backend TTS falhar silenciosamente, não trava o slide para sempre.
        if not self._news_slide_voice_seen and elapsed < 6.0:
            return

        if not self._news_slide_current_done:
            self._news_slide_current_done = True
            panel = getattr(self, "info_panel", None)
            if panel is not None:
                try:
                    panel.set_slide_index(self._news_slide_index, speaking=False)
                except Exception:
                    pass

        if self._news_slide_paused:
            self._news_slide_timer.stop()
            return

        self._news_slide_timer.stop()
        QTimer.singleShot(420, self._advance_news_slide)

    def _advance_news_slide(self):
        if not self._news_slide_items or self._news_slide_paused:
            return
        nxt = self._news_slide_index + 1
        if nxt >= len(self._news_slide_items):
            self._news_slide_timer.stop()
            panel = getattr(self, "info_panel", None)
            if panel is not None:
                try:
                    panel.set_slide_index(self._news_slide_index, speaking=False)
                except Exception:
                    pass
            self._news_slide_items = []
            self._news_slide_index = -1
            self._settle_state_after_audio()
            return
        self._speak_news_slide(nxt)

    @Slot(int)
    def _news_slide_manual_requested(self, index):
        # Navegar manualmente pausa a automação. Não cortamos uma fala no meio;
        # apenas impedimos a troca automática seguinte.
        self._news_slide_paused = True
        self._news_slide_index = int(index)
        self._news_slide_timer.stop()

    @Slot(bool)
    def _news_slide_pause_changed(self, paused):
        self._news_slide_paused = bool(paused)
        if self._news_slide_paused:
            return
        if not self._news_slide_items:
            return
        # Se a fala atual ainda está tocando, voltamos a observar. Se já acabou,
        # seguimos para a próxima manchete.
        if self.voice_engine.is_speaking():
            self._news_slide_timer.start(120)
        elif self._news_slide_current_done:
            QTimer.singleShot(180, self._advance_news_slide)
        else:
            self._news_slide_timer.start(120)

    def _cancel_news_slideshow(self):
        self._news_slide_timer.stop()
        self._news_slide_items = []
        self._news_slide_index = -1
        self._news_slide_paused = False
        self._news_slide_current_done = False

    def _maybe_show_internal_panel(self, results):
        """Abre a janela interna e retorna metadados da apresentação."""
        panel = getattr(self, "info_panel", None)
        if panel is None or not hasattr(panel, "show_content"):
            return None

        raw_items = []
        for result in (results or []):
            skill = str(getattr(result, "skill", "") or "").upper()
            message = str(getattr(result, "message", "") or "")
            data = getattr(result, "data", None) or {}
            raw_items.append({"tool": skill, "message": message, "data": data if isinstance(data, dict) else {}})
            nested = data.get("tool_results") if isinstance(data, dict) else None
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict):
                        raw_items.append({
                            "tool": str(item.get("tool", "") or "").upper(),
                            "message": str(item.get("message", "") or ""),
                            "data": item.get("data") if isinstance(item.get("data"), dict) else {},
                        })

        preferred = None
        for item in raw_items:
            tool = item["tool"]
            data = item.get("data", {}) or {}
            structured = data.get("items") if isinstance(data.get("items"), list) else []
            if tool.startswith("NEWS."):
                preferred = {"title":"V / NOTÍCIAS", "text":item["message"], "hint":"NEWS SLIDE MODE", "items":structured, "kind":"news"}
                break
            if tool.startswith("WEB.RESEARCH"):
                preferred = {"title":"V / PESQUISA", "text":item["message"], "hint":"RESEARCH PANEL", "items":structured, "kind":"research"}
                break
            if tool.startswith("MARKET."):
                preferred = {"title":"V / MERCADO", "text":item["message"], "hint":"MARKET PANEL", "items":structured, "kind":"market"}
                break
            if tool.startswith("SYSTEM.PC_STATUS"):
                preferred = {"title":"V / SISTEMA", "text":item["message"], "hint":"SYSTEM PANEL", "items":structured, "kind":"system"}

        if preferred:
            try:
                self._active_panel_kind = preferred.get("kind", "")
                panel.show_content(preferred["title"], preferred["text"], preferred["hint"], preferred["items"], kind=preferred.get("kind", ""))
                QTimer.singleShot(0, self._position_internal_panel)
                return preferred
            except Exception as exc:
                try:
                    self.last_action.setText(f"PANEL ERROR • {type(exc).__name__}: {exc}")
                except Exception:
                    pass
        return None

    @Slot(object)
    def _command_done(self, results):
        self._command_complete = True
        results = list(results or [])
        self._task_elapsed = max(0.0, time.perf_counter() - self._command_started_at) if self._command_started_at else 0.0
        self._task_stage = "Pedido concluído." if results and all(r.ok for r in results) else "Pedido encerrado com pendências. Confira o resultado."
        if results and (getattr(results[0], 'data', None) or {}).get('kind') == 'briefing_detail':
            self.processing_sound.stop()
            panel = getattr(self, '_briefing_panel', None)
            if panel is not None and not self._speech_suppressed:
                if panel.finish_details(results[0].data['generation'], results[0].message):
                    self.append_v(results[0].message)
            self._settle_state_after_audio()
            return
        self._initiative_completion(results)
        self.processing_sound.stop()
        presentation = self._maybe_show_internal_panel(results)
        spoken=[]
        if not results:
            self.append_v("O Core não gerou nenhuma ação para esse comando.")
        for result in results:
            msg = result.message or ("Ação concluída." if result.ok else "A ação falhou sem mensagem de diagnóstico.")
            self.append_v(msg)
            data = getattr(result, "data", None) or {}
            if result.ok and isinstance(data, dict) and data.get('kind') == 'document' and data.get('path'):
                self.game_mode.quick_chat.set_document(data['path'])
            if not result.ok:
                from core.failure_help import explain
                self.orchestrator.last_failure = data if isinstance(data, dict) and data.get('kind') == 'failure_help' else explain((result.skill or '') + ' ' + msg)
            speech_text = str(data.get("speech_text", "") or "").strip() if isinstance(data, dict) else ""
            spoken.append(speech_text or msg)
            self.last_action.setText(f"{result.skill or 'CORE'} • {'OK' if result.ok else 'FALHOU'}\n{msg}")
        self._last_result_text = "\n\n".join(r.message or ("Ação concluída." if r.ok else "A ação falhou.") for r in results)
        self._last_response_spoken = " ".join(dict.fromkeys(spoken))
        try:
            if hasattr(self, "memory_status"):
                mem = getattr(self.orchestrator, "memory", None)
                count = mem.count() if mem is not None and hasattr(mem, "count") else len(mem.get_memories()) if mem is not None else 0
                self.memory_status.setText(f"MEMÓRIA LOCAL: {count} item(ns) • explícita e persistente")
        except Exception:
            pass
        streamed = any(bool((getattr(r, "data", None) or {}).get("streamed_speech")) for r in (results or []))
        news_slideshow_started = False
        for result in results:
            data = getattr(result, 'data', None) or {}
            if data.get('kind') == 'daily_briefing' and data.get('items') and not self._speech_suppressed:
                from .daily_briefing import BriefingPanel
                self._cancel_news_slideshow()
                if getattr(self, 'info_panel', None) is not None:
                    self.info_panel.hide()
                if not hasattr(self, '_briefing_panel'):
                    self._briefing_panel = BriefingPanel(self)
                self._briefing_panel.start(data['items'])
                news_slideshow_started = True
                break
        if presentation and presentation.get("kind") == "news" and presentation.get("items") and not streamed and not self._speech_suppressed:
            news_slideshow_started = self._start_news_slideshow(presentation.get("items"))
        if spoken and not self._speech_suppressed and self.tts_toggle.isChecked() and not streamed and not news_slideshow_started:
            self.set_state("SPEAKING")
            self.voice_engine.speak(self._last_response_spoken)
        try:
            total_ms=(time.perf_counter()-self._command_started_at)*1000.0 if self._command_started_at else 0.0
            first_ms=((self._first_stream_speech_at-self._command_started_at)*1000.0) if self._first_stream_speech_at and self._command_started_at else None
            brain_ms=None
            for r in results or []:
                d=getattr(r,"data",None) or {}
                if d.get("brain_latency") and isinstance(d.get("brain_latency"),dict):
                    brain_ms=d["brain_latency"].get("first_chunk_ms") or d["brain_latency"].get("total_ms")
                    break
                if d.get("brain_ms"):
                    brain_ms=d.get("brain_ms"); break
            pieces=[]
            if first_ms is not None: pieces.append(f"1ª fala {first_ms:.0f} ms")
            if brain_ms is not None: pieces.append(f"Gemini {float(brain_ms):.0f} ms")
            tr=self._active_input_meta.get("transcription_ms") if isinstance(self._active_input_meta,dict) else None
            if tr is not None: pieces.append(f"Whisper {float(tr):.0f} ms")
            pieces.append(f"Core {total_ms:.0f} ms")
            self.latency_status.setText("LATÊNCIA: " + " • ".join(pieces))
            logs=Path(__file__).resolve().parent.parent/'logs'; logs.mkdir(parents=True,exist_ok=True)
            (logs/'latency_last.json').write_text(json.dumps({"first_speech_ms":first_ms,"brain_ms":brain_ms,"command_total_ms":round(total_ms,1),"input":self._active_input_meta},ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception:
            pass

    @Slot(str)
    def _command_failed(self, error):
        from core.failure_help import explain
        self.orchestrator.last_failure = explain(error)
        error = self.orchestrator.last_failure['message'] + ' Abra O que aconteceu? para conferir.'
        self._command_complete = True
        self._task_stage = "Não consegui concluir o pedido. Confira o erro na conversa."
        self._task_elapsed = max(0.0, time.perf_counter() - self._command_started_at) if self._command_started_at else 0.0
        self._last_result_text = str(error)
        self._last_response_spoken = self._task_stage
        self._initiative_completion(failed=True)
        self._conversation.cancel()
        self.processing_sound.stop()
        self.append_v(f"Erro interno do Core: {error}"); self.last_action.setText(error); self.set_state("ERROR")
        if not self._speech_suppressed and self.tts_toggle.isChecked(): self.voice_engine.speak("Ocorreu um erro interno no Core.")

    @Slot()
    def _command_thread_finished(self):
        self.command_thread = None; self._command_worker = None
        if self.pending_commands:
            QTimer.singleShot(60, self._pump_commands)
        else:
            self._settle_state_after_audio()

    def _settle_state_after_audio(self):
        if self.command_thread is not None and self.command_thread.isRunning():
            return
        if self.pending_commands:
            return
        if self.voice_engine.is_speaking() or self.voice_engine.has_pending_speech():
            self.set_state("SPEAKING")
            self.voice_status.setText(getattr(self.voice_engine, "tts_status", "Preparando áudio"))
            QTimer.singleShot(180, self._settle_state_after_audio)
        else:
            self.set_state("READY")
            if not self.voice_enabled or self.voice_engine.last_tts_error:
                self.voice_status.setText(getattr(self.voice_engine, "tts_status", "Voz pronta"))
            self._report_tts_failure()
            if self._conversation.pending and self.voice_enabled and self.followup_toggle.isChecked():
                if self.voice_engine.voice_input_allowed():
                    self._conversation.open(time.monotonic())
                    self._refresh_followup()
                else:
                    QTimer.singleShot(180, self._settle_state_after_audio)

    def _startup_greeting(self):
        """Saudação curta e variável ao abrir o V.

        Mantém a presença de cavalheiro sem transformar "senhor" em bordão.
        A fala acontece depois que a janela já abriu para não atrasar o startup.
        """
        try:
            brain = getattr(self.orchestrator, "brain", None)
            personality = getattr(brain, "personality", {}) if brain is not None else {}
            if personality.get("startup_greeting_enabled", True) is False:
                return

            hour = datetime.datetime.now().hour
            if 5 <= hour < 12:
                period = "Bom dia"
            elif 12 <= hour < 18:
                period = "Boa tarde"
            else:
                period = "Boa noite"

            configured = personality.get("startup_greetings") or []
            if configured:
                choices = [str(x).replace("{period}", period) for x in configured if str(x).strip()]
            else:
                choices = [
                    "Olá, senhor. Sistemas online.",
                    f"{period}, senhor. Tudo em ordem.",
                    f"{period}, senhor. V está online.",
                    "Estamos online, senhor. Tudo pronto.",
                    f"{period}. Sistemas online e à disposição.",
                ]
            message = random.choice(choices) if choices else "Olá, senhor. Sistemas online."
            self.append_v(message)
            if self.tts_toggle.isChecked():
                self.set_state("SPEAKING")
                self.voice_engine.speak(message)
                QTimer.singleShot(180, self._settle_state_after_audio)
        except Exception:
            # A saudação nunca deve impedir a inicialização da interface.
            pass

    def _report_tts_failure(self):
        error = str(getattr(self.voice_engine, 'last_tts_error', '') or '')
        if error and error != getattr(self, '_last_reported_tts_error', ''):
            self.append_v('Não consegui reproduzir minha voz. ' + error)
        self._last_reported_tts_error = error

    def test_v_voice(self):
        self.processing_sound.stop()
        self.set_state("SPEAKING")
        self.voice_engine.speak("Boa tarde, senhor. Sistemas online. Tudo pronto.")
        QTimer.singleShot(180, self._settle_state_after_audio)

    def _change_xtts_voice(self, index):
        key = str(self.xtts_voice_combo.itemData(index) or "v_prime")
        try:
            from voice.preferences import save_xtts_voice
            save_xtts_voice(self.voice_engine, key)
            dialog = getattr(self, "_task_dialog", None)
            if dialog is not None and dialog.isVisible():
                dialog.xtts_voice.blockSignals(True)
                dialog.xtts_voice.setCurrentIndex(dialog.xtts_voice.findData(key))
                dialog.xtts_voice.blockSignals(False)
                dialog.load_sample_speed()
            self.voice_status.setText(f"AMOSTRA ATIVA • {self.xtts_voice_combo.currentText()} • salve e teste a voz")
        except Exception as exc:
            self.voice_status.setText("Não foi possível trocar a amostra: " + str(exc))

    def _toggle_processing_sound(self, enabled):
        self.processing_sound.set_enabled(bool(enabled))
        try:
            cfg_path = Path(__file__).resolve().parent.parent / "config" / "default.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg.setdefault("ui", {})["processing_sound_enabled"] = bool(enabled)
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def toggle_continuous_voice(self):
        if self.voice_enabled: self.stop_continuous_voice()
        else: self.start_continuous_voice()

    def start_continuous_voice(self):
        if self.voice_thread is not None and self.voice_thread.isRunning(): return
        device = self.mic_combo.currentData()
        try:
            mic = self.voice_engine.validate_input_device(device)
            self.voice_engine.invalidate_ambient(device)
            self.voice_status.setText(f"MIC OK • {mic.get('name','')} • preparando Whisper")
        except Exception as exc:
            # Se um dispositivo específico sumiu (USB/P2 reconectado), volta ao padrão.
            if device is not None:
                try:
                    device = None
                    mic = self.voice_engine.validate_input_device(None)
                    self.voice_engine.invalidate_ambient()
                    self.voice_status.setText(f"MIC RECUPERADO • usando padrão: {mic.get('name','')}")
                    self.mic_combo.setCurrentIndex(0)
                except Exception:
                    self.append_v(f"Não consegui abrir o microfone: {exc}")
                    self.voice_status.setText(f"MIC ERROR: {exc}")
                    return
            else:
                self.append_v(f"Não consegui abrir o microfone: {exc}")
                self.voice_status.setText(f"MIC ERROR: {exc}")
                return
        thread = QThread(self); worker = ContinuousVoiceWorker(self.voice_engine, device); worker.moveToThread(thread)
        thread.started.connect(worker.run); worker.heard.connect(self._continuous_heard); worker.status.connect(self._voice_status); worker.calibrated.connect(self._voice_calibrated)
        worker.failed.connect(self._continuous_failed); worker.stopped.connect(thread.quit); worker.stopped.connect(worker.deleteLater)
        thread.finished.connect(self._voice_thread_finished); thread.finished.connect(thread.deleteLater)
        self.voice_thread = thread; self._voice_worker = worker; self.voice_enabled = True
        self.voice_toggle.setText("DESATIVAR VOZ CONTÍNUA"); self.voice_status.setText("PREPARANDO VOZ — aguarde o Whisper e a calibração")
        self.mic_combo.setEnabled(False); thread.start()

    def stop_continuous_voice(self):
        self._voice_capture_busy = False
        self._conversation.cancel()
        self.voice_enabled = False
        if self._voice_worker is not None: self._voice_worker.request_stop()
        self.voice_toggle.setText("ATIVAR VOZ CONTÍNUA"); self.voice_status.setText("VOICE OFF"); self.mic_combo.setEnabled(True)

    @Slot(str, object)
    def _continuous_heard(self, text, meta):
        self._voice_capture_busy = False
        if not self.voice_enabled: return
        if (meta or {}).get('reason') in {'uncertain_speech', 'audio_overflow', 'cancelled', 'tts_overlap'}:
            self.voice_status.setText('Não entendi com segurança. Repita a frase, por favor.')
            return
        text = str(text or "").strip()
        if not text:
            return
        self.voice_status.setText(f"OUVI: {text}")
        wake = has_wake_word(text)
        started = (meta or {}).get("speech_started_at")
        followup = self.followup_toggle.isChecked() and self._conversation.accepts(float(started) if started is not None else time.monotonic())
        if wake or followup:
            command = strip_wake_word(text)
            if command.lower().strip(" .!?,") in {"encerrar conversa", "fim da conversa", "pode descansar"}:
                self._conversation.cancel()
                self._refresh_followup()
                self.voice_status.setText("Conversa encerrada. Diga V para chamar novamente.")
                return
            if command:
                self._conversation.cancel()
                self.enqueue_command(text, source="voice", input_meta=meta)
            elif wake and self.followup_toggle.isChecked():
                self._conversation.wait_for_reply()
                self._conversation.open(time.monotonic())
                self._refresh_followup()
        else:
            # Não polui o chat com TV, jogo ou conversa ambiente.
            self.voice_status.setText(f"IGNORADO (sem 'V'): {text}")

    @Slot(str)
    def _voice_status(self, status):
        self._voice_capture_busy = status in {"HEARING SPEECH", "TRANSCRIBING", "CALIBRATING", "LOADING WHISPER"}
        if not self.voice_enabled:
            return
        if status == 'REPEAT PLEASE':
            self._recognition_notice_until = time.monotonic() + 3
        elif status == 'LISTENING' and time.monotonic() < getattr(self, '_recognition_notice_until', 0):
            return
        elif status == 'HEARING SPEECH':
            self._recognition_notice_until = 0
        labels = {
            "LOADING WHISPER": "CARREGANDO WHISPER • na primeira vez pode demorar",
            "CALIBRATING": "CALIBRANDO AMBIENTE • fique em silêncio por ~1 segundo",
            "LISTENING": "VOICE ON • OUVINDO",
            "HEARING SPEECH": "VOICE ON • ENTENDENDO SUA FRASE",
            "TRANSCRIBING": "VOICE ON • TRANSCREVENDO",
            "RECONNECTING MIC": "VOICE ON • RECONECTANDO MICROFONE",
            "REPEAT PLEASE": "FALA INCOMPLETA OU INCERTA • repita a frase, por favor",
        }
        self.voice_status.setText(labels.get(status, f"VOICE ON • {status}"))

    @Slot(object)
    def _voice_calibrated(self, profile):
        if not self.voice_enabled:
            return
        noise = profile.get("noise_rms", 0)
        threshold = profile.get("start_threshold", 0)
        self._last_voice_error = ""
        self.voice_status.setText(f"VOICE ON • CALIBRADO • ruído {noise:.4f} • limiar {threshold:.4f}")
        QTimer.singleShot(900, lambda: self.voice_enabled and self.voice_status.setText("VOICE ON • OUVINDO"))

    @Slot(str)
    def _continuous_failed(self, error):
        self._last_voice_error = str(error)
        self.voice_status.setText(f"VOICE ERROR: {error}"); self.append_v(f"Voz contínua parou: {error}"); self.stop_continuous_voice()

    @Slot()
    def _voice_thread_finished(self):
        self._voice_capture_busy = False
        self.voice_thread = None; self._voice_worker = None
        if not self.voice_enabled: self.mic_combo.setEnabled(True)

    def start_mic_test(self):
        if self.mic_test_thread is not None and self.mic_test_thread.isRunning(): return
        if self.voice_enabled:
            self.append_v("Desative a voz contínua antes de testar o microfone."); return
        self.append_v("Teste de microfone: fale uma frase curta agora.")
        thread=QThread(self); worker=MicTestWorker(self.voice_engine, self.mic_combo.currentData()); worker.moveToThread(thread)
        thread.started.connect(worker.run); worker.finished.connect(self._mic_test_done); worker.failed.connect(self._mic_test_failed)
        worker.finished.connect(thread.quit); worker.failed.connect(thread.quit); worker.finished.connect(worker.deleteLater); worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater); self.mic_test_thread=thread; self._mic_test_worker=worker; thread.start()

    @Slot(str, object)
    def _mic_test_done(self, text, meta):
        self.append_v(f"MIC {'OK' if text else 'SEM TRANSCRIÇÃO'} — ouvi: {text or '(nada)'}\nDiagnóstico: {meta}"); self.mic_test_thread=None; self._mic_test_worker=None
    @Slot(str)
    def _mic_test_failed(self, error):
        self.append_v(f"MIC ERROR: {error}"); self.mic_test_thread=None; self._mic_test_worker=None

    def set_state(self, state):
        state = str(state or "READY").upper()
        self.neural.set_state(state)
        self.intent_label.setText(state)
        labels = {
            "READY": "● SYSTEM ONLINE",
            "LISTENING": "● OUVINDO",
            "PROCESSING": "● PROCESSANDO",
            "SPEAKING": "● FALANDO",
            "ERROR": "● ATENÇÃO",
        }
        self.state_label.setText(labels.get(state, f"● {state}"))
        if state == "PROCESSING":
            self.processing_sound.schedule()
        else:
            self.processing_sound.stop()

    def closeEvent(self, event):
        if hasattr(self, '_camera_panel'):
            self._camera_panel.shutdown()
        if hasattr(self, '_briefing_panel'):
            self._briefing_panel.cancel()
        self.game_mode.shutdown()
        if hasattr(self, "_task_dialog"):
            self._task_dialog.close()
        self._initiative_timer.stop()
        if hasattr(self, "_notice_tray"):
            self._notice_tray.hide()
        try: self._news_slide_timer.stop()
        except Exception: pass
        try: self.processing_sound.shutdown()
        except Exception: pass
        try:
            self.stop_continuous_voice()
            if not getattr(self, "_mode_switching", False):
                if hasattr(self.orchestrator, '_live_notifications'):
                    self.orchestrator._live_notifications.close()
                self.voice_engine.shutdown()
        except Exception:
            pass
        super().closeEvent(event)
