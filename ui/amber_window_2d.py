from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QFrame,QTextEdit,QLineEdit,QPushButton,QProgressBar,QComboBox,QCheckBox
from .main_window import MainWindow
from .amber_neural_2d import AmberNeural2DWidget
from .internal_panel import VInternalPanel

AMBER_STYLE=r"""
QWidget { background: transparent; color:#e8b85f; font-family:'Segoe UI'; font-size:9pt; }
QMainWindow { background-color:#02040a; }
QFrame#amberGlass { background-color:rgba(5,7,13,202); border:1px solid rgba(232,166,54,105); border-radius:10px; }
QLabel#tiny { color:#b48237; font-size:8px; font-weight:600; letter-spacing:1px; }
QLabel#strong { color:#f1bd58; font-size:9px; font-weight:700; letter-spacing:2px; }
QLabel#online { color:#ffc95d; font-size:8px; font-weight:700; letter-spacing:1px; }
QTextEdit { background-color:rgba(3,5,10,190); border:0; color:#e9c781; padding:7px; }
QLineEdit { background-color:rgba(5,7,13,220); border:1px solid rgba(227,160,44,125); border-radius:18px; padding:9px 14px; color:#ffe0a1; }
QPushButton { background-color:rgba(35,24,9,220); border:1px solid rgba(239,173,54,135); border-radius:15px; padding:7px 11px; color:#ffd078; font-weight:600; }
QPushButton:hover { background-color:rgba(57,37,10,235); border-color:#ffd16a; }
QProgressBar { background-color:rgba(12,9,5,190); border:1px solid rgba(151,100,28,90); border-radius:3px; min-height:5px; max-height:5px; color:transparent; }
QProgressBar::chunk { background-color:#e9a72f; border-radius:2px; }
QComboBox { background-color:#090b10; border:1px solid #5e421b; border-radius:5px; padding:4px; color:#e9bd70; }
QCheckBox { color:#af8b4b; font-size:8px; }
"""

def glass():
    f=QFrame(); f.setObjectName('amberGlass'); return f

class Amber2DTestWindow(MainWindow):
    def __init__(self, orchestrator, registry, voice_engine, startup_greeting=True):
        super().__init__(orchestrator, registry, voice_engine, startup_greeting=startup_greeting)
        self.setWindowTitle('V 1.9.1 // FACE LAB // MODE 1 — 2D')
        self.setStyleSheet(AMBER_STYLE)

    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root)
        stack=QGridLayout(root); stack.setContentsMargins(0,0,0,0); stack.setSpacing(0)
        self.neural=AmberNeural2DWidget(); stack.addWidget(self.neural,0,0)

        overlay=QWidget(); overlay.setAttribute(Qt.WA_TranslucentBackground)
        ov=QVBoxLayout(overlay); ov.setContentsMargins(20,14,20,16); ov.setSpacing(9); stack.addWidget(overlay,0,0)

        self.info_panel=VInternalPanel(accent='#f1bd58', border='rgba(232, 166, 54, 160)', parent=root)

        top=QHBoxLayout();
        logo=QLabel('V / FACE LAB / MODE 1 — 2D'); logo.setObjectName('strong')
        self.intent_label=QLabel('READY'); self.intent_label.setObjectName('tiny')
        self.state_label=QLabel('● SYSTEM ONLINE'); self.state_label.setObjectName('online')
        self.clock=QLabel(''); self.clock.setObjectName('tiny')
        top.addWidget(logo); top.addWidget(self.intent_label); top.addStretch(1); top.addWidget(self.state_label); top.addSpacing(8); top.addWidget(self.clock)
        ov.addLayout(top)

        mid=QHBoxLayout(); mid.addStretch(1)
        status=glass(); status.setFixedWidth(195); status.setMaximumHeight(160)
        sl=QVBoxLayout(status); sl.setContentsMargins(10,9,10,9); sl.setSpacing(6)
        st=QLabel('SYSTEM'); st.setObjectName('strong'); sl.addWidget(st)
        self.cpu=QProgressBar(); self.cpu.setTextVisible(False); sl.addWidget(self.cpu)
        self.ram=QProgressBar(); self.ram.setTextVisible(False); sl.addWidget(self.ram)
        self.ai_status=QLabel('AI ONLINE'); self.ai_status.setObjectName('tiny'); sl.addWidget(self.ai_status)
        self.spotify_api_status=QLabel('SPOTIFY ...'); self.spotify_api_status.setObjectName('tiny'); sl.addWidget(self.spotify_api_status)
        self.spotify_bridge_status=QLabel('BRIDGE READY'); self.spotify_bridge_status.setObjectName('tiny'); sl.addWidget(self.spotify_bridge_status)
        self.memory_status=QLabel('MEMORY LOCAL'); self.memory_status.setObjectName('tiny'); sl.addWidget(self.memory_status)
        self.latency_status=QLabel('LATENCY --'); self.latency_status.setObjectName('tiny'); sl.addWidget(self.latency_status)
        mid.addWidget(status,0,Qt.AlignTop)
        ov.addLayout(mid,1)

        bottom=QHBoxLayout(); bottom.setSpacing(12)
        monitor=glass(); monitor.setFixedSize(350,205)
        ml=QVBoxLayout(monitor); ml.setContentsMargins(10,8,10,8); ml.setSpacing(5)
        mh=QHBoxLayout(); lab=QLabel('COMMAND'); lab.setObjectName('strong'); self.last_action=QLabel('IDLE'); self.last_action.setObjectName('online'); mh.addWidget(lab); mh.addStretch(1); mh.addWidget(self.last_action); ml.addLayout(mh)
        self.chat=QTextEdit(); self.chat.setReadOnly(True); ml.addWidget(self.chat,1)
        bottom.addWidget(monitor,0,Qt.AlignBottom)

        center=QVBoxLayout(); center.addStretch(1)
        row=QHBoxLayout(); self.input=QLineEdit(); self.input.setPlaceholderText('Fale com o V ou digite...'); self.input.setMinimumWidth(390); self.input.returnPressed.connect(self.submit_text)
        self.send_btn=QPushButton('SEND'); self.send_btn.clicked.connect(self.submit_text); row.addWidget(self.input,1); row.addWidget(self.send_btn); center.addLayout(row)
        mode=QPushButton('ALTERNAR PARA MODO ORBITAL  [F6]'); mode.clicked.connect(self.request_mode_switch); center.addWidget(mode)
        bottom.addLayout(center,1)

        controls=glass(); controls.setFixedSize(190,205)
        cr=QVBoxLayout(controls); cr.setContentsMargins(10,8,10,8); cr.setSpacing(5)
        ct=QLabel('VOICE LINK'); ct.setObjectName('strong'); cr.addWidget(ct)
        self.mic_combo=QComboBox(); cr.addWidget(self.mic_combo)
        self.voice_toggle=QPushButton('MIC / VOICE ON'); self.voice_toggle.clicked.connect(self.toggle_continuous_voice); cr.addWidget(self.voice_toggle)
        self.voice_status=QLabel('VOICE OFF'); self.voice_status.setWordWrap(True); self.voice_status.setObjectName('tiny'); cr.addWidget(self.voice_status)
        sample_label=QLabel('VOICE'); sample_label.setObjectName('tiny'); cr.addWidget(sample_label)
        self.xtts_voice_combo=QComboBox(); self.xtts_voice_combo.addItem('V Prime · atual','v_prime'); self.xtts_voice_combo.addItem('V Alt · nova amostra','v_alt')
        from voice.preferences import setup_voice_selector
        setup_voice_selector(self.xtts_voice_combo, self.voice_engine.config)
        self.xtts_voice_combo.currentIndexChanged.connect(self._change_xtts_voice); cr.addWidget(self.xtts_voice_combo)
        rr=QHBoxLayout(); self.test_mic=QPushButton('MIC'); self.test_mic.clicked.connect(self.start_mic_test); self.test_voice=QPushButton('VOICE'); self.test_voice.clicked.connect(self.test_v_voice); rr.addWidget(self.test_mic); rr.addWidget(self.test_voice); cr.addLayout(rr)
        self.tts_toggle=QCheckBox('VOICE RESPONSE'); self.tts_toggle.setChecked(True); cr.addWidget(self.tts_toggle)
        self.process_sound_toggle=QCheckBox('PROCESS FX'); self.process_sound_toggle.setChecked(self.processing_sound.enabled); self.process_sound_toggle.toggled.connect(self._toggle_processing_sound); cr.addWidget(self.process_sound_toggle)
        self.process_sound_status=QLabel(f'FX {self.processing_sound.backend.upper()}'); self.process_sound_status.setObjectName('tiny'); cr.addWidget(self.process_sound_status)
        cr.addStretch(1); bottom.addWidget(controls,0,Qt.AlignBottom)
        ov.addLayout(bottom)

    def append_user(self,text):
        self.chat.append(f"<div style='color:#a67c38'><b>YOU //</b> {self._esc(text)}</div>")
        self.chat.ensureCursorVisible()
    def append_v(self,text):
        self.chat.append(f"<div style='color:#f0c879'><b>V //</b> {self._esc(text)}</div>")
        self.chat.ensureCursorVisible()
