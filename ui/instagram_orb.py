from __future__ import annotations
import math
import random
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class InstagramOrbWidget(QWidget):
    """Experimento visual inspirado na interface vista no vídeo enviado pelo usuário.

    Agora com um pequeno "mouth visor" holográfico que anima SOMENTE quando o V
    está no estado SPEAKING. O efeito é leve e combina com a interface orbital.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "READY"
        self.phase = 0.0
        self.setMinimumSize(720, 520)
        rng = random.Random(619)
        self.stars = []
        for _ in range(130):
            self.stars.append((rng.random(), rng.random(), rng.uniform(0.35, 1.0), rng.uniform(0.4, 1.6)))
        self.orbiters = []
        for _ in range(78):
            ring = rng.choice([0, 0, 1, 1, 2, 3])
            ang = rng.uniform(0, math.tau)
            radius = [0.43, 0.57, 0.72, 0.88][ring]
            wobble = rng.uniform(-0.06, 0.06)
            speed = rng.uniform(0.35, 1.2) * (-1 if rng.random() < 0.22 else 1)
            size = rng.uniform(0.7, 2.2)
            self.orbiters.append((ring, ang, radius, wobble, speed, size))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)  # ~20 FPS

    def set_state(self, state: str):
        self.state = str(state or "READY").upper()
        self.update()

    def _tick(self):
        rate = {
            "READY": 0.016,
            "LISTENING": 0.030,
            "PROCESSING": 0.055,
            "SPEAKING": 0.038,
            "ERROR": 0.020,
        }.get(self.state, 0.022)
        self.phase = (self.phase + rate) % math.tau
        self.update()

    def _cyan(self):
        if self.state == "ERROR":
            return QColor(255, 70, 95)
        if self.state == "LISTENING":
            return QColor(73, 255, 221)
        if self.state == "PROCESSING":
            return QColor(88, 168, 255)
        return QColor(53, 208, 255)

    def _draw_voice_mouth(self, p: QPainter, cx: float, cy: float, base: float, main: QColor):
        """Desenha um "visor"/boca holográfica sutil abaixo do núcleo.

        Ele pulsa quando SPEAKING, fica discreto em READY/LISTENING e praticamente
        some em PROCESSING para não poluir a leitura visual do orb.
        """
        if self.state == "PROCESSING":
            return

        mouth_y = cy + base * 0.68
        mouth_w = base * 1.02
        speaking = self.state == "SPEAKING"
        listening = self.state == "LISTENING"

        talk_wave = 0.5 + 0.5 * math.sin(self.phase * 14.0)
        mouth_h = base * (0.055 + (0.13 * talk_wave if speaking else 0.018 if listening else 0.008))
        outer = QRectF(cx - mouth_w / 2, mouth_y - mouth_h / 2, mouth_w, mouth_h)

        glow = QRadialGradient(QPointF(cx, mouth_y), mouth_w * 0.8)
        glow_alpha = 65 if speaking else 28 if listening else 14
        glow.setColorAt(0.0, QColor(main.red(), main.green(), main.blue(), glow_alpha))
        glow.setColorAt(0.55, QColor(main.red(), main.green(), main.blue(), glow_alpha // 3))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, mouth_y), mouth_w * 0.76, max(base * 0.18, mouth_h * 2.8))

        # Cápsula principal.
        p.setBrush(QColor(5, 18, 32, 165 if speaking else 140))
        p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), 180 if speaking else 110), 1.2))
        p.drawRoundedRect(outer, mouth_h / 2, mouth_h / 2)

        # Barra interna luminosa - "abre" e "fecha" durante a fala.
        inner_margin = max(2.0, base * 0.02)
        inner = outer.adjusted(inner_margin, inner_margin, -inner_margin, -inner_margin)
        if inner.height() > 2 and inner.width() > 6:
            bar = QLinearGradient(inner.left(), inner.center().y(), inner.right(), inner.center().y())
            side_alpha = 0 if speaking else 38 if listening else 28
            mid_alpha = 240 if speaking else 115 if listening else 90
            bar.setColorAt(0.0, QColor(main.red(), main.green(), main.blue(), side_alpha))
            bar.setColorAt(0.22, QColor(main.red(), main.green(), main.blue(), 145 if speaking else 72))
            bar.setColorAt(0.50, QColor(232, 250, 255, mid_alpha))
            bar.setColorAt(0.78, QColor(main.red(), main.green(), main.blue(), 145 if speaking else 72))
            bar.setColorAt(1.0, QColor(main.red(), main.green(), main.blue(), side_alpha))
            p.setPen(Qt.NoPen)
            p.setBrush(bar)
            p.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)

        # Pequenas barras internas extras durante a fala para parecer articulação.
        if speaking:
            slots = 5
            slot_gap = inner.width() / (slots + 1)
            for i in range(slots):
                sx = inner.left() + slot_gap * (i + 1)
                local = 0.35 + 0.65 * abs(math.sin(self.phase * 8.6 + i * 0.9))
                hh = max(2.0, inner.height() * local)
                rr = QRectF(sx - max(1.4, base * 0.012), mouth_y - hh / 2, max(2.8, base * 0.024), hh)
                p.setBrush(QColor(230, 250, 255, 160))
                p.drawRoundedRect(rr, rr.width() / 2, rr.width() / 2)

        # Marcas laterais discretas.
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), 110 if speaking else 72), 1.0))
        wing = base * 0.14
        p.drawLine(QPointF(outer.left() - wing, mouth_y), QPointF(outer.left() - base * 0.03, mouth_y))
        p.drawLine(QPointF(outer.right() + base * 0.03, mouth_y), QPointF(outer.right() + wing, mouth_y))

    def paintEvent(self, _):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            w, h = self.width(), self.height()

            # Deep-space navy background, like the screen shown in the reference video.
            bg = QLinearGradient(0, 0, w, h)
            bg.setColorAt(0, QColor(2, 6, 17))
            bg.setColorAt(0.46, QColor(4, 14, 36))
            bg.setColorAt(1, QColor(1, 7, 18))
            p.fillRect(self.rect(), bg)

            main = self._cyan()

            # Sparse drifting star field.
            p.setPen(Qt.NoPen)
            for idx, (sx, sy, alpha, size) in enumerate(self.stars):
                x = ((sx * w) + math.sin(self.phase * 0.21 + idx) * 4.0) % w
                y = ((sy * h) + math.cos(self.phase * 0.17 + idx * 0.37) * 3.0) % h
                tw = 0.60 + 0.40 * math.sin(self.phase * 0.8 + idx * 0.9)
                a = int(25 + 92 * alpha * max(0.15, tw))
                p.setBrush(QColor(68, 153, 255, a))
                p.drawEllipse(QPointF(x, y), size, size)

            # Core is slightly right-of-center, matching the video composition.
            cx, cy = w * 0.57, h * 0.50
            base = min(w, h) * 0.17

            # Wide atmospheric halo.
            grad = QRadialGradient(QPointF(cx, cy), base * 4.2)
            grad.setColorAt(0.0, QColor(main.red(), main.green(), main.blue(), 72))
            grad.setColorAt(0.24, QColor(20, 84, 190, 30))
            grad.setColorAt(0.56, QColor(5, 34, 92, 12))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), base * 4.2, base * 4.2)

            # Fine orbit circles/arcs.
            for j, factor in enumerate([0.72, 1.0, 1.31, 1.64, 2.05]):
                rr = base * factor
                alpha = [72, 58, 43, 31, 18][j]
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), alpha), 0.8))
                p.drawEllipse(QPointF(cx, cy), rr, rr * (0.78 if j > 1 else 0.88))

            # Broken rotating arcs around the core.
            for idx, (scale, span, a) in enumerate([(2.26, 68, 92), (1.80, 43, 78), (1.42, 84, 66)]):
                rw, rh = base * scale, base * scale * 0.78
                rect = QRectF(cx-rw, cy-rh, rw*2, rh*2)
                start = int((self.phase * (0.9 + idx*0.27) + idx*1.4) * 180/math.pi * 16)
                p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), a), 1.0 + idx*0.18))
                p.drawArc(rect, start, span * 16)
                p.drawArc(rect, start + 156*16, int(span*0.42) * 16)

            # Orbiting points.
            boost = 1.45 if self.state == "PROCESSING" else 1.15 if self.state in {"LISTENING", "SPEAKING"} else 1.0
            for idx, (ring, ang0, rad, wobble, speed, size) in enumerate(self.orbiters):
                angle = ang0 + self.phase * speed * boost
                r = base * (0.90 + rad * 1.48)
                flatten = 0.62 + 0.04 * ring
                x = cx + math.cos(angle) * r
                y = cy + math.sin(angle) * r * flatten + math.sin(angle * 2.4 + idx) * base * wobble
                pulse = 0.65 + 0.35 * math.sin(self.phase * 1.8 + idx * 0.57)
                alpha = int(70 + 150 * max(0.1, pulse))
                p.setBrush(QColor(main.red(), main.green(), main.blue(), alpha))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x, y), size * (0.8 + pulse), size * (0.8 + pulse))

            # Bright central point.
            pulse = 1.0 + (0.13 if self.state == "PROCESSING" else 0.06) * math.sin(self.phase * 3.1)
            core_r = base * 0.13 * pulse
            cg = QRadialGradient(QPointF(cx, cy), core_r * 4.0)
            cg.setColorAt(0, QColor(235, 254, 255, 255))
            cg.setColorAt(0.18, QColor(main.red(), main.green(), main.blue(), 245))
            cg.setColorAt(0.45, QColor(28, 95, 255, 95))
            cg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(cg)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), core_r * 4.0, core_r * 4.0)

            # Minimal center reticle.
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(126, 226, 255, 150), 1))
            p.drawEllipse(QPointF(cx, cy), base * 0.22, base * 0.22)
            p.drawLine(QPointF(cx-base*0.31, cy), QPointF(cx-base*0.24, cy))
            p.drawLine(QPointF(cx+base*0.24, cy), QPointF(cx+base*0.31, cy))

            # Voice mouth / visor (somente faz "lip sync" visual nesta interface).
            self._draw_voice_mouth(p, cx, cy, base, main)

            # State label below orb.
            state_text = {
                "READY": "CORE ONLINE",
                "LISTENING": "LISTENING",
                "PROCESSING": "PROCESSING",
                "SPEAKING": "RESPONDING",
                "ERROR": "SYSTEM ALERT",
            }.get(self.state, self.state)
            font = p.font()
            font.setFamily("Segoe UI")
            font.setPointSize(8)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
            p.setFont(font)
            p.setPen(QColor(main.red(), main.green(), main.blue(), 190))
            p.drawText(QRectF(cx-base*1.2, cy+base*1.16, base*2.4, 28), Qt.AlignCenter, state_text)

            # Thin frame/top scan line.
            p.setPen(QPen(QColor(31, 128, 190, 80), 1))
            p.drawLine(28, 36, w-28, 36)
            p.setPen(QPen(QColor(main.red(), main.green(), main.blue(), 160), 2))
            p.drawLine(w*0.39, 36, w*0.61, 36)
        finally:
            p.end()
