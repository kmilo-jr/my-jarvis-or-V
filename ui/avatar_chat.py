"""Compact command surface sharing the main window's command and voice services."""
from PySide6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from pathlib import Path
from html import escape
from collections import deque
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextBrowser


class AvatarChat(QWidget):
    def __init__(self, window, orb):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.window = window
        self.orb = orb
        self.setWindowTitle('Conversar com V')
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.resize(390, 440)
        self.setObjectName('avatarChat')
        self._messages = deque(maxlen=16)
        self._last_answer = ''
        self._error = ''
        self.setStyleSheet("""
            QWidget { background:#121018; color:#f7e9ef; font:12px 'Segoe UI'; }
            QWidget#avatarChat { border:1px solid #663043; }
            QLabel#brand { color:#ff7098; font-size:18px; font-weight:600; }
            QLabel#subtitle { color:#af9cae; font-size:11px; }
            QLabel#presence { color:#ff98b5; background:#302030; border-radius:8px; padding:5px 9px; }
            QPushButton, QLineEdit { border:1px solid #4d3043; border-radius:9px; padding:9px; background:#211a29; }
            QPushButton:hover { background:#3c2639; border-color:#aa4669; }
            QPushButton:pressed { background:#64273f; }
            QPushButton:disabled { color:#796979; border-color:#302536; }
            QPushButton#send { background:#a62e54; color:white; border-color:#d04770; font-weight:600; }
            QLineEdit { padding:12px; background:#0e0d14; }
            QLineEdit:focus { border-color:#ff628c; }
            QTextBrowser { border:1px solid #302333; border-radius:10px; padding:10px; background:#17131e; }
            QScrollBar:vertical { width:5px; background:#17131e; }
            QScrollBar::handle:vertical { background:#684052; border-radius:2px; min-height:20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14); layout.setSpacing(10)
        header = QHBoxLayout()
        brand = QLabel('V /'); brand.setObjectName('brand'); header.addWidget(brand)
        subtitle = QLabel('SEU COMPANHEIRO'); subtitle.setObjectName('subtitle'); header.addWidget(subtitle,1)
        close = QPushButton('×'); close.setFixedSize(30,30); close.setAccessibleName('Fechar conversa compacta')
        close.clicked.connect(self.hide); header.addWidget(close); layout.addLayout(header)
        self.presence = QLabel('● Disponível'); self.presence.setObjectName('presence'); layout.addWidget(self.presence)
        self.reply = QTextBrowser(); self.reply.setOpenLinks(False)
        self.reply.setAccessibleName('Conversa com V')
        layout.addWidget(self.reply,1)
        actions = QHBoxLayout()
        self.copy_button = QPushButton('Copiar resposta'); self.copy_button.clicked.connect(self.copy_answer)
        self.clear_button = QPushButton('Limpar'); self.clear_button.clicked.connect(self.clear_conversation)
        self.stop_button = QPushButton('Parar fala'); self.stop_button.clicked.connect(self.stop_speech)
        actions.addWidget(self.copy_button,1); actions.addWidget(self.stop_button); actions.addWidget(self.clear_button)
        layout.addLayout(actions)
        self.input = QLineEdit(); self.input.setMaxLength(6000)
        self.input.setPlaceholderText('Escreva para o V…')
        self.input.setAccessibleName('Pedido para o V')
        self.input.returnPressed.connect(self.submit); layout.addWidget(self.input)
        buttons = QHBoxLayout()
        self.mic = QPushButton('Falar'); self.mic.clicked.connect(self.toggle_voice); buttons.addWidget(self.mic)
        self.send_button = QPushButton('Enviar'); self.send_button.setObjectName('send')
        self.send_button.clicked.connect(self.submit); buttons.addWidget(self.send_button,1)
        self.input.textChanged.connect(lambda text: self.send_button.setEnabled(bool(text.strip())))
        self.send_button.setEnabled(False); layout.addLayout(buttons)
        self.status = QLabel(''); self.status.setObjectName('subtitle'); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.document_path = None
        self.open_document = QPushButton('Abrir arquivo criado'); self.open_document.hide()
        self.open_document.clicked.connect(self.open_file); layout.addWidget(self.open_document)
        self.appear = QPropertyAnimation(self,b'pos',self)
        self.appear.setDuration(180); self.appear.setEasingCurve(QEasingCurve.OutCubic)
        self.orb.positionChanged.connect(self.follow_avatar)
        self.clear_conversation()
        self.timer = QTimer(self); self.timer.setInterval(500)
        self.timer.timeout.connect(self.sync_voice)

    def present(self):
        screen = self.orb.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.resize(min(390, area.width()), min(440, area.height()))
        x = self.orb.x() - self.width() - 8
        if x < area.left():
            x = self.orb.geometry().right() + 8
        target = QPoint(max(area.left(), min(x, area.right() - self.width() + 1)),
                        max(area.top(), min(self.orb.y(), area.bottom() - self.height() + 1)))
        animate = not self.isVisible()
        self.appear.stop(); self.move(target)
        self.show(); self.raise_(); self.activateWindow(); self.input.setFocus()
        if animate:
            start = QPoint(target.x(), max(area.top(), target.y()-10))
            self.appear.setStartValue(start); self.appear.setEndValue(target); self.appear.start()

    def follow_avatar(self):
        if not self.isVisible():
            return
        screen = self.orb.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.appear.stop()
        x = self.orb.x()-self.width()-8
        if x < area.left(): x = self.orb.geometry().right()+8
        self.move(max(area.left(),min(x,area.right()-self.width()+1)),
                  max(area.top(),min(self.orb.y(),area.bottom()-self.height()+1)))

    def clear_conversation(self):
        self._messages.clear(); self._last_answer = ''
        self.copy_button.setEnabled(False); self.open_document.hide()
        self.reply.setHtml('<p style="color:#ff90af;font-size:17px">Estou por aqui.</p>'
                           '<p style="color:#bcabbc">Digite um pedido ou ative o microfone.<br>O V continua recolhido enquanto conversamos.</p>')

    def copy_answer(self):
        QApplication.clipboard().setText(self._last_answer)

    def stop_speech(self):
        interrupt = getattr(self.window, 'interrupt_speech', None)
        if callable(interrupt):
            interrupt()

    def add_message(self, role, text):
        self._messages.append((role,str(text)))
        blocks=[]
        for who, content in self._messages:
            color = '#ff91af' if who == 'V' else '#bcb1ca'
            blocks.append(f'<p style="color:{color};margin-top:14px"><b>{who}</b></p>'
                          f'<p style="color:#f3e9f1">{escape(content).replace(chr(10), "<br>")}</p>')
        self.reply.setHtml(''.join(blocks)); self.reply.ensureCursorVisible()
        bar=self.reply.verticalScrollBar(); bar.setValue(bar.maximum())

    def set_reply(self, text):
        self._last_answer=str(text); self._error=''
        self.copy_button.setEnabled(bool(text)); self.add_message('V', text)

    def set_document(self, path):
        from core.documents import OUTPUT_DIR
        candidate = Path(path).resolve()
        if (candidate.is_relative_to(OUTPUT_DIR.resolve()) and candidate.is_file()
                and candidate.suffix.lower() in {'.pdf', '.docx', '.xlsx'}):
            self.document_path = candidate
            self.open_document.setToolTip(str(candidate))
            self.open_document.show()

    def open_file(self):
        if self.document_path and self.document_path.is_file():
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.document_path))):
                self.status.setText('Não consegui abrir. O caminho está na resposta acima.')
        else:
            self.status.setText('O arquivo foi movido ou removido.')

    def submit(self):
        text = self.input.text().strip()
        if not text:
            return
        self.open_document.hide()
        self._error=''
        self.add_message('VOCÊ',text)
        self.presence.setText('● Pedido enviado')
        try:
            self.window.enqueue_command(text)
        except Exception as exc:
            self.set_reply(f'Não consegui enviar: {type(exc).__name__}: {exc}')
        else:
            self.input.clear()

    def toggle_voice(self):
        try:
            self.window.toggle_continuous_voice()
        except Exception as exc:
            self._error=f'Falha no microfone: {type(exc).__name__}: {exc}'
            self.status.setText(self._error)
            return
        self._error=''
        self.sync_voice()

    def sync_voice(self):
        active = bool(getattr(self.window, 'voice_enabled', False))
        self.mic.setText('Parar microfone' if active else 'Falar')
        label = getattr(self.window, 'voice_status', None)
        state = getattr(getattr(self.window,'neural',None),'state','READY')
        self.presence.setText('● ' + self.orb.LABELS.get(state,'Disponível'))
        self.status.setText(self._error or (('Diga “V” e seu pedido. ' if active else 'Microfone desligado · Enter envia · Esc recolhe. ') +
                            (label.text() if active and label is not None else '')))

    def showEvent(self, event):
        self.orb.chat_open=True; self.orb.update()
        self.sync_voice(); self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop(); self.appear.stop()
        self.orb.chat_open=False; self.orb.update()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
