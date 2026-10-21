"""Small, independent presence indicator; no voice or AI services of its own."""
import math
import random
import time
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRegion
from PySide6.QtWidgets import QApplication, QWidget


class FloatingOrb(QWidget):
    activated = Signal()
    menuRequested = Signal(QPoint)
    positionChanged = Signal()
    COLORS = {'READY': '#f04b70', 'LISTENING': '#ff8da5', 'PROCESSING': '#ffb36e',
              'SPEAKING': '#ff527d', 'ERROR': '#ff303f'}
    LABELS = {'READY': 'Ativo', 'LISTENING': 'Ouvindo', 'PROCESSING': 'Processando',
              'SPEAKING': 'Falando', 'ERROR': 'Atenção'}

    def __init__(self, state_provider):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle('V — avatar')
        self.setFixedSize(104, 118)
        self.setMask(QRegion(4, 4, 96, 110, QRegion.Rectangle))
        self.setAccessibleName("Avatar do V. Clique para conversar; arraste para mover.")
        self.setCursor(Qt.PointingHandCursor)
        self.state_provider = state_provider
        self.state = 'READY'
        self.chat_open = False
        self.mic_active = False
        self.phase = 0.0
        self._pleased_until = 0.0
        self._hovered = False
        self._placed = False
        self._press = None
        self._dragging = False
        self.timer = QTimer(self)
        self.timer.setInterval(500)  # Only this tiny surface animates while V is hidden.
        self.timer.timeout.connect(self._tick)
        self._greeting_progress = 0.0
        self._greeting_kind = 0
        self.greeting = QVariantAnimation(self)
        self.greeting.setDuration(650)
        self.greeting.setStartValue(0.0)
        self.greeting.setEndValue(1.0)
        self.greeting.valueChanged.connect(self._greeting_frame)

    def _greeting_frame(self, value):
        self._greeting_progress = float(value)
        self.update()

    def play_greeting(self):
        self.greeting.stop()
        self._greeting_kind = random.choice([i for i in range(4) if i != self._greeting_kind])
        self.greeting.start()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.positionChanged.emit()

    def _tick(self):
        state, mic = self.state_provider()
        previous = self.state
        was_pleased = self._pleased_until > 0
        mic_changed = self.mic_active != bool(mic)
        self.mic_active = bool(mic)
        self.state = state if state in self.COLORS else 'READY'
        if previous in {'PROCESSING', 'SPEAKING'} and self.state == 'READY':
            self._pleased_until = time.monotonic() + 2.0
        elif self.state != 'READY' or time.monotonic() >= self._pleased_until:
            self._pleased_until = 0.0
        self.timer.setInterval(500 if self.state in {'READY', 'ERROR'} else 100)
        self.phase = (self.phase + .16) % math.tau
        self.setToolTip(f"V • {self.LABELS[self.state]} • Microfone {'ativo' if mic else 'desligado'}\nClique para conversar · Arraste para mover · Botão direito para abrir o V")
        if mic_changed or previous != self.state or was_pleased or self.state not in {'READY', 'ERROR'}:
            self.update()

    def present(self, preferred_screen=None):
        if not self._placed:
            screen = preferred_screen or QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                self.move(area.right() - self.width() - 20, area.bottom() - self.height() - 20)
            self._placed = True
        self.keep_on_screen()
        if not self.isVisible():
            self.show()

    def keep_on_screen(self):
        center = self.geometry().center()
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(max(area.left(), min(self.x(), area.right() - self.width() + 1)),
                  max(area.top(), min(self.y(), area.bottom() - self.height() + 1)))

    def showEvent(self, event):
        self._tick()
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        self.greeting.stop()
        self._greeting_progress = 0.0
        self._pleased_until = 0.0
        self._press = None
        self._dragging = False
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._origin = self.pos()
            self._dragging = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self._press
            self._dragging = self._dragging or delta.manhattanLength() >= QApplication.startDragDistance()
            if self._dragging:
                self.move(self._origin + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press is not None:
            dragged = self._dragging
            self._press = None
            self._dragging = False
            self.keep_on_screen()
            if not dragged:
                self.activated.emit()
            event.accept()

    def contextMenuEvent(self, event):
        self.menuRequested.emit(event.globalPos())
        event.accept()

    def paintEvent(self, event):
        from .game_mascot_art import mascot_frame
        t=self._greeting_progress
        amount=round(4*math.sin(t*math.pi)) if 0<t<1 else 0
        frame=mascot_frame(self.state,int(self.phase*6)%3,self._greeting_kind,amount,
                          self._pleased_until>time.monotonic(),self._hovered)
        p=QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform,False)
        p.drawImage(QRectF(0,0,104,104),frame)
        # Small status plate; the character itself has a transparent backdrop.
        p.setRenderHint(QPainter.Antialiasing,True)
        p.setPen(QPen(QColor('#a95870' if self.chat_open else '#593747'),.7))
        p.setBrush(QColor(20,17,26,235))
        p.drawRoundedRect(QRectF(8,100,88,15),5,5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#f9b6a6' if self.mic_active else '#745669'))
        p.drawEllipse(QPointF(16,107.5),2,2)
        p.setFont(QFont('Segoe UI',8));p.setPen(QColor('#f1c9cb'))
        p.drawText(QRectF(21,100,70,15),Qt.AlignCenter,self.LABELS[self.state])
        p.end()
