from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class MobileFaceCoreWidget(QWidget):
    """V mobile face adapted for the dedicated second interface.

    1.5 visual goals:
      * facial geometry stays stable while V speaks (no rubber/stretch effect);
      * speech animation follows a smoothed envelope from VoiceEngine;
      * the mouth becomes an energy emitter rather than a cartoon jaw;
      * denser particles orbit around the face while keeping the face readable;
      * ~60 FPS remains the target on the dedicated second display.
    """

    def __init__(self, parent=None, voice_engine=None):
        super().__init__(parent)
        self.voice_engine = voice_engine
        self.setMinimumSize(520, 420)
        self.state = "READY"
        self.phase = 0.0
        self.speech_level = 0.0

        rng = random.Random(1509)
        # Face-centric orbital particles.  Most visual density now lives around
        # the head instead of being uniformly scattered across the whole panel.
        self.orbit_particles = []
        for _ in range(172):
            self.orbit_particles.append({
                "angle": rng.uniform(0.0, math.tau),
                "radius": rng.uniform(1.18, 2.48),
                "speed": rng.uniform(-0.20, 0.20),
                "size": rng.uniform(0.65, 1.75),
                "alpha": rng.uniform(0.36, 1.0),
                "wobble": rng.uniform(0.4, 1.8),
                "seed": rng.uniform(0.0, math.tau),
            })

        # Sparse distant dust keeps depth without competing with the face.
        self.dust = [
            (rng.random(), rng.random(), rng.uniform(0.30, 0.85), rng.uniform(0.45, 1.25), rng.uniform(0, math.tau))
            for _ in range(58)
        ]

        # Speech sparks originate near the voice core and travel outward.
        self.speech_sparks = [
            (rng.uniform(0, math.tau), rng.uniform(0.25, 1.0), rng.uniform(0.6, 1.55), rng.uniform(0, 1))
            for _ in range(28)
        ]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)  # ~60 FPS, second interface only.

    def set_state(self, state: str):
        self.state = str(state or "READY").upper()
        self.update()

    def _raw_speech_level(self) -> float:
        if self.state != "SPEAKING":
            return 0.0
        engine = self.voice_engine
        if engine is not None and hasattr(engine, "get_speech_visual_level"):
            try:
                return max(0.0, min(1.0, float(engine.get_speech_visual_level())))
            except Exception:
                pass
        # Compatibility fallback for old/custom voice engines.
        return max(0.0, min(1.0, 0.42 + 0.26 * math.sin(self.phase * 5.3) + 0.18 * math.sin(self.phase * 9.1 + 1.2)))

    def _tick(self):
        target = self._raw_speech_level()
        # Faster attack, slower release: removes jitter and gives voice a
        # convincing physical response instead of frame-by-frame shaking.
        smoothing = 0.34 if target > self.speech_level else 0.15
        self.speech_level += (target - self.speech_level) * smoothing
        if self.speech_level < 0.004 and target <= 0.0:
            self.speech_level = 0.0

        speed = {
            "READY": 0.016,
            "LISTENING": 0.029,
            "PROCESSING": 0.050,
            "SPEAKING": 0.034 + 0.020 * self.speech_level,
            "ERROR": 0.021,
        }.get(self.state, 0.020)
        self.phase = (self.phase + speed) % math.tau
        self.update()

    def _accent(self) -> QColor:
        if self.state == "LISTENING":
            return QColor(255, 92, 92)
        if self.state == "PROCESSING":
            return QColor(255, 68, 78)
        if self.state == "SPEAKING":
            return QColor(255, 118, 118)
        if self.state == "ERROR":
            return QColor(255, 42, 60)
        return QColor(241, 78, 84)

    @staticmethod
    def _with_alpha(c: QColor, alpha: int) -> QColor:
        return QColor(c.red(), c.green(), c.blue(), max(0, min(255, int(alpha))))

    def _draw_eye(self, p: QPainter, cx: float, cy: float, s: float, mirror: bool, accent: QColor):
        pts = [
            QPointF(-1.00 * s, -0.18 * s), QPointF(-0.15 * s, -0.52 * s),
            QPointF(0.96 * s, -0.04 * s), QPointF(0.72 * s, 0.38 * s),
            QPointF(-0.58 * s, 0.24 * s),
        ]
        if mirror:
            pts = [QPointF(-q.x(), q.y()) for q in pts]
        poly = QPolygonF([QPointF(cx + q.x(), cy + q.y()) for q in pts])

        glow_alpha = 58 + int(24 * self.speech_level)
        p.setPen(QPen(self._with_alpha(accent, glow_alpha), max(4.0, s * 0.18)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(poly)
        p.setPen(Qt.NoPen)
        p.setBrush(self._with_alpha(accent, 235))
        p.drawPolygon(poly)

        inner = QPolygonF([
            QPointF(cx + (-0.38 * s if not mirror else 0.38 * s), cy - 0.10 * s),
            QPointF(cx + (0.25 * s if not mirror else -0.25 * s), cy - 0.23 * s),
            QPointF(cx + (0.45 * s if not mirror else -0.45 * s), cy + 0.03 * s),
            QPointF(cx + (-0.12 * s if not mirror else 0.12 * s), cy + 0.09 * s),
        ])
        eye_alpha = 205 + int(35 * self.speech_level)
        p.setBrush(QColor(255, 235, 235, min(245, eye_alpha)))
        p.drawPolygon(inner)

    def _draw_jaw(self, p: QPainter, cx: float, cy: float, s: float, accent: QColor):
        # The jaw is intentionally fixed.  Speech no longer scales or stretches
        # the face; voice energy is rendered inside/around it instead.
        pts = [
            QPointF(cx - 1.18 * s, cy - 0.60 * s), QPointF(cx - 0.72 * s, cy - 0.10 * s),
            QPointF(cx - 0.42 * s, cy + 0.72 * s), QPointF(cx, cy + 1.00 * s),
            QPointF(cx + 0.42 * s, cy + 0.72 * s), QPointF(cx + 0.72 * s, cy - 0.10 * s),
            QPointF(cx + 1.18 * s, cy - 0.60 * s), QPointF(cx + 0.84 * s, cy + 1.18 * s),
            QPointF(cx - 0.84 * s, cy + 1.18 * s),
        ]
        poly = QPolygonF(pts)
        p.setPen(QPen(self._with_alpha(accent, 48 + int(22 * self.speech_level)), max(5.0, s * 0.16)))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(poly)
        p.setPen(Qt.NoPen)
        p.setBrush(self._with_alpha(accent, 218))
        p.drawPolygon(poly)

    def _draw_voice_core(self, p: QPainter, cx: float, cy: float, base: float, accent: QColor):
        """Energy aperture that reacts to speech without distorting the face."""
        level = self.speech_level
        mouth_y = cy + base * 0.54
        width = base * 0.43

        # Soft emitter glow.
        core_r = base * (0.105 + 0.040 * level)
        g = QRadialGradient(QPointF(cx, mouth_y), core_r * 3.8)
        g.setColorAt(0.0, QColor(255, 248, 248, int(90 + 145 * level)))
        g.setColorAt(0.20, self._with_alpha(accent, int(72 + 118 * level)))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, mouth_y), core_r * 3.8, core_r * 2.35)

        # Angular aperture.  Only the energy gap changes; facial geometry does not.
        gap = base * (0.018 + 0.050 * level)
        upper = QPainterPath()
        upper.moveTo(cx - width, mouth_y - gap)
        upper.cubicTo(cx - width * 0.44, mouth_y - base * 0.08 - gap,
                      cx + width * 0.44, mouth_y - base * 0.08 - gap,
                      cx + width, mouth_y - gap)
        lower = QPainterPath()
        lower.moveTo(cx - width * 0.88, mouth_y + gap)
        lower.cubicTo(cx - width * 0.38, mouth_y + base * 0.07 + gap,
                      cx + width * 0.38, mouth_y + base * 0.07 + gap,
                      cx + width * 0.88, mouth_y + gap)

        line_alpha = 78 if self.state != "SPEAKING" else int(125 + 110 * level)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(self._with_alpha(accent, line_alpha), 1.2 + 1.5 * level))
        p.drawPath(upper)
        p.drawPath(lower)

        # Seven short energy channels. Their individual amplitudes vary to avoid
        # the old synchronized bar/stretch effect.
        if self.state == "SPEAKING" or level > 0.02:
            for i in range(7):
                xoff = (i - 3) * base * 0.075
                local = max(0.08, level * (0.58 + 0.42 * math.sin(self.phase * (5.2 + i * 0.17) + i * 1.31) ** 2))
                hh = base * (0.018 + 0.105 * local)
                alpha = int(80 + 160 * local)
                p.setPen(QPen(QColor(255, 238, 238, min(245, alpha)), 1.1 + local))
                p.drawLine(QPointF(cx + xoff, mouth_y - hh), QPointF(cx + xoff, mouth_y + hh))

        # Small lateral pulses make voice feel emitted rather than stretched.
        if level > 0.03:
            for side in (-1, 1):
                for n in range(2):
                    offset = base * (0.50 + n * 0.13 + level * 0.05)
                    length = base * (0.09 + level * 0.10)
                    yoff = (n - 0.5) * base * 0.055
                    start_x = cx + side * offset
                    end_x = start_x + side * length
                    p.setPen(QPen(self._with_alpha(accent, int((72 - n * 18) * level + 18)), 1.0))
                    p.drawLine(QPointF(start_x, mouth_y + yoff), QPointF(end_x, mouth_y + yoff))

    def _draw_particles(self, p: QPainter, w: int, h: int, cx: float, cy: float, base: float, accent: QColor):
        level = self.speech_level
        if self.state == "PROCESSING":
            state_boost = 1.28
        elif self.state == "LISTENING":
            state_boost = 1.12
        elif self.state == "SPEAKING":
            state_boost = 1.08 + 0.42 * level
        else:
            state_boost = 1.0

        # Distant dust first.
        p.setPen(Qt.NoPen)
        for i, (px, py, a0, size, seed) in enumerate(self.dust):
            x = (px * w + math.sin(self.phase * 0.37 + seed) * 7.0) % w
            y = (py * h + math.cos(self.phase * 0.29 + seed * 1.3) * 5.0) % h
            tw = 0.55 + 0.45 * math.sin(self.phase * 1.25 + seed + i * 0.08)
            alpha = int((8 + 38 * a0 * max(0.10, tw)) * state_boost)
            p.setBrush(self._with_alpha(accent, alpha))
            p.drawEllipse(QPointF(x, y), size, size)

        # Face-centric orbital field.
        for i, part in enumerate(self.orbit_particles):
            ang = part["angle"] + self.phase * part["speed"]
            wob = math.sin(self.phase * part["wobble"] + part["seed"])
            radius = base * part["radius"] * (1.0 + 0.035 * wob)
            # During speech a subtle outward wave travels across the field.
            if self.state == "SPEAKING":
                radius *= 1.0 + level * 0.035 * (0.5 + 0.5 * math.sin(ang * 3.0 + self.phase * 5.0))
            x = cx + math.cos(ang) * radius
            y = cy + math.sin(ang) * radius * 0.73 + base * 0.06

            # Preserve a clean mask immediately around eyes and jaw.
            nx = (x - cx) / max(1.0, base)
            ny = (y - cy) / max(1.0, base)
            if (nx * nx) / (1.08 * 1.08) + (ny * ny) / (1.10 * 1.10) < 1.0:
                continue

            tw = 0.48 + 0.52 * math.sin(self.phase * (1.6 + abs(part["speed"]) * 3.0) + part["seed"])
            alpha = int((18 + 112 * part["alpha"] * max(0.06, tw)) * state_boost)
            size = part["size"] * (1.0 + 0.30 * level)
            if i % 4 == 0:
                p.setBrush(self._with_alpha(accent, int(alpha * 0.22)))
                p.drawEllipse(QPointF(x, y), size * 3.1, size * 3.1)
            p.setBrush(self._with_alpha(accent, min(225, alpha)))
            p.drawEllipse(QPointF(x, y), size, size)

        # Short-lived voice sparks emerging from the core.
        if level > 0.04:
            mouth_y = cy + base * 0.54
            for i, (ang0, speed, size, offset) in enumerate(self.speech_sparks):
                progress = (offset + self.phase * speed * 0.42) % 1.0
                ang = ang0 + math.sin(self.phase * 1.7 + i) * 0.10
                dist = base * (0.22 + progress * 1.75)
                x = cx + math.cos(ang) * dist
                y = mouth_y + math.sin(ang) * dist * 0.62
                fade = (1.0 - progress) * level
                p.setBrush(QColor(255, 210, 210, int(150 * fade)))
                p.drawEllipse(QPointF(x, y), size * (0.7 + level), size * (0.7 + level))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(3, 5, 10))
        bg.setColorAt(0.55, QColor(7, 8, 13))
        bg.setColorAt(1, QColor(2, 3, 7))
        p.fillRect(self.rect(), bg)

        accent = self._accent()
        cx, cy = w * 0.52, h * 0.47
        base = min(w, h) * 0.20
        level = self.speech_level

        # Atmospheric halo reacts to voice energy, but the face itself stays stable.
        state_pulse = 0.0
        if self.state == "PROCESSING":
            state_pulse = 0.06 * (0.5 + 0.5 * math.sin(self.phase * 3.0))
        elif self.state == "SPEAKING":
            state_pulse = 0.10 * level
        halo_r = base * (2.35 + state_pulse)
        g = QRadialGradient(QPointF(cx, cy), halo_r)
        g.setColorAt(0, self._with_alpha(accent, 48 + int(55 * level)))
        g.setColorAt(0.34, QColor(110, 12, 20, 25 + int(18 * level)))
        g.setColorAt(0.72, QColor(40, 4, 8, 8))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        self._draw_particles(p, w, h, cx, cy, base, accent)

        # Thin energy rings behind face. Speaking adds a fourth breathing ring.
        p.setBrush(Qt.NoBrush)
        ring_factors = [1.02, 1.42, 1.86]
        if self.state == "SPEAKING" and level > 0.03:
            ring_factors.append(2.12 + 0.08 * level)
        for j, factor in enumerate(ring_factors):
            base_alpha = (48, 28, 15, 22)[min(j, 3)]
            alpha = base_alpha + (int(42 * level) if self.state == "SPEAKING" and j in (0, 3) else 0)
            p.setPen(QPen(self._with_alpha(accent, alpha), 0.9 + (0.35 * level if j == 0 else 0.0)))
            r = base * factor
            p.drawEllipse(QPointF(cx, cy + base * 0.05), r, r * 0.78)

        eye_y = cy - base * 0.33
        eye_dx = base * 0.57
        eye_s = base * 0.30
        self._draw_eye(p, cx - eye_dx, eye_y, eye_s, False, accent)
        self._draw_eye(p, cx + eye_dx, eye_y, eye_s, True, accent)
        self._draw_jaw(p, cx, cy + base * 0.40, base * 0.43, accent)
        self._draw_voice_core(p, cx, cy, base, accent)

        # Processor pulse remains independent from mouth animation.
        proc_base = 0.0
        if self.state == "PROCESSING":
            proc_base = 0.5 + 0.5 * math.sin(self.phase * 5.0)
        proc_alpha = 70 + int(85 * proc_base) + int(35 * level)
        proc_r = base * (0.105 + 0.020 * proc_base + 0.010 * level)
        proc_y = cy + base * 0.26
        cg = QRadialGradient(QPointF(cx, proc_y), proc_r * 3.2)
        cg.setColorAt(0, QColor(255, 245, 245, 205))
        cg.setColorAt(0.24, self._with_alpha(accent, proc_alpha))
        cg.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(cg)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, proc_y), proc_r * 3.2, proc_r * 3.2)

        # Understated frame accents.
        p.setPen(QPen(self._with_alpha(accent, 55), 1))
        p.drawLine(28, 36, w - 28, 36)
        p.setPen(QPen(self._with_alpha(accent, 145 + int(45 * level)), 2))
        p.drawLine(w * 0.42, 36, w * 0.62, 36)
        p.end()
