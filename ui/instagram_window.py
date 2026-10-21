from __future__ import annotations
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QTextEdit,
    QLineEdit, QPushButton, QProgressBar, QComboBox, QCheckBox, QSizePolicy, QDialog, QTabWidget, QTextBrowser
)
from .main_window import MainWindow
from .briefing_scene import BriefingBackdrop, TopicThumbnail
from .internal_panel import VInternalPanel


EXPERIMENT_STYLE = r"""
QWidget { background: transparent; color: #bfe7ff; font-family: 'Segoe UI'; font-size: 9pt; }
QMainWindow { background-color: #020611; }
QFrame#glass { background-color: rgba(3, 11, 25, 198); border: 1px solid rgba(40, 137, 204, 125); border-radius: 8px; }
QFrame#microPanel { background-color: rgba(2, 9, 21, 182); border: 1px solid rgba(32, 122, 185, 102); border-radius: 7px; }
QFrame#orbitalSide { background-color: rgba(3, 13, 30, 210); border: 1px solid rgba(44, 118, 170, 145); border-radius: 9px; }
QLabel#sideEyebrow { color: #5ea8c9; font-size: 9px; font-weight: 700; letter-spacing: 1.4px; }
QLabel#sideTitle { color: #d8f4ff; font-size: 15px; font-weight: 650; }
QLabel#sideBody { color: #8fbcd3; font-size: 11px; }
QLabel#tiny { color: #8fbcd3; font-size: 11px; }
QLabel#tinyStrong { color: #a3eaff; font-size: 12px; font-weight: 600; letter-spacing: 1px; }
QLabel#online { color: #76dfcb; font-size: 11px; font-weight: 600; }
QToolBar { background: #07111e; border: 0; border-bottom: 1px solid #19374a; spacing: 12px; padding: 5px 12px; }
QToolButton { color: #b2d0e1; padding: 5px 8px; border-radius: 5px; }
QToolButton:hover { background: #123249; }
QTextEdit { background-color: rgba(1, 7, 17, 185); border: 0px; color: #bfe8ff; padding: 5px; }
QLineEdit { background-color: rgba(2, 11, 26, 218); border: 1px solid rgba(43, 142, 204, 150); border-radius: 17px; padding: 9px 14px; color: #d7f5ff; }
QPushButton { background-color: rgba(4, 31, 58, 210); border: 1px solid rgba(51, 166, 224, 145); border-radius: 15px; padding: 7px 12px; color: #9feaff; font-weight: 600; }
QPushButton:hover { background-color: rgba(6, 47, 81, 230); border-color: #4be2ff; }
QPushButton:pressed { background-color: rgba(4, 22, 38, 230); }
QProgressBar { background-color: rgba(2, 12, 26, 185); border: 1px solid rgba(30, 107, 163, 95); border-radius: 3px; min-height: 5px; max-height: 5px; text-align: center; color: transparent; }
QProgressBar::chunk { background-color: #35c8ff; border-radius: 2px; }
QComboBox { background-color: #061220; border: 1px solid #174b6b; border-radius: 5px; padding: 4px; }
QComboBox QAbstractItemView { background: #081827; color: #d7f5ff; selection-background-color: #174b6b; }
QCheckBox { color: #a5c6d8; font-size: 11px; spacing: 7px; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border-color: #8ceaff; }
QPushButton#sendPrimary { background: #65d8ed; color: #052332; border: 1px solid #a7f0ff; }
QPushButton#sendPrimary:hover { background: #a7f0ff; }
QScrollBar:vertical { background: transparent; width: 6px; }
QScrollBar::handle:vertical { background: #315369; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

RED_EXPERIMENT_STYLE = r"""
QWidget { background: transparent; color: #ffe4e7; font-family: 'Segoe UI'; font-size: 9pt; }
QMainWindow { background-color: #13040a; }
QFrame#glass { background-color: rgba(35, 4, 12, 220); border: 1px solid rgba(207, 42, 65, 170); border-radius: 8px; }
QFrame#microPanel { background-color: rgba(25, 3, 9, 205); border: 1px solid rgba(177, 35, 57, 135); border-radius: 7px; }
QFrame#orbitalSide { background-color: rgba(35, 4, 13, 218); border: 1px solid rgba(190, 42, 66, 165); border-radius: 9px; }
QLabel#sideEyebrow { color: #e85c70; font-size: 9px; font-weight: 700; letter-spacing: 1.4px; }
QLabel#sideTitle { color: #ffe3e7; font-size: 15px; font-weight: 650; }
QLabel#sideBody { color: #d39aa3; font-size: 11px; }
QLabel#tiny { color: #d7a0a8; font-size: 11px; }
QLabel#tinyStrong { color: #ff8e98; font-size: 12px; font-weight: 600; letter-spacing: 1px; }
QLabel#online { color: #ff9ca5; font-size: 11px; font-weight: 600; }
QToolBar { background: #1d050d; border: 0; border-bottom: 1px solid #5b1726; spacing: 12px; padding: 5px 12px; }
QToolButton { color: #e3b2b9; padding: 5px 8px; border-radius: 5px; }
QToolButton:hover { background: #4a0c1b; }
QTextEdit { background-color: rgba(12, 2, 6, 205); border: 0px; color: #ffe2e5; padding: 5px; }
QLineEdit { background-color: rgba(28, 3, 10, 232); border: 1px solid rgba(199, 47, 68, 180); border-radius: 17px; padding: 9px 14px; color: #fff0f1; }
QPushButton { background-color: rgba(67, 8, 22, 225); border: 1px solid rgba(230, 70, 88, 175); border-radius: 15px; padding: 7px 12px; color: #ffd7db; font-weight: 600; }
QPushButton:hover { background-color: rgba(104, 13, 33, 240); border-color: #ff7c86; }
QPushButton:pressed { background-color: rgba(45, 4, 14, 240); }
QProgressBar { background-color: rgba(30, 4, 12, 205); border: 1px solid rgba(154, 32, 51, 120); border-radius: 3px; min-height: 5px; max-height: 5px; text-align: center; color: transparent; }
QProgressBar::chunk { background-color: #ef4057; border-radius: 2px; }
QComboBox { background-color: #21050d; border: 1px solid #6b1c2c; border-radius: 5px; padding: 4px; }
QComboBox QAbstractItemView { background: #26060f; color: #ffe6e8; selection-background-color: #6b1c2c; }
QCheckBox { color: #ddb1b7; font-size: 11px; spacing: 7px; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border-color: #ff9da5; }
QPushButton#sendPrimary { background: #f05b6c; color: #28030a; border: 1px solid #ffb1b8; }
QPushButton#sendPrimary:hover { background: #ff9da5; }
QScrollBar:vertical { background: transparent; width: 6px; }
QScrollBar::handle:vertical { background: #8b2e40; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def glass(name="glass"):
    f = QFrame(); f.setObjectName(name); return f


class InstagramExperimentWindow(MainWindow):
    """Orbital shell using the same visual language as the daily briefing."""

    def __init__(self, orchestrator, registry, voice_engine, startup_greeting=True, theme='blue'):
        self.visual_theme = str(theme or 'blue').lower()
        if self.visual_theme not in {'blue', 'red'}:
            self.visual_theme = 'blue'
        super().__init__(orchestrator, registry, voice_engine, startup_greeting=startup_greeting)
        self.setWindowTitle("V / Orbital")
        base_style = RED_EXPERIMENT_STYLE if self.visual_theme == 'red' else EXPERIMENT_STYLE
        if self.visual_theme == 'red':
            extra_style = """
                QFrame#orbitalCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(69,7,21,250),stop:1 rgba(28,3,10,248)); border:1px solid #c9324d; border-radius:7px; }
                QTextBrowser { background:transparent; border:0; color:#ffe5e8; font-size:15px; }
                QDialog { background:#1a040b; }
                QTabWidget::pane { border:1px solid #762136; }
                QTabBar::tab { background:#360914; padding:10px; color:#ffd9dd; }
                QTabBar::tab:selected { background:#6e1b2d; }
            """
        else:
            extra_style = """
                QFrame#orbitalCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(3,23,51,248),stop:1 rgba(2,17,49,246)); border:1px solid #278dde; border-radius:7px; }
                QTextBrowser { background:transparent; border:0; color:#d6eeff; font-size:15px; }
                QDialog { background:#06142b; }
                QTabWidget::pane { border:1px solid #245579; }
                QTabBar::tab { background:#092442; padding:10px; color:#bfe7ff; }
                QTabBar::tab:selected { background:#174572; }
            """
        self.setStyleSheet(base_style + extra_style)
        self.session_toolbar.hide()
        self.set_state('READY')
        if self.visual_theme == 'red': self.statusBar().hide()
        if self.visual_theme == 'red':
            from .desktop_shell import DesktopShell
            stage = self.takeCentralWidget()
            self.reference_stage = stage
            self.desktop_shell = DesktopShell(self, stage)
            self.setCentralWidget(self.desktop_shell)
            self.reference_menu.hide()
            QTimer.singleShot(0, self._position_reference)

    def _build_ui(self):
        if self.visual_theme == 'red':
            self._build_reference_ui()
            return
        self._reply_cards = []
        self._reply_buttons = []
        self._current_reply = ''
        root = QWidget(); self.setCentralWidget(root)
        stack = QGridLayout(root); stack.setContentsMargins(0,0,0,0)
        self.neural = BriefingBackdrop(root, theme=self.visual_theme)
        stack.addWidget(self.neural, 0, 0)
        overlay = QWidget(); overlay.setAttribute(Qt.WA_TranslucentBackground)
        stack.addWidget(overlay, 0, 0)
        outer = QVBoxLayout(overlay); outer.setContentsMargins(24,16,24,58); outer.setSpacing(12)
        top = QHBoxLayout()
        logo = QLabel('V  /  ORBITAL'); logo.setObjectName('tinyStrong'); top.addWidget(logo)
        self.state_label = QLabel('● PRONTO'); self.state_label.setObjectName('tiny'); top.addWidget(self.state_label)
        top.addStretch()
        self.clock = QLabel(); self.clock.setObjectName('tiny'); top.addWidget(self.clock)
        camera = QPushButton('Câmera'); camera.clicked.connect(self.show_camera); top.addWidget(camera)
        tools = QPushButton('Ferramentas'); tools.clicked.connect(self._toggle_tools); top.addWidget(tools)
        controls = QPushButton('Controles'); controls.clicked.connect(self._show_controls); top.addWidget(controls)
        outer.addLayout(top)
        content = QHBoxLayout(); content.setSpacing(14); content.setContentsMargins(0, 2, 0, 0)
        left = QVBoxLayout(); left.setSpacing(10); left.setContentsMargins(0, 0, 0, 0); left.setAlignment(Qt.AlignTop)
        self.left_panorama = self._side_card('PANORAMA DO DIA', 'SEM DESVIOS', 'Clima, agenda, e-mails e notícias aparecem no briefing.')
        self.left_readiness = self._side_card('PRONTIDÃO', 'ONLINE', 'O núcleo visual acompanha o estado atual do V.')
        self.left_activity = self._side_card('ATIVIDADE', 'AGUARDANDO', 'O histórico recente fica na faixa de cartões abaixo.')
        for card in (self.left_panorama, self.left_readiness, self.left_activity): left.addWidget(card)
        content.addLayout(left, 0)

        center = QVBoxLayout(); center.setSpacing(8); center.setContentsMargins(0, 0, 0, 0)
        self.intent_label = QLabel('PRONTO PARA AJUDAR'); self.intent_label.setAlignment(Qt.AlignCenter)
        intent_color = '#ff6875' if self.visual_theme == 'red' else '#4bd4ff'
        response_color = '#fff0f1' if self.visual_theme == 'red' else '#d9f6ff'
        self.intent_label.setStyleSheet(f'color:{intent_color}; letter-spacing:4px; font-size:12px;')
        center.addWidget(self.intent_label)
        self.response_card = QFrame(); self.response_card.setObjectName('orbitalCard')
        self.response_card.setMinimumSize(560, 272); self.response_card.setMaximumHeight(300)
        card_layout = QVBoxLayout(self.response_card); card_layout.setContentsMargins(18,14,18,14)
        self.response_title = QLabel('Como posso ajudar?'); self.response_title.setTextFormat(Qt.PlainText)
        self.response_title.setStyleSheet(f'font-size:19px; font-weight:600; color:{response_color};')
        card_layout.addWidget(self.response_title)
        self.response = QTextBrowser(); self.response.setOpenExternalLinks(False); card_layout.addWidget(self.response, 1)
        self.last_action = QLabel('Aguardando seu pedido.'); self.last_action.setObjectName('tiny')
        self.last_action.setWordWrap(True); self.last_action.setMaximumHeight(32)
        card_layout.addWidget(self.last_action)
        center.addWidget(self.response_card, 0, Qt.AlignHCenter)
        rail_label = QLabel('CARTÕES // HISTÓRICO RECENTE'); rail_label.setObjectName('sideEyebrow')
        rail_label.setAlignment(Qt.AlignCenter); center.addWidget(rail_label)
        self.reply_trail = QWidget(); self.reply_trail.setFixedHeight(126)
        self.reply_layout = QHBoxLayout(self.reply_trail); self.reply_layout.setContentsMargins(0,0,0,0)
        self.reply_layout.setSpacing(10); self.reply_layout.setAlignment(Qt.AlignCenter)
        center.addWidget(self.reply_trail)
        content.addLayout(center, 1)

        right = QVBoxLayout(); right.setSpacing(10); right.setContentsMargins(0, 0, 0, 0); right.setAlignment(Qt.AlignTop)
        self.right_connections = self._side_card('CONEXÕES', 'GMAIL • AGENDA', 'Teste e acompanhe suas integrações pela Central de conexões.')
        self.right_system = self._side_card('SISTEMA', 'VOZ LOCAL', 'A fala continua configurada para reduzir o uso da GPU.')
        self.right_attention = self._side_card('ATENÇÃO', 'NENHUM ALERTA', 'Novos avisos entram como cartão e notificação.')
        for card in (self.right_connections, self.right_system, self.right_attention): right.addWidget(card)
        content.addLayout(right, 0)
        outer.addLayout(content, 1)
        shortcuts = QHBoxLayout(); shortcuts.addStretch()
        briefing = QPushButton('Resumo do dia'); briefing.clicked.connect(lambda: self.enqueue_command('resumo do dia'))
        shortcuts.addWidget(briefing)
        history = QPushButton('Histórico da conversa'); history.clicked.connect(lambda: self._show_controls(1)); shortcuts.addWidget(history)
        stop = QPushButton('Interromper · Esc'); stop.clicked.connect(self.interrupt_speech); shortcuts.addWidget(stop)
        shortcuts.addStretch(); outer.addLayout(shortcuts)
        row = QHBoxLayout(); row.addStretch()
        self.input = QLineEdit(); self.input.setPlaceholderText('Fale com o V ou digite seu pedido…')
        self.input.setFixedWidth(490); self.input.returnPressed.connect(self.submit_text)
        self.input.setAccessibleName('Mensagem para o V'); row.addWidget(self.input)
        self.send_btn = QPushButton('Enviar'); self.send_btn.clicked.connect(self.submit_text); row.addWidget(self.send_btn)
        row.addStretch(); outer.addLayout(row)
        panel_accent = '#ff6875' if self.visual_theme == 'red' else '#50d8ff'
        panel_border = 'rgba(214,53,77,170)' if self.visual_theme == 'red' else 'rgba(56,173,231,160)'
        self.info_panel = VInternalPanel(accent=panel_accent, border=panel_border, parent=root)
        self._build_controls()

    def _build_reference_ui(self):
        from PySide6.QtWidgets import QScrollArea
        self._reply_cards, self._reply_buttons, self._current_reply = [], [], ''
        root = QWidget(); self.setCentralWidget(root)
        self.neural = BriefingBackdrop(root, theme='red')
        self.reference_brand = QLabel('V  /  ASSISTENTE PESSOAL    ·    GERENCIAR', root)
        self.reference_brand.setObjectName('tinyStrong'); self.reference_brand.setAlignment(Qt.AlignCenter)
        self.state_label = QLabel('EM ESPERA', root); self.state_label.hide()
        self.intent_label = QLabel('EM ESPERA', root); self.intent_label.setAlignment(Qt.AlignCenter)
        self.intent_label.setStyleSheet('color:#ff6473; font-size:12px; letter-spacing:5px;')
        self.clock = QLabel(root); self.clock.setObjectName('tiny')
        self.reference_menu = QFrame(root); self.reference_menu.setObjectName('orbitalSide')
        menu = QVBoxLayout(self.reference_menu); menu.setContentsMargins(9, 12, 9, 12); menu.setSpacing(6)
        caption = QLabel('CONTROLES'); caption.setObjectName('sideEyebrow'); menu.addWidget(caption)
        for title, callback in [
            ('Bom dia', lambda: self.enqueue_command('resumo do dia')),
            ('Notificações', self.show_notification_center),
            ('Conexões', self.show_connections_center),
            ('Câmera', self.show_camera),
            ('Memórias', self.show_memory_center),
            ('Projetos', self.show_project_center),
            ('Editar bom dia', self.show_briefing_editor),
            ('Histórico', lambda: self._show_controls(1)),
            ('Voz e controles', self._show_controls),
            ('Ferramentas', self._toggle_tools),
            ('Interromper · Esc', self.interrupt_speech),
        ]:
            button = QPushButton(title); button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet('text-align:left; border-radius:5px; padding:6px 8px; font-size:11px;')
            button.clicked.connect(lambda checked=False, action=callback: action()); menu.addWidget(button)
        self.reference_health = self._side_card('ESTE COMPUTADOR', 'CPU —  /  RAM —', 'Aguardando medição local.')
        self.reference_health.setParent(root)
        self.reference_status = self._side_card('SESSÃO', 'EM ESPERA', 'Escuta desativada')
        self.reference_status.setParent(root)
        self.response_card = QFrame(root); self.response_card.setObjectName('orbitalCard')
        layout = QVBoxLayout(self.response_card); layout.setContentsMargins(16,12,16,12)
        kicker = QLabel('CONVERSA  /  V'); kicker.setObjectName('sideEyebrow'); layout.addWidget(kicker)
        self.response_title = QLabel('Seu assistente está pronto'); self.response_title.setTextFormat(Qt.PlainText)
        self.response_title.setStyleSheet('font-size:17px; font-weight:600;'); layout.addWidget(self.response_title)
        self.response = QTextBrowser(); self.response.setOpenExternalLinks(False); layout.addWidget(self.response,1)
        self.last_action = QLabel(''); self.last_action.setObjectName('tiny'); self.last_action.setMaximumHeight(28)
        layout.addWidget(self.last_action)
        self.reference_scroll = QScrollArea(root); self.reference_scroll.setWidgetResizable(True)
        self.reference_scroll.setStyleSheet('QScrollArea {border:0;background:transparent;}')
        self.reference_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reply_trail = QWidget(); self.reference_scroll.setWidget(self.reply_trail)
        self.reply_layout = QHBoxLayout(self.reply_trail); self.reply_layout.setContentsMargins(0,0,0,0)
        self.reply_layout.setSpacing(10); self.reply_layout.setAlignment(Qt.AlignCenter)
        self.reference_dock = QWidget(root); dock = QHBoxLayout(self.reference_dock); dock.setContentsMargins(0,0,0,0)
        self.input = QLineEdit(); self.input.setPlaceholderText('Escreva seu pedido…'); self.input.returnPressed.connect(self.submit_text)
        self.input.setAccessibleName('Mensagem para o V'); dock.addWidget(self.input)
        self.send_btn = QPushButton('Enviar'); self.send_btn.clicked.connect(self.submit_text); dock.addWidget(self.send_btn)
        self.reference_dock.hide()
        self.keyboard_button = QPushButton('Digitar', root); self.keyboard_button.clicked.connect(self._toggle_reference_input)
        self.listen_button = QPushButton('◉', root); self.listen_button.setToolTip('Ativar ou desativar voz contínua')
        self.listen_button.setAccessibleName('Ativar ou desativar voz contínua')
        self.listen_button.clicked.connect(self.toggle_continuous_voice)
        self.listen_button.setStyleSheet('border-radius:17px; padding:0; color:#ff9ba5; background:#390813; border:1px solid #f64b61;')
        self.info_panel = VInternalPanel(accent='#ff6875', border='rgba(214,53,77,170)', parent=root)
        self._build_controls()
        self._position_reference()
        QTimer.singleShot(0, self._position_reference)

    def _toggle_reference_input(self):
        self.reference_dock.setVisible(not self.reference_dock.isVisible())
        if self.reference_dock.isVisible(): self.input.setFocus()

    def _position_reference(self):
        if not hasattr(self, 'reference_menu'): return
        stage = getattr(self, 'reference_stage', self.centralWidget())
        w, h = stage.width(), stage.height()
        self.neural.setGeometry(0,0,w,h)
        self.reference_brand.setGeometry(w//2-230, 10, 460, 24)
        self.intent_label.setGeometry(w//2-250, 58, 500, 30)
        self.clock.setGeometry(w-154, 14, 140, 24)
        self.reference_menu.setGeometry(16, 112, 150, min(450,h-200))
        self.reference_health.setGeometry(184, 126, 218, 106)
        self.reference_status.setGeometry(w-208, 126, 192, 112)
        cw = min(440, w-420); ch = 208
        self.response_card.setGeometry((w-cw)//2, max(248, int(h*.31)), cw, ch)
        self.reference_scroll.setGeometry(180, int(h*.64), w-400, 140)
        self.reference_dock.setGeometry(w//2-230, h-105, 460, 44)
        self.listen_button.setGeometry(w//2-17, h-44, 34,34)
        self.keyboard_button.setGeometry(w//2+30,h-44,70,32)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_reference()

    def _side_card(self, eyebrow, title, body):
        frame = QFrame(); frame.setObjectName('orbitalSide'); frame.setMinimumWidth(184); frame.setMaximumWidth(226)
        layout = QVBoxLayout(frame); layout.setContentsMargins(13, 12, 13, 12); layout.setSpacing(5)
        top = QLabel(eyebrow); top.setObjectName('sideEyebrow'); layout.addWidget(top)
        main = QLabel(title); main.setObjectName('sideTitle'); main.setWordWrap(True); layout.addWidget(main)
        detail = QLabel(body); detail.setObjectName('sideBody'); detail.setWordWrap(True); layout.addWidget(detail)
        frame._v_title = main; frame._v_body = detail
        return frame

    def _build_controls(self):
        self.controls_dialog = QDialog(self); self.controls_dialog.setWindowTitle('V / Controles')
        self.controls_dialog.resize(660, 540)
        layout = QVBoxLayout(self.controls_dialog)
        self.control_tabs = QTabWidget(); layout.addWidget(self.control_tabs)
        voice = QWidget(); cr = QVBoxLayout(voice); cr.setSpacing(10)
        self.control_tabs.addTab(voice, 'Voz e escuta')
        self.mic_combo = QComboBox(); self.mic_combo.setAccessibleName('Microfone'); cr.addWidget(self.mic_combo)
        self.voice_toggle = QPushButton('ATIVAR VOZ CONTÍNUA'); self.voice_toggle.clicked.connect(self.toggle_continuous_voice); cr.addWidget(self.voice_toggle)
        self.voice_status = QLabel('Microfone em espera.'); self.voice_status.setWordWrap(True); cr.addWidget(self.voice_status)
        self.test_mic = QPushButton('Testar microfone'); self.test_mic.clicked.connect(self.start_mic_test); cr.addWidget(self.test_mic)
        self.test_voice = QPushButton('Ouvir o V'); self.test_voice.clicked.connect(self.test_v_voice); cr.addWidget(self.test_voice)
        self.tts_toggle = QCheckBox('Respostas em voz alta'); self.tts_toggle.setChecked(True); cr.addWidget(self.tts_toggle)
        self.process_sound_toggle = QCheckBox('Som durante o processamento')
        self.process_sound_toggle.setChecked(self.processing_sound.enabled)
        self.process_sound_toggle.toggled.connect(self._toggle_processing_sound); cr.addWidget(self.process_sound_toggle)
        self.process_sound_status = QLabel(f'FX {self.processing_sound.backend.upper()}'); cr.addWidget(self.process_sound_status)
        self.mode_switch_btn = QPushButton('Trocar interface · F6'); self.mode_switch_btn.clicked.connect(self.request_mode_switch); cr.addWidget(self.mode_switch_btn)
        cr.addStretch()
        self.chat = QTextEdit(); self.chat.setReadOnly(True); self.control_tabs.addTab(self.chat, 'Conversa')
        system = QWidget(); sl = QVBoxLayout(system); self.control_tabs.addTab(system, 'Sistema')
        sl.addWidget(QLabel('CPU')); self.cpu = QProgressBar(); sl.addWidget(self.cpu)
        sl.addWidget(QLabel('RAM')); self.ram = QProgressBar(); sl.addWidget(self.ram)
        self.ai_status = QLabel('Diagnóstico · F8')
        self.spotify_api_status = QLabel('Spotify · consulte o diagnóstico')
        self.spotify_bridge_status = QLabel('Bridge · consulte o diagnóstico')
        self.memory_status = QLabel('Memória local')
        self.latency_status = QLabel('Tempo de resposta · aguardando')
        for label in (self.ai_status, self.spotify_api_status, self.spotify_bridge_status, self.memory_status, self.latency_status):
            label.setWordWrap(True); sl.addWidget(label)
        diagnostics = QPushButton('Abrir diagnóstico · F8'); diagnostics.clicked.connect(self.show_diagnostics); sl.addWidget(diagnostics)
        sl.addStretch()
        from .gmail_settings import GmailSettings
        self.control_tabs.addTab(GmailSettings(self), 'Gmail')

    def _toggle_tools(self):
        self.session_toolbar.setVisible(not self.session_toolbar.isVisible())

    def _show_controls(self, tab=0):
        if hasattr(self,'desktop_shell'):
            self.desktop_shell.select('chat' if int(tab)==1 else 'settings')
            return
        self.control_tabs.setCurrentIndex(int(tab)); self.controls_dialog.show(); self.controls_dialog.raise_()

    def show_briefing_editor(self):
        if hasattr(self,'desktop_shell'): self.desktop_shell.select('editor')
        else: super().show_briefing_editor()

    def show_connections_center(self):
        if hasattr(self,'desktop_shell'): self.desktop_shell.select('connections')
        else: super().show_connections_center()

    def show_notification_center(self):
        if hasattr(self,'desktop_shell'): self.desktop_shell.select('notices')
        else: super().show_notification_center()

    def show_memory_center(self):
        if hasattr(self,'desktop_shell'): self.desktop_shell.select('memory')
        else: super().show_memory_center()

    def show_project_center(self):
        if hasattr(self,'desktop_shell'): self.desktop_shell.select('projects')
        else: super().show_project_center()

    @Slot(object)
    def _command_done(self, results):
        if hasattr(self,'desktop_shell'):
            for result in results or []:
                data=getattr(result,'data',None) or {}
                if data.get('kind')=='daily_briefing' and data.get('items'):
                    self.desktop_shell.update_briefing(data['items'])
        super()._command_done(results)

    def set_state(self, state):
        super().set_state(state)
        state = str(state or 'READY').upper()
        labels = {'READY':'PRONTO PARA AJUDAR', 'LISTENING':'OUVINDO', 'PROCESSING':'PREPARANDO', 'SPEAKING':'FALANDO', 'ERROR':'VERIFIQUE O DIAGNÓSTICO'}
        state_labels = {'READY':'● EM ESPERA', 'LISTENING':'● OUVINDO', 'PROCESSING':'● PROCESSANDO', 'SPEAKING':'● FALANDO', 'ERROR':'● ERRO'}
        self.intent_label.setText(labels.get(state, state))
        if self.visual_theme == 'red' and state == 'READY': self.intent_label.setText('EM ESPERA')
        self.state_label.setText(state_labels.get(state, f'● {state}'))
        if hasattr(self, 'left_activity'):
            self.left_activity._v_title.setText({'READY':'AGUARDANDO', 'LISTENING':'ESCUTANDO', 'PROCESSING':'PREPARANDO', 'SPEAKING':'NARRANDO', 'ERROR':'REVISAR'}.get(state, state))
            self.left_activity._v_body.setText('O núcleo visual acompanha o estado atual do V.')

    def _update_system(self):
        super()._update_system()
        self.cpu.setToolTip(f'CPU: {self.cpu.value()}%'); self.ram.setToolTip(f'RAM: {self.ram.value()}%')
        if hasattr(self, 'reference_health'):
            self.reference_health._v_title.setText(f'CPU {self.cpu.value()}%  /  RAM {self.ram.value()}%')
            self.reference_health._v_body.setText('Uso atual do computador')
            self.reference_status._v_title.setText(self.intent_label.text())
            self.reference_status._v_body.setText('Escuta ativada' if self.voice_enabled else 'Escuta desativada')

    def append_user(self, text):
        super().append_user(text)
        self.response_title.setText('Seu pedido')
        self.response_card.show()
        self.response.setPlainText(str(text))

    def append_v(self, text):
        super().append_v(text)
        text = str(text)
        if text.startswith('V Prototype '):
            self.response.setPlainText('Bom ter você por aqui. Diga “V” ou escreva seu pedido.\n\nPara começar, você pode pedir o resumo do dia.')
            if self.visual_theme == 'red': self.response_card.hide()
            return
        self.response_card.show()
        if self._current_reply:
            self._reply_cards.append(self._current_reply)
            self._reply_cards = self._reply_cards[-3:]
        self._current_reply = text
        self.response_title.setText('V / Resposta')
        self.response.setPlainText(text)
        self._refresh_reply_trail()

    def _refresh_reply_trail(self):
        while self.reply_layout.count():
            item = self.reply_layout.takeAt(0)
            if item.widget(): item.widget().hide(); item.widget().deleteLater()
        self._reply_buttons = []
        for i, text in enumerate(self._reply_cards):
            button = TopicThumbnail({'kind':'conversa', 'title':f'Resposta anterior {i+1}', 'body':text}, theme=self.visual_theme)
            button.clicked.connect(lambda checked=False, value=text: self._revisit_reply(value))
            self.reply_layout.addWidget(button); self._reply_buttons.append(button)

    def _revisit_reply(self, text):
        self.response_title.setText('V / Resposta anterior')
        self.response.setPlainText(text)

    def closeEvent(self, event):
        self.controls_dialog.close()
        super().closeEvent(event)
