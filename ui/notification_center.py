from datetime import datetime
from PySide6.QtCore import Qt, QRect, QTimer, Signal, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QFrame, QGraphicsOpacityEffect)


class NotificationToast(QFrame):
    """Aviso curto que entra pela lateral, sem janela modal nem blur pesado."""
    closed = Signal(object)

    def __init__(self, parent, label, text, red=False):
        super().__init__(parent)
        self.setObjectName('vToast')
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedWidth(366)
        self.setMinimumHeight(82)
        self.setStyleSheet((
            "QFrame#vToast { background:rgba(42,5,15,248); border:1px solid #e2445b; border-radius:10px; }"
            "QLabel#toastKicker { color:#ff7180; font-size:9px; font-weight:700; letter-spacing:1.4px; }"
            "QLabel#toastText { color:#ffe4e7; font-size:12px; }"
            if red else
            "QFrame#vToast { background:rgba(5,25,44,248); border:1px solid #3298cc; border-radius:10px; }"
            "QLabel#toastKicker { color:#63d9ff; font-size:9px; font-weight:700; letter-spacing:1.4px; }"
            "QLabel#toastText { color:#d9f5ff; font-size:12px; }"
        ))
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(4)
        kicker = QLabel(label); kicker.setObjectName('toastKicker'); layout.addWidget(kicker)
        body = QLabel(text); body.setObjectName('toastText'); body.setWordWrap(True); layout.addWidget(body)
        self._opacity = QGraphicsOpacityEffect(self); self.setGraphicsEffect(self._opacity)
        self._animation = None
        self._dismiss_timer = QTimer(self); self._dismiss_timer.setSingleShot(True); self._dismiss_timer.timeout.connect(self.dismiss)

    def reveal(self, target):
        start = QRect(target.x() + 42, target.y(), target.width(), target.height())
        self.setGeometry(start); self._opacity.setOpacity(0.0); self.show(); self.raise_()
        slide = QPropertyAnimation(self, b'geometry', self); slide.setDuration(300)
        slide.setStartValue(start); slide.setEndValue(target); slide.setEasingCurve(QEasingCurve.OutCubic)
        fade = QPropertyAnimation(self._opacity, b'opacity', self); fade.setDuration(240); fade.setStartValue(0.0); fade.setEndValue(1.0)
        group = QParallelAnimationGroup(self); group.addAnimation(slide); group.addAnimation(fade); group.start()
        self._animation = group
        self._dismiss_timer.start(7000)

    def dismiss(self):
        if not self.isVisible():
            return
        self._dismiss_timer.stop()
        fade = QPropertyAnimation(self._opacity, b'opacity', self); fade.setDuration(180); fade.setStartValue(self._opacity.opacity()); fade.setEndValue(0.0)
        fade.finished.connect(lambda: self.closed.emit(self))
        self._animation = fade; fade.start()


class NotificationCenter(QDialog):
    """Small non-modal inbox for initiative events visible in the conversation UI."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.unread = 0
        self.setWindowTitle('V / Notificações')
        self.resize(620, 430)
        red = str(getattr(window, 'visual_theme', 'blue') or 'blue').lower() == 'red'
        if red:
            self.setStyleSheet("""
                QDialog { background:#19040b; color:#ffe4e7; }
                QLabel#section { color:#ff7885; font-weight:700; letter-spacing:1px; }
                QListWidget { background:#260610; color:#ffe4e7; border:1px solid #762136; border-radius:8px; padding:5px; }
                QPushButton { background:#4c0b1c; color:#ffd9dd; border:1px solid #a82f47; border-radius:6px; padding:7px 12px; }
                QPushButton:hover { background:#71152b; border-color:#ff7b86; }
            """)
        layout = QVBoxLayout(self)
        self.heading = QLabel('NOTIFICAÇÕES DO V')
        self.heading.setObjectName('section'); layout.addWidget(self.heading)
        self.list = QListWidget(); self.list.setWordWrap(True); layout.addWidget(self.list)
        row = QHBoxLayout(); layout.addLayout(row)
        self.clear_button = QPushButton('Marcar como lidas'); self.clear_button.clicked.connect(self.mark_read); row.addWidget(self.clear_button)
        close = QPushButton('Fechar'); close.clicked.connect(self.hide); row.addWidget(close)

    def add_notice(self, kind, text, show_center=True):
        label = {'gmail': 'GMAIL', 'messages': 'MENSAGENS', 'alarms': 'ALARME'}.get(kind, 'V')
        stamp = datetime.now().astimezone().strftime('%d/%m %H:%M')
        self.list.insertItem(0, f'[{stamp}] {label}\n{text}')
        self.unread += 1
        self.heading.setText(f'NOTIFICAÇÕES DO V  •  {self.unread} nova(s)')
        if show_center:
            self.show(); self.raise_()

    def mark_read(self):
        self.unread = 0
        self.heading.setText('NOTIFICAÇÕES DO V')

    def closeEvent(self, event):
        # Closing the tab does not discard its entries.
        event.accept()
