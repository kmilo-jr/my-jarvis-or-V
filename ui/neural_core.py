from __future__ import annotations
import math
import random
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget
from .animation_clock import AnimationClock


class NeuralCoreWidget(QWidget):
    """Núcleo visual leve do V.

    Continua usando apenas QPainter, com movimento baseado no tempo, e reage aos
    estados READY / LISTENING / PROCESSING / SPEAKING / ERROR.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(430, 430)
        self.phase = 0.0
        self._clock = AnimationClock()
        self.state = "READY"
        rng = random.Random(42)
        self.nodes = [(rng.uniform(-1, 1), rng.uniform(-0.72, 0.72), rng.uniform(0.5, 1.0)) for _ in range(58)]
        self._network_key = None
        self._network_points = []
        self._network_edges = []
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(33)

    def showEvent(self, event):
        self._clock.reset()
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def set_state(self, state: str):
        self.state = str(state or "READY").upper()
        self.update()

    def _tick(self):
        speed = {
            "READY": 0.035,
            "LISTENING": 0.060,
            "PROCESSING": 0.105,
            "SPEAKING": 0.075,
            "ERROR": 0.040,
        }.get(self.state, 0.045)
        self.phase = (self.phase + speed * self._clock.step() / .083) % (math.pi * 2)
        self.update()

    def _palette(self):
        if self.state == "PROCESSING":
            return QColor(88, 167, 255), QColor(40, 113, 255)
        if self.state == "LISTENING":
            return QColor(72, 255, 213), QColor(20, 168, 156)
        if self.state == "SPEAKING":
            return QColor(117, 231, 255), QColor(35, 185, 236)
        if self.state == "ERROR":
            return QColor(255, 95, 95), QColor(204, 48, 76)
        return QColor(55, 224, 255), QColor(0, 118, 178)

    def _network(self, w, h):
        # Node positions and their nearest neighbors do not move with phase.
        # Rebuild only on resize, preserving the original sorting/drawing order.
        if self._network_key != (w, h):
            cx, cy, r = w/2, h/2, min(w, h)*.34
            pts = [QPointF(cx+x*r*.92, cy+y*r*.92) for x, y, _ in self.nodes]
            edges = []
            for i, a in enumerate(pts):
                distances = [((a.x()-b.x())**2 + (a.y()-b.y())**2, j)
                             for j, b in enumerate(pts) if i != j]
                edges.extend((i, j, d) for d, j in sorted(distances)[:3] if j >= i)
            self._network_key = (w, h)
            self._network_points, self._network_edges = pts, edges
        return self._network_points, self._network_edges

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.34
        main, accent = self._palette()

        # halo central; PROCESSING ganha uma pulsação mais forte.
        halo_boost = 1.0
        if self.state == "PROCESSING":
            halo_boost = 1.12 + 0.08 * math.sin(self.phase * 2)
        elif self.state == "SPEAKING":
            halo_boost = 1.06 + 0.04 * math.sin(self.phase * 3)
        grad = QRadialGradient(QPointF(cx, cy), r * 1.62 * halo_boost)
        grad.setColorAt(0, QColor(main.red(), main.green(), main.blue(), 54))
        grad.setColorAt(0.52, QColor(accent.red(), accent.green(), accent.blue(), 24))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 1.58 * halo_boost, r * 1.58 * halo_boost)

        # Anéis HUD completos.
        for i, alpha in [(0, 115), (1, 62), (2, 38)]:
            rr = r * (1.02 + i * 0.16) + math.sin(self.phase + i) * (3 if self.state == "PROCESSING" else 2)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), alpha), 1))
            p.drawEllipse(QPointF(cx, cy), rr, rr)

        # Arcos rotativos dão sensação de cálculo sem usar 3D/shaders.
        if self.state in {"PROCESSING", "LISTENING", "SPEAKING"}:
            rect1 = QRectF(cx-r*1.31, cy-r*1.31, r*2.62, r*2.62)
            rect2 = QRectF(cx-r*1.48, cy-r*1.48, r*2.96, r*2.96)
            angle = int((self.phase / (math.pi * 2)) * 360 * 16)
            p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), 175), 2))
            p.drawArc(rect1, angle, 92 * 16)
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 115), 1.4))
            p.drawArc(rect2, -angle - 65 * 16, 58 * 16)

        pts, edges = self._network(w, h)
        for i, j, d in edges:
            alpha = max(18, min(95, int(98 - math.sqrt(d) * 0.30)))
            if self.state == "PROCESSING":
                alpha = min(125, alpha + 22)
            p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), alpha), 0.8))
            p.drawLine(pts[i], pts[j])

        boost = {"READY": 1.0, "PROCESSING": 1.75, "LISTENING": 1.5, "SPEAKING": 1.58, "ERROR": 1.2}.get(self.state, 1.2)
        for idx, (pt, (_, _, z)) in enumerate(zip(pts, self.nodes)):
            pulse = 1.35 + z * 2.25 + (math.sin(self.phase * 2 + idx * 0.6) + 1) * 0.72 * boost
            color = QColor(main.red(), main.green(), main.blue(), 225)
            p.setBrush(color)
            p.setPen(Qt.NoPen)
            p.drawEllipse(pt, pulse, pulse)

        # centro
        core_r = 23 + (5 if self.state == "PROCESSING" else 2) * (0.5 + 0.5 * math.sin(self.phase * 2))
        core_grad = QRadialGradient(QPointF(cx, cy), core_r * 1.9)
        core_grad.setColorAt(0, QColor(215, 250, 255, 235))
        core_grad.setColorAt(0.22, QColor(main.red(), main.green(), main.blue(), 210))
        core_grad.setColorAt(1, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(core_grad)
        p.drawEllipse(QPointF(cx, cy), core_r * 1.9, core_r * 1.9)

        p.setPen(QPen(QColor(215, 250, 255), 1))
        font = p.font(); font.setPointSize(18); font.setBold(True); p.setFont(font)
        p.drawText(0, int(cy - 8), w, 30, Qt.AlignCenter, "V")
        font.setPointSize(9); font.setBold(False); p.setFont(font)
        p.setPen(QColor(main.red(), main.green(), main.blue(), 205))
        state_text = {
            "READY": "ONLINE",
            "LISTENING": "OUVINDO",
            "PROCESSING": "PROCESSANDO",
            "SPEAKING": "FALANDO",
            "ERROR": "ERRO",
        }.get(self.state, self.state)
        p.drawText(0, int(cy + 26), w, 22, Qt.AlignCenter, state_text)
