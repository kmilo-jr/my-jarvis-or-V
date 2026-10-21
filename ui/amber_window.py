from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTextEdit,
    QLineEdit, QPushButton, QProgressBar, QComboBox, QCheckBox, QSizePolicy
)
from .main_window import MainWindow
from .futuristic_face import FuturisticFaceWidget
from .internal_panel import VInternalPanel

FUTURE_STYLE = """
QWidget { background: transparent; color: #e5e8eb; font-family: 'Segoe UI'; font-size: 10pt; }
QMainWindow, QWidget#futureRoot { background: #090e14; }
QToolBar { background: #0e151e; border: 0; border-bottom: 1px solid #29313a; spacing: 12px; padding: 5px 16px; }
QToolButton { color: #b2bbc4; border: 0; padding: 5px; font-size: 9pt; }
QToolButton:hover { color: #ffab95; background: #212630; }
QFrame#sidePanel { background: #101720; border: 1px solid #28323c; border-radius: 12px; }
QFrame#commandDock { background: #111a23; border: 1px solid #303b44; border-radius: 12px; }
QLabel#eyebrow { color: #b1bbc4; font-size: 9px; font-weight: 600; letter-spacing: 2px; }
QLabel#brand { color: #ffe3d3; font-size: 31px; font-weight: 600; letter-spacing: 5px; }
QLabel#heading { color: #f2d6c8; font-size: 16px; font-weight: 600; }
QLabel#muted { color: #96a3af; font-size: 11px; }
QLabel#live { color: #f49b86; font-size: 11px; }
QLabel#heroState { font-size: 21px; font-weight: 400; color: #f7dfd3; }
QTextEdit { background: transparent; border: 0; color: #dce4eb; font-size: 12px; padding: 0; }
QLineEdit { background: transparent; border: 0; color: #f2ece7; padding: 12px 5px; font-size: 14px; }
QPushButton { background: #19232d; color: #dce4eb; border: 1px solid #34414e; border-radius: 7px; padding: 8px 10px; font-size: 11px; }
QPushButton:hover { background: #29323c; border-color: #bd7d6f; color: white; }
QPushButton:pressed { background: #3b3030; }
QPushButton#primary { background: #e8967e; border: 1px solid #ffb89c; color: #161113; font-weight: 700; padding: 10px 20px; }
QPushButton#primary:hover { background: #ffc0a3; }
QComboBox { background: #0c131b; border: 1px solid #34414e; border-radius: 6px; padding: 7px; font-size: 11px; }
QComboBox QAbstractItemView { background: #15212b; color: #e4eaf0; selection-background-color: #59433c; }
QCheckBox { color: #acb9c4; spacing: 7px; font-size: 11px; }
QCheckBox::indicator { width: 13px; height: 13px; }
QProgressBar { background: #28323c; border: 0; border-radius: 2px; min-height: 4px; max-height: 4px; }
QProgressBar::chunk { background: #cb8876; border-radius: 2px; }
QScrollBar:vertical { background: transparent; width: 6px; }
QScrollBar::handle:vertical { background: #42505e; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def label(text, role='muted'):
    widget = QLabel(text)
    widget.setObjectName(role)
    return widget


def card(name='sidePanel'):
    widget = QFrame()
    widget.setObjectName(name)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    return widget, layout


class AmberExperimentWindow(MainWindow):
    """Second interface: a live vector face with conversation and voice controls."""
    def __init__(self, orchestrator, registry, voice_engine, startup_greeting=True):
        super().__init__(orchestrator, registry, voice_engine, startup_greeting=startup_greeting)
        self.setWindowTitle('V / Presença digital')
        self.setStyleSheet(FUTURE_STYLE)
        # Recompute layout hints after replacing the shared window stylesheet.
        self.ensurePolished()
        for widget in reversed(self.findChildren(QWidget)):
            if widget.layout() is not None:
                widget.layout().invalidate()
            widget.updateGeometry()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('futureRoot')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 18, 28, 22)
        outer.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(20)
        header.addWidget(label('V', 'brand'))
        title = QVBoxLayout()
        title.setSpacing(2)
        title.addWidget(label('PRESENÇA DIGITAL', 'eyebrow'))
        title.addWidget(label('Seu assistente. Sempre por perto.'))
        header.addLayout(title)
        header.addStretch()
        self.state_label = label('● PRONTO', 'live')
        self.clock = label('')
        header.addWidget(self.state_label)
        header.addSpacing(12)
        header.addWidget(self.clock)
        mode = QPushButton('Orbital  /  F6')
        mode.clicked.connect(self.request_mode_switch)
        header.addWidget(mode)
        outer.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(24)
        stage = QVBoxLayout()
        stage.setSpacing(4)
        self.neural = FuturisticFaceWidget(voice_engine=self.voice_engine)
        stage.addWidget(self.neural, 1)
        self.intent_label = label('Pronto para ajudar.', 'heroState')
        self.intent_label.setAlignment(Qt.AlignCenter)
        stage.addWidget(self.intent_label)
        self.presence_hint = label('Ative o microfone ou escreva um pedido abaixo.')
        self.presence_hint.setAlignment(Qt.AlignCenter)
        stage.addWidget(self.presence_hint)
        stage.addSpacing(18)
        dock, dock_layout = card('commandDock')
        dock_layout.setContentsMargins(14, 6, 8, 6)
        row = QHBoxLayout()
        row.addWidget(label('›', 'heading'))
        self.input = QLineEdit()
        self.input.setPlaceholderText('O que vamos fazer agora?')
        self.input.returnPressed.connect(self.submit_text)
        row.addWidget(self.input, 1)
        self.send_btn = QPushButton('Enviar')
        self.send_btn.setObjectName('primary')
        self.send_btn.clicked.connect(self.submit_text)
        row.addWidget(self.send_btn)
        dock_layout.addLayout(row)
        stage.addWidget(dock)
        content.addLayout(stage, 1)

        side = QWidget()
        side.setFixedWidth(318)
        sidebar = QVBoxLayout(side)
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(12)
        conversation, cl = card()
        top = QHBoxLayout()
        top.addWidget(label('Conversa', 'heading'))
        top.addStretch()
        top.addWidget(label('VOCÊ + V', 'eyebrow'))
        cl.addLayout(top)
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setMinimumHeight(60)
        cl.addWidget(self.chat, 1)
        self.last_action = label('Aguardando seu próximo pedido.')
        self.last_action.setWordWrap(False)
        self.last_action.setMaximumHeight(36)
        self.last_action.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        cl.addWidget(self.last_action)
        sidebar.addWidget(conversation, 1)

        voice, vl = card()
        voice.setFixedHeight(260)
        vl.addWidget(label('Voz e escuta', 'heading'))
        self.mic_combo = QComboBox()
        self.mic_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mic_combo.setMinimumContentsLength(16)
        vl.addWidget(self.mic_combo)
        self.voice_toggle = QPushButton('ATIVAR VOZ CONTÍNUA')
        self.voice_toggle.clicked.connect(self.toggle_continuous_voice)
        vl.addWidget(self.voice_toggle)
        self.voice_status = label('Microfone em espera.')
        self.voice_status.setWordWrap(False)
        self.voice_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.voice_status.setMaximumHeight(36)
        vl.addWidget(self.voice_status)
        vl.addWidget(label('Voz de resposta', 'eyebrow'))
        self.xtts_voice_combo = QComboBox()
        self.xtts_voice_combo.addItem('V Prime · atual', 'v_prime')
        self.xtts_voice_combo.addItem('V Alt · nova amostra', 'v_alt')
        from voice.preferences import setup_voice_selector
        setup_voice_selector(self.xtts_voice_combo, self.voice_engine.config)
        self.xtts_voice_combo.currentIndexChanged.connect(self._change_xtts_voice)
        vl.addWidget(self.xtts_voice_combo)
        tests = QHBoxLayout()
        self.test_mic = QPushButton('Testar microfone')
        self.test_mic.clicked.connect(self.start_mic_test)
        self.test_voice = QPushButton('Ouvir o V')
        self.test_voice.clicked.connect(self.test_v_voice)
        tests.addWidget(self.test_mic)
        tests.addWidget(self.test_voice)
        vl.addLayout(tests)
        self.tts_toggle = QCheckBox('Respostas em voz alta')
        self.tts_toggle.setChecked(True)
        vl.addWidget(self.tts_toggle)
        self.process_sound_toggle = QCheckBox('Som durante o processamento')
        self.process_sound_toggle.setChecked(self.processing_sound.enabled)
        self.process_sound_toggle.toggled.connect(self._toggle_processing_sound)
        vl.addWidget(self.process_sound_toggle)
        sidebar.addWidget(voice)

        system, sl = card()
        system.setMinimumHeight(89)
        system_row = QHBoxLayout()
        system_row.addWidget(label('ESTE COMPUTADOR', 'eyebrow'))
        system_row.addStretch()
        diagnostic = QPushButton('Diagnóstico ↗')
        diagnostic.clicked.connect(self.show_diagnostics)
        system_row.addWidget(diagnostic)
        sl.addLayout(system_row)
        metrics = QHBoxLayout()
        self.cpu = QProgressBar()
        self.ram = QProgressBar()
        for name, bar in (('CPU', self.cpu), ('RAM', self.ram)):
            bar.setTextVisible(False)
            metrics.addWidget(label(name, 'eyebrow'))
            metrics.addWidget(bar, 1)
        sl.addLayout(metrics)
        sidebar.addWidget(system)
        content.addWidget(side)
        outer.addLayout(content, 1)

        # Compatibility with the shared command, latency and diagnostics handlers.
        hidden = QWidget(root)
        hidden.hide()
        for name in ('ai_status', 'spotify_api_status', 'spotify_bridge_status',
                     'memory_status', 'latency_status', 'process_sound_status'):
            setattr(self, name, QLabel('', hidden))
        self.info_panel = VInternalPanel(accent='#eea18c', border='rgba(238,161,140,110)', parent=root)

    def set_state(self, state):
        state = str(state or 'READY').upper()
        if state == 'READY' and self.voice_enabled:
            state = 'LISTENING'
        super().set_state(state)
        titles = {'READY': 'Pronto para ajudar.', 'LISTENING': 'Estou ouvindo.',
                  'PROCESSING': 'Um instante. Estou pensando.', 'SPEAKING': 'Vamos conversar.',
                  'ERROR': 'Vamos verificar isso.'}
        self.intent_label.setText(titles.get(state, state))
        if state == 'READY':
            self.state_label.setText('● PRONTO')
        self.presence_hint.setText({'SPEAKING': 'Esc para interromper a fala.',
                                    'LISTENING': 'Diga “V” e faça seu pedido.',
                                    'PROCESSING': 'Acompanhe o andamento na conversa.',
                                    'ERROR': 'Abra o diagnóstico para conferir as conexões.'}.get(
                                        state, 'Ative o microfone ou escreva um pedido abaixo.'))

    def _voice_status(self, status):
        super()._voice_status(status)
        busy = self.command_thread is not None and self.command_thread.isRunning()
        if self.voice_enabled and not busy and not self.voice_engine.is_speaking():
            if status in ('LISTENING', 'HEARING SPEECH'):
                self.set_state('LISTENING')
            elif status == 'TRANSCRIBING':
                self.intent_label.setText('Entendendo seu pedido.')

    def stop_continuous_voice(self):
        super().stop_continuous_voice()
        busy = self.command_thread is not None and self.command_thread.isRunning()
        if not busy and not self.voice_engine.is_speaking():
            self.set_state('READY')

    def _update_system(self):
        super()._update_system()
        self.cpu.setToolTip(f'CPU: {self.cpu.value()}%')
        self.ram.setToolTip(f'RAM: {self.ram.value()}%')
        self.last_action.setToolTip(self.last_action.text())
        self.voice_status.setToolTip(self.voice_status.text())

    def append_user(self, text):
        self.chat.append(f"<p style='color:#b2bec9; margin-top:12px'><b>VOCÊ</b><br>{self._esc(text)}</p>")
        self.chat.ensureCursorVisible()

    def append_v(self, text):
        if str(text).startswith('V Prototype 1.8.3 //'):
            text = 'Interface pronta. Fale comigo ou envie um pedido.'
        self.chat.append(f"<p style='color:#efd7cc; margin-top:12px'><b>V</b><br>{self._esc(text)}</p>")
        self.chat.ensureCursorVisible()
        game = getattr(self, 'game_mode', None)
        if game is not None:
            game.quick_chat.set_reply(str(text))
