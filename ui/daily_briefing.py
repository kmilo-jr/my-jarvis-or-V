"""A spoken topic in focus, with a persistent, clickable trail of earlier topics."""
import time
from urllib.parse import urlparse
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from .briefing_scene import BriefingBackdrop, TopicThumbnail
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QTextBrowser, QScrollArea, QWidget, QGraphicsOpacityEffect, QProgressBar, QToolBar)


class BriefingPanel(QFrame):
    def __init__(self, window):
        super().__init__(window.centralWidget())
        self.window = window
        self.visual_theme = str(getattr(window, 'visual_theme', 'blue') or 'blue').lower()
        self.video_style = self.visual_theme == 'red'
        self.cards = []
        self.index = -1
        self.active = False
        self.paused = False
        self._started = 0.0
        self._silent = False
        self._generation = 0
        self._buttons = []
        self._visited = set()
        self._receipt = None
        self._details = False
        self._detail_pending = False
        self._toolbars = []
        self._image_cache = {}
        self._image_replies = set()
        self.network = QNetworkAccessManager(self)
        self.backdrop = BriefingBackdrop(self, theme=self.visual_theme)
        self._ghost = None
        self._flight = None
        self.setObjectName('dailyBriefing')
        self.setStyleSheet("""
            QFrame#dailyBriefing { background:transparent; border:0; }
            QFrame#briefCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(3,23,51,248),stop:0.55 rgba(4,38,96,241),stop:1 rgba(1,10,31,250)); border:1px solid #278dde; border-radius:7px; }
            QLabel { background:transparent; color:#dcf5ff; border:0; }
            QLabel#briefKicker { color:#49d1ff; font-size:10px; letter-spacing:2px; }
            QLabel#briefTitle { font-size:19px; font-weight:600; }
            QLabel#briefMetric { font-size:34px; color:#8aeaff; }
            QLabel#briefSource { color:#6eabd2; font-size:10px; }
            QTextBrowser { background:transparent; color:#cbe9ff; border:0; font-size:14px; padding:0; }
            QPushButton { background:rgba(3,24,58,180); color:#89c6e9; border:1px solid #1b4d7a; border-radius:5px; padding:6px 10px; font-size:11px; }
            QPushButton:hover { background:#083e78; border-color:#38caff; color:#e1f8ff; }
            QPushButton:disabled { color:#416282; border-color:#183450; }
            QScrollArea, QWidget#briefTrail { background:transparent; border:0; }
            QScrollBar:horizontal { height:4px; background:transparent; }
            QScrollBar::handle:horizontal { background:#267eb4; min-width:20px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
        """)
        if self.video_style:
            self.setStyleSheet(self._red_style())
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 16, 24, 58)
        outer.setSpacing(8)
        head = QHBoxLayout()
        brand = QLabel('V  /  RESUMO DO DIA'); brand.setObjectName('briefKicker')
        head.addWidget(brand); head.addStretch()
        self.status = QLabel('PREPARANDO'); self.status.setObjectName('briefSource')
        head.addWidget(self.status)
        close = QPushButton('Fechar'); close.clicked.connect(self.close_briefing)
        head.addWidget(close); outer.addLayout(head)
        self.progress = QProgressBar(); self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False); self.progress.setFixedHeight(4)
        self.progress.hide()
        self.progress_animation = QPropertyAnimation(self.progress, b'value', self)
        self.progress_animation.setDuration(360)
        self.progress_animation.setEasingCurve(QEasingCurve.OutCubic)

        self.scene = QWidget(); self.scene.setMinimumHeight(330)
        outer.addWidget(self.scene, 1)
        self.voice_label = QLabel('PREPARANDO', self.scene)
        self.voice_label.setAlignment(Qt.AlignCenter)
        self.voice_label.setStyleSheet('color:#41ceff; font-size:12px; letter-spacing:5px;')
        if self.video_style:
            self.voice_label.setStyleSheet('color:#ff6473; font-size:12px; letter-spacing:5px;')
        self.focus_card = QFrame(self.scene); self.focus_card.setObjectName('briefCard')
        focus = QVBoxLayout(self.focus_card); focus.setContentsMargins(16, 12, 16, 12); focus.setSpacing(7)
        top = QHBoxLayout()
        self.category = QLabel(); self.category.setObjectName('briefKicker')
        self.metric_label = QLabel(); self.metric_label.setObjectName('briefMetric')
        top.addWidget(self.category); top.addStretch(); top.addWidget(self.metric_label)
        focus.addLayout(top)
        self.title = QLabel(); self.title.setObjectName('briefTitle'); self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.PlainText); focus.addWidget(self.title)
        self.news_image = QLabel(); self.news_image.setAlignment(Qt.AlignCenter); self.news_image.hide()
        focus.addWidget(self.news_image)
        self.body = QTextBrowser(); self.body.setOpenExternalLinks(False)
        self.body.setMinimumHeight(32)
        focus.addWidget(self.body, 1)
        self.source = QLabel(); self.source.setObjectName('briefSource'); self.source.setWordWrap(True)
        self.source.setTextFormat(Qt.PlainText); focus.addWidget(self.source)

        self.up_next = QLabel(); self.up_next.setObjectName('briefSource')
        self.up_next.setTextFormat(Qt.PlainText); self.up_next.setWordWrap(True)
        self.up_next.setAlignment(Qt.AlignCenter); outer.addWidget(self.up_next)

        self.trail_scroll = QScrollArea(self.scene); self.trail_scroll.setWidgetResizable(True)
        self.trail_scroll.setFixedHeight(134)
        self.trail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        trail = QWidget(); trail.setObjectName('briefTrail')
        self.trail = QHBoxLayout(trail); self.trail.setContentsMargins(0, 0, 0, 0); self.trail.setSpacing(10); self.trail.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.trail_scroll.setWidget(trail)
        self._build_video_side_panels()
        row = QHBoxLayout()
        self.previous = QPushButton('← Voltar'); self.previous.clicked.connect(lambda: self.navigate(-1))
        self.pause_button = QPushButton('Pausar'); self.pause_button.clicked.connect(self.toggle_pause)
        self.next_button = QPushButton('Próximo →'); self.next_button.clicked.connect(lambda: self.navigate(1))
        self.open_button = QPushButton('Abrir fonte'); self.open_button.clicked.connect(self.open_source)
        self.details_button = QPushButton('Me explique melhor'); self.details_button.clicked.connect(self.explain)
        for button in (self.previous, self.pause_button, self.next_button):
            row.addWidget(button)
        row.addStretch(); row.addWidget(self.details_button); row.addWidget(self.open_button)
        self.controls_row = QWidget(); self.controls_row.setLayout(row); outer.addWidget(self.controls_row)
        if self.video_style:
            self.controls_row.hide()
            self._populate_video_options()
        hint = QLabel('Diga “V, me explique melhor” ou “V, retomar resumo”. Para interromper falando, ative “Interromper por voz” e use fones.')
        hint.setObjectName('briefSource'); hint.setWordWrap(True); outer.addWidget(hint)
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll)
        self.effect = QGraphicsOpacityEffect(self.focus_card); self.focus_card.setGraphicsEffect(self.effect)
        self.fade = QPropertyAnimation(self.effect, b'opacity', self)
        self.fade.setDuration(450); self.fade.setStartValue(.0); self.fade.setEndValue(1.)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)
        self.hide()

    def _populate_video_options(self):
        for button in (self.previous, self.pause_button, self.next_button, self.details_button, self.open_button):
            button.setParent(self.options_panel)
            self.options_layout.addWidget(button)
            self.video_option_buttons.append(button)
        for text, method in [('Notificações', 'show_notification_center'), ('Conexões', 'show_connections_center'), ('Editar bom dia', 'show_briefing_editor')]:
            callback = getattr(self.window, method, None)
            if callable(callback):
                button = QPushButton(text); button.clicked.connect(lambda checked=False, action=callback: action())
                self.options_layout.addWidget(button)
        self.options_layout.addStretch()

    def _red_style(self):
        return """
            QFrame#dailyBriefing { background:transparent; border:0; }
            QFrame#briefCard { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(64,6,20,248),stop:0.55 rgba(105,10,29,242),stop:1 rgba(25,2,9,250)); border:1px solid #ef4057; border-radius:9px; }
            QFrame#briefSide { background:rgba(34,4,13,224); border:1px solid rgba(193,42,65,185); border-radius:8px; }
            QLabel { background:transparent; color:#ffe4e7; border:0; }
            QLabel#briefKicker { color:#ff6573; font-size:10px; letter-spacing:2px; }
            QLabel#briefTitle { font-size:19px; font-weight:650; color:#fff0f1; }
            QLabel#briefMetric { font-size:34px; color:#ff9da5; }
            QLabel#briefSource { color:#d69ba4; font-size:10px; }
            QLabel#briefSideKicker { color:#e75a6d; font-size:9px; font-weight:700; letter-spacing:1.5px; }
            QLabel#briefSideTitle { color:#ffe5e8; font-size:14px; font-weight:650; }
            QLabel#briefSideBody { color:#d19aa3; font-size:10px; }
            QTextBrowser { background:transparent; color:#ffe0e4; border:0; font-size:13px; padding:0; }
            QPushButton { background:rgba(67,7,22,205); color:#ffd5da; border:1px solid #9f2b42; border-radius:5px; padding:6px 10px; font-size:11px; }
            QPushButton:hover { background:#74172d; border-color:#ff7b86; color:#fff2f3; }
            QPushButton:disabled { color:#7f3544; border-color:#541827; }
            QScrollArea, QWidget#briefTrail { background:transparent; border:0; }
            QScrollBar:horizontal { height:4px; background:transparent; }
            QScrollBar::handle:horizontal { background:#bd304a; min-width:20px; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
        """

    def _build_video_side_panels(self):
        self.left_side = QFrame(self.scene); self.left_side.setObjectName('briefSide')
        left = QVBoxLayout(self.left_side); left.setContentsMargins(12, 12, 12, 12); left.setSpacing(5)
        left_kicker = QLabel('PRONTIDÃO DO V'); left_kicker.setObjectName('briefSideKicker'); left.addWidget(left_kicker)
        self.left_side_title = QLabel('Resumo do dia'); self.left_side_title.setObjectName('briefSideTitle'); left.addWidget(self.left_side_title)
        self.left_side_body = QLabel('Aguardando os dados.'); self.left_side_body.setObjectName('briefSideBody'); self.left_side_body.setWordWrap(True); left.addWidget(self.left_side_body)
        left.addStretch()
        self.right_side = QFrame(self.scene); self.right_side.setObjectName('briefSide')
        right = QVBoxLayout(self.right_side); right.setContentsMargins(12, 12, 12, 12); right.setSpacing(5)
        right_kicker = QLabel('CONEXÕES'); right_kicker.setObjectName('briefSideKicker'); right.addWidget(right_kicker)
        self.right_side_title = QLabel('GMAIL · AGENDA'); self.right_side_title.setObjectName('briefSideTitle'); right.addWidget(self.right_side_title)
        self.right_side_body = QLabel('Mensagens, agenda e alertas ficam nos cartões do briefing.'); self.right_side_body.setObjectName('briefSideBody'); self.right_side_body.setWordWrap(True); right.addWidget(self.right_side_body)
        right.addStretch()
        self.options_panel = QFrame(self.scene); self.options_panel.setObjectName('briefSide')
        self.options_layout = QVBoxLayout(self.options_panel); self.options_layout.setContentsMargins(10, 10, 10, 10); self.options_layout.setSpacing(6)
        options_title = QLabel('OPÇÕES'); options_title.setObjectName('briefSideKicker'); self.options_layout.addWidget(options_title)
        self.video_option_buttons = []
        if not self.video_style:
            self.left_side.hide(); self.right_side.hide(); self.options_panel.hide()

    def position(self):
        self.setGeometry(self.window.centralWidget().rect())
        self.layout().activate()
        self._position_scene()
        self.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.backdrop.setGeometry(self.rect())
        self.layout().activate()
        self._position_scene()

    def _position_scene(self):
        if not hasattr(self, 'scene'):
            return
        width, height = self.scene.width(), self.scene.height()
        if self.video_style:
            self._position_reference_scene(width, height)
            return
        card_width = min(430 if self.video_style else 520, max(300, width - 40))
        news = 0 <= self.index < len(self.cards) and self.cards[self.index]['kind'] == 'notícias'
        card_height = min(300 if news else (214 if self.video_style else 270), max(180, height - 180))
        y = max(46, (height - card_height - (170 if self.video_style else 142)) // 2 + 12)
        self.focus_card.setGeometry((width-card_width)//2, y, card_width, card_height)
        self.voice_label.setGeometry(0, max(0, y-47), width, 28)
        trail_width = min(width-24, max(card_width, len(self.cards) * (150 if self.video_style else 176)))
        self.trail_scroll.setGeometry((width-trail_width)//2, y+card_height+12, trail_width, 134 if self.video_style else 134)
        if self.video_style:
            self.left_side.setGeometry(20, max(60, y-8), 190, 142)
            self.right_side.setGeometry(width-210, max(60, y-8), 190, 160)
            self.options_panel.setGeometry(20, max(60, y+142), 190, 218)
            self.left_side.raise_(); self.right_side.raise_()
            self.options_panel.raise_()
            self.focus_card.raise_(); self.voice_label.raise_(); self.trail_scroll.raise_()
        self.backdrop.lower()

    def _position_reference_scene(self, width, height):
        completed = bool(self.cards) and not self.active and self.index == len(self.cards)-1
        cw = min(430, width-430)
        news = 0 <= self.index < len(self.cards) and self.cards[self.index]['kind'] == 'notícias'
        ch = 290 if news else 218
        y = max(148, int(height*.28))
        self.voice_label.setGeometry(width//2-250, 8, 500, 28)
        self.focus_card.setVisible(not completed)
        self.focus_card.setGeometry((width-cw)//2,y,cw,ch)
        self.options_panel.setGeometry(0, 80, 150, min(360,height-90))
        self.left_side.setGeometry(166, 80, 194, 108)
        self.right_side.setGeometry(width-196, 80, 190, 110)
        trail_y = int(height*.51) if completed else y+ch+12
        self.trail_scroll.setGeometry(166, trail_y, width-376, 134)
        self.backdrop.lower()

    def _stop_flight(self):
        if self._flight is not None:
            self._flight.stop(); self._flight.deleteLater(); self._flight = None
        if self._ghost is not None:
            self._ghost.hide(); self._ghost.deleteLater(); self._ghost = None

    def _fly_to_trail(self, pixmap, index):
        self._stop_flight()
        if pixmap is None or self._buttons[index].isHidden():
            return
        self.trail_scroll.widget().layout().activate()
        self.trail_scroll.ensureWidgetVisible(self._buttons[index])
        target = self._buttons[index]
        self._ghost = QLabel(self.scene)
        self._ghost.setPixmap(pixmap); self._ghost.setScaledContents(True)
        self._ghost.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._ghost.setGeometry(self.focus_card.geometry()); self._ghost.show()
        self._flight = QPropertyAnimation(self._ghost, b'geometry', self)
        self._flight.setDuration(520); self._flight.setEasingCurve(QEasingCurve.InOutCubic)
        self._flight.setStartValue(self.focus_card.geometry())
        self._flight.setEndValue(QRect(target.mapTo(self.scene, QPoint(0, 0)), target.size()))
        self._flight.finished.connect(self._stop_flight)
        self._flight.start()

    def start(self, cards):
        self.cancel()
        self.cards = [dict(c) for c in cards]
        if not self.cards:
            return
        while self.trail.count():
            widget = self.trail.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        self._buttons = []
        self._visited = set()
        self.index = -1
        self.progress_animation.stop(); self.progress.setValue(0)
        for i, item in enumerate(self.cards):
            button = TopicThumbnail(item, theme=self.visual_theme)
            if self.video_style:
                button.setFixedSize(150, 112)
            button.clicked.connect(lambda checked=False, index=i: self.present(index, automatic=False))
            self.trail.addWidget(button); self._buttons.append(button)
        self._toolbars = [bar for bar in self.window.findChildren(QToolBar) if bar.isVisible()]
        for bar in self._toolbars:
            bar.hide()
        self.show(); self.position(); self.present(0)
        self.backdrop.timer.start()
        game_mode = getattr(self.window, 'game_mode', None)
        if game_mode is not None:
            game_mode.refresh_rendering()
        QTimer.singleShot(0, self.position)

    def present(self, index, automatic=True):
        if not 0 <= index < len(self.cards):
            return
        previous_index = self.index
        outgoing = None
        if self.isVisible() and 0 <= previous_index < len(self.cards) and previous_index != index:
            self.fade.stop(); self.effect.setOpacity(1)
            outgoing = self.focus_card.grab()
        self._generation += 1
        self._details = False
        self._detail_pending = False
        self.details_button.setEnabled(True)
        self.details_button.setText('Me explique melhor')
        self.timer.stop()
        self.window.voice_engine.stop_speaking()
        self.window.processing_sound.stop()
        self.index = index
        self._position_scene()
        self.active = True
        self.focus_card.show()
        self.paused = not automatic
        self._started = time.monotonic()
        self._silent = not self.window.tts_toggle.isChecked()
        self._receipt = None
        self._visited.add(index)
        item = self.cards[index]
        if self.video_style:
            self.left_side_title.setText(f'{index+1:02d} / {len(self.cards):02d} assuntos')
            self.left_side_body.setText('Dados desta consulta · ' + time.strftime('%H:%M'))
            self.right_side_title.setText(item['kind'].upper())
            self.right_side_body.setText(item.get('source') or ('Consulta disponível' if item.get('ok', True) else 'Consulta indisponível'))
        self.category.setText(f"{item['kind'].upper()}  /  {index+1:02d}")
        self.title.setText(item['title']); self.body.setPlainText(item['body'])
        self.metric_label.setText(item.get('metric', ''))
        self.metric_label.setVisible(item['kind'] != 'notícias')
        self.source.setText(item.get('source', ''))
        self._show_image(item)
        self.status.setText(f'{index+1:02d} / {len(self.cards):02d} ASSUNTOS')
        self.up_next.setText('A SEGUIR  /  ' + self.cards[index+1]['title']
                             if index+1 < len(self.cards) else 'ÚLTIMO ASSUNTO  /  Você pode revisitar os cartões abaixo.')
        self.progress_animation.stop()
        self.progress_animation.setStartValue(self.progress.value())
        self.progress_animation.setEndValue(round((index+1) / len(self.cards) * 1000))
        self.progress_animation.start()
        self.previous.setEnabled(index > 0); self.next_button.setEnabled(index < len(self.cards)-1)
        self.open_button.setEnabled(self._source_url() != '')
        self.pause_button.setText('Continuar' if self.paused else 'Pausar')
        for i, button in enumerate(self._buttons):
            # All fetched cards are readable immediately, independent of TTS.
            button.setVisible(i != index and self.cards[i]['kind'] != 'seu dia')
            button.setChecked(i == index)
        self._position_scene()
        self._fly_to_trail(outgoing, previous_index)
        self.fade.stop(); self.fade.start()
        if not self._silent:
            self.window.set_state('SPEAKING')
            profile = 'qwen_local' if item['kind'] == 'seu dia' else 'piper'
            self._receipt = self.window.voice_engine.speak_tracked(item['speech'], profile=profile)
        else:
            self.window.set_state('READY')
        self._update_voice_label()
        self.timer.start(120)

    def explain(self):
        if not self.cards or self._detail_pending:
            return
        if self._details:
            self.present(self.index, automatic=False)
            return
        self._generation += 1
        self.active = True; self.paused = True
        self._details = True; self._detail_pending = True
        self.timer.stop(); self.window.voice_engine.stop_speaking()
        self._receipt = None
        self.status.setText('PREPARANDO EXPLICAÇÃO · RESUMO PAUSADO')
        self.voice_label.setText('PREPARANDO'); self.backdrop.speaking = False
        self.pause_button.setText('Retomar resumo')
        self.details_button.setEnabled(False)
        self.window.request_briefing_details(self.cards[self.index], self._generation)

    def finish_details(self, generation, text):
        if generation != self._generation or not self.active or not self.isVisible():
            return False
        self._detail_pending = False
        self.details_button.setEnabled(True); self.details_button.setText('Ver cartão original')
        self.news_image.hide()
        self.body.setPlainText(text)
        self.status.setText('EM DETALHES · RESUMO PAUSADO')
        self.fade.stop(); self.fade.start()
        if self.window.tts_toggle.isChecked():
            self.window.set_state('SPEAKING')
            self._receipt = self.window.voice_engine.speak_tracked(text, profile='piper')
            self.timer.start(120)
        return True

    def poll(self):
        self._update_voice_label()
        if not self.active:
            return
        if self.paused:
            if self._receipt is None or self._receipt['state'] not in ('queued', 'speaking'):
                if self._receipt is not None and self._receipt['state'] in ('failed', 'dropped'):
                    self.status.setText('VOZ INDISPONÍVEL · LEIA OS DETALHES NA TELA')
                self.timer.stop()
                self.window._settle_state_after_audio()
            return
        if self._receipt is not None:
            state = self._receipt['state']
            if state in ('queued', 'speaking'):
                return
            if state == 'cancelled':
                self.paused = True
                self.timer.stop()
                self.pause_button.setText('Continuar')
                return
            if state in ('failed', 'dropped'):
                self.status.setText('VOZ INDISPONÍVEL · CONTINUANDO A LEITURA NA TELA')
                self._silent = True
                self._started = time.monotonic()
                self._receipt = None
        elapsed = time.monotonic() - self._started
        reading_time = max(5, min(22, len(self.cards[self.index]['body'].split()) / 3))
        if self._silent and elapsed < reading_time:
            return
        self.timer.stop()
        generation = self._generation
        QTimer.singleShot(450, lambda: self._advance(generation))

    def _update_voice_label(self):
        state = self._receipt.get('state') if self._receipt else None
        speaking = state == 'speaking'
        self.backdrop.speaking = speaking
        if speaking:
            label = 'F A L A N D O'
        elif self._detail_pending or state == 'queued':
            label = 'P R E P A R A N D O'
        elif not self.active:
            label = 'EM ESPERA' if self.video_style else 'C O N C L U Í D O'
        elif self.paused:
            label = 'P A U S A D O'
        else:
            label = 'S E U   D I A'
        if state in ('queued', 'speaking'):
            narrator = 'COLEGA Z' if self._receipt.get('profile') == 'piper' else 'V'
            label += '  /  ' + narrator
        self.voice_label.setText(label)

    def _show_image(self, item):
        self.news_image.hide(); self.news_image.clear()
        if item.get('image_data'):
            import base64
            try:
                picture = QPixmap()
                if picture.loadFromData(base64.b64decode(item['image_data'], validate=True)):
                    self._set_picture(picture)
                    self._buttons[self.index].picture = picture
                    self._buttons[self.index].update()
                    return
            except (ValueError, TypeError):
                pass
        url = str(item.get('image_url', ''))
        if urlparse(url).scheme not in ('http', 'https') or not urlparse(url).netloc:
            return
        if url in self._image_cache:
            self._set_picture(self._image_cache[url])
            self._buttons[self.index].picture = self._image_cache[url]
            self._buttons[self.index].update()
            return
        generation, index = self._generation, self.index
        request = QNetworkRequest(QUrl(url)); request.setTransferTimeout(7000)
        reply = self.network.get(request)
        self._image_replies.add(reply)
        reply.readyRead.connect(lambda: reply.abort() if reply.bytesAvailable() > 3_000_000 else None)

        def finished():
            self._image_replies.discard(reply)
            if reply.error() == reply.NetworkError.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if len(data) <= 3_000_000 and pixmap.loadFromData(data):
                    pixmap = pixmap.scaled(900, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    if len(self._image_cache) >= 16:
                        self._image_cache.pop(next(iter(self._image_cache)))
                    self._image_cache[url] = pixmap
                    if index < len(self._buttons) and self.cards[index].get('image_url') == url:
                        self._buttons[index].picture = pixmap; self._buttons[index].update()
                    if generation == self._generation and not self._details:
                        self._set_picture(pixmap)
            reply.deleteLater()
        reply.finished.connect(finished)

    def _set_picture(self, pixmap):
        target_width = max(250, self.focus_card.width()-34)
        image_height = max(90, min(155, self.focus_card.height()-185))
        self.news_image.setFixedHeight(image_height)
        self.news_image.setPixmap(pixmap.scaled(target_width, image_height, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.news_image.show()

    def _advance(self, generation):
        if generation != self._generation or not self.active or self.paused:
            return
        if self.index + 1 < len(self.cards):
            self.present(self.index + 1)
        else:
            self.active = False
            if self.video_style:
                for i, button in enumerate(self._buttons):
                    button.setVisible(self.cards[i]['kind'] != 'seu dia')
                self._position_scene()
            self.status.setText('RESUMO CONCLUÍDO · ASSUNTOS DISPONÍVEIS ABAIXO')
            self.pause_button.setText('Recomeçar')
            self._update_voice_label()
            self.window._settle_state_after_audio()

    def navigate(self, offset):
        target = self.index + offset
        if 0 <= target < len(self.cards):
            self.present(target, automatic=not self.paused)

    def toggle_pause(self):
        if not self.active:
            self.present(0)
        elif self.paused:
            # Resume the current topic, since pausing may have interrupted it.
            self.present(self.index)
        else:
            self.pause()

    def pause(self):
        self.paused = True
        self._generation += 1
        self.timer.stop(); self.window.voice_engine.stop_speaking()
        self._receipt = None
        if self._detail_pending:
            self._detail_pending = False; self._details = False
            self.details_button.setEnabled(True)
        self.pause_button.setText('Continuar'); self.status.setText('PAUSADO · SEU LUGAR ESTÁ GUARDADO')
        self._update_voice_label()
        self.window._settle_state_after_audio()

    def _source_url(self):
        url = str(self.cards[self.index].get('url', '')) if self.cards and self.index >= 0 else ''
        return url if urlparse(url).scheme in ('https', 'http') and urlparse(url).netloc else ''

    def open_source(self):
        url = self._source_url()
        if url:
            if self.active:
                self.pause()
            import webbrowser
            webbrowser.open(url)

    def handle_command(self, text):
        if not self.isVisible() or not self.cards:
            return False
        if text in ('proximo', 'proxima', 'proximo assunto', 'pule esse'):
            self.navigate(1)
        elif text in ('voltar', 'anterior', 'assunto anterior'):
            self.navigate(-1)
        elif text in ('me explique melhor', 'explique melhor', 'me explica melhor', 'mais detalhes', 'detalhes desse assunto'):
            self.explain()
        elif text in ('pausar resumo', 'pause o resumo', 'pausar briefing', 'pausa', 'pausar', 'pare', 'para', 'parar', 'espere'):
            if self.active:
                self.pause()
        elif text in ('continuar resumo', 'continue o resumo', 'continuar briefing', 'retomar resumo', 'retome o resumo', 'pode continuar'):
            if self.paused or not self.active:
                self.toggle_pause()
        elif text in ('abre esse', 'abra esse', 'abrir fonte', 'abra a fonte'):
            self.open_source()
        elif text in ('repita esse', 'repita o assunto'):
            self.present(self.index)
        elif text in ('fechar resumo', 'feche o resumo'):
            self.close_briefing()
        else:
            return False
        return True

    def cancel(self):
        was_active = self.active
        self.active = False
        self._generation += 1
        self.timer.stop()
        self.fade.stop(); self.progress_animation.stop()
        self._stop_flight()
        self.backdrop.speaking = False
        self.backdrop.timer.stop()
        for reply in list(self._image_replies):
            reply.abort()
        for bar in self._toolbars:
            bar.show()
        self._toolbars = []
        self.pause_button.setText('Recomeçar')
        if was_active:
            self.window.voice_engine.stop_speaking()

    def close_briefing(self):
        self.cancel(); self.hide()
        game_mode = getattr(self.window, 'game_mode', None)
        if game_mode is not None:
            game_mode.refresh_rendering()
        self.window._settle_state_after_audio()
