from __future__ import annotations
import math
import random
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget
from .face_reference_geometry import FACE_POINTS, FACE_EDGES


class AmberNeural2DWidget(QWidget):
    """MODE 1 / 2D: flat direct-reference face with a more neural texture."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "READY"
        self.phase = 0.0
        self.setMinimumSize(720, 520)
        self.setObjectName('vFace2D')
        rng = random.Random(1709)
        self.ambient = [
            (rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(0.3, 1.0), rng.uniform(0.0, math.tau))
            for _ in range(110)
        ]
        # Internal neural-texture links: only subtle decoration over the existing shape.
        candidates = [i for i, (_x, _y, tag) in enumerate(FACE_POINTS) if tag in {'head', 'spine', 'cheek', 'chin', 'mouth'}]
        self.neural_links = []
        for _ in range(54):
            a = rng.choice(candidates)
            b = rng.choice(candidates)
            if a == b:
                continue
            ax, ay, _ = FACE_POINTS[a]
            bx, by, _ = FACE_POINTS[b]
            d = math.hypot(ax - bx, ay - by)
            if 0.10 <= d <= 0.55:
                self.neural_links.append((a, b, rng.uniform(-1.0, 1.0), rng.uniform(0.28, 1.0), rng.uniform(0.0, math.tau)))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(42)

    def set_state(self, state: str):
        self.state = str(state or "READY").upper()
        self.update()

    def _tick(self):
        rate = {
            "READY": 0.018,
            "LISTENING": 0.030,
            "PROCESSING": 0.062,
            "SPEAKING": 0.036,
            "ERROR": 0.028,
        }.get(self.state, 0.022)
        self.phase = (self.phase + rate) % math.tau
        self.update()

    def _accent(self):
        if self.state == "ERROR":
            return QColor(255, 72, 54)
        if self.state == "LISTENING":
            return QColor(255, 191, 72)
        if self.state == "PROCESSING":
            return QColor(255, 108, 62)
        if self.state == "SPEAKING":
            return QColor(255, 132, 60)
        return QColor(255, 88, 62)

    def _draw_background(self, p: QPainter, w: int, h: int, accent: QColor):
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0, QColor(2, 4, 10))
        bg.setColorAt(0.5, QColor(5, 8, 18))
        bg.setColorAt(1, QColor(2, 3, 8))
        p.fillRect(self.rect(), bg)

        halo = QRadialGradient(QPointF(w * 0.5, h * 0.47), min(w, h) * 0.40)
        halo.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 22))
        halo.setColorAt(0.55, QColor(accent.red(), accent.green(), accent.blue(), 8))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(w * 0.5, h * 0.48), min(w, h) * 0.40, min(w, h) * 0.40)

        density = 1.15 if self.state == "PROCESSING" else 0.72 if self.state in {"LISTENING", "SPEAKING"} else 0.48
        for _i, (ux, uy, wt, drift) in enumerate(self.ambient):
            ang = self.phase * (1.2 + 0.8 * wt) + drift
            x = w * 0.5 + (ux * 0.42 + math.cos(ang) * 0.028 * density) * min(w, h) * 0.32
            y = h * 0.50 + (uy * 0.34 + math.sin(self.phase * 1.1 + drift) * 0.028 * density) * min(w, h) * 0.32
            a = int((10 + 44 * wt) * (1.0 if self.state == "PROCESSING" else 0.58))
            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), min(126, a)))
            p.drawEllipse(QPointF(x, y), 0.55 + wt * 0.95, 0.55 + wt * 0.95)

    def _draw_neural_texture(self, p: QPainter, coords, cx, cy, scale, accent: QColor):
        for idx, (a, b, bend, strength, seed) in enumerate(self.neural_links):
            x1, y1, _ = coords[a]
            x2, y2, _ = coords[b]
            mx, my = (x1 + x2) * 0.5, (y1 + y2) * 0.5
            dx, dy = (x2 - x1), (y2 - y1)
            dist = max(1e-6, math.hypot(dx, dy))
            nx, ny = -dy / dist, dx / dist
            control_shift = scale * 0.035 * bend * (0.6 + 0.4 * math.sin(self.phase * 2.3 + seed))
            cx1, cy1 = mx + nx * control_shift, my + ny * control_shift
            path = QPainterPath(QPointF(x1, y1))
            path.quadTo(QPointF(cx1, cy1), QPointF(x2, y2))
            flow = 0.45 + 0.55 * math.sin(self.phase * (2.1 + 0.25 * strength) + seed)
            alpha = int((16 + 34 * strength) * flow)
            width = 0.35 + 0.45 * strength
            if self.state == 'PROCESSING':
                alpha = int(alpha * 1.35)
                width += 0.08
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), min(96, alpha)), width))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

            # Traveling pulse along the neural strand.
            t = (math.sin(self.phase * (2.8 + 0.18 * strength) + seed) * 0.5 + 0.5)
            qx = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * cx1 + t * t * x2
            qy = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * cy1 + t * t * y2
            pulse_alpha = 40 + int(85 * strength * (0.55 + 0.45 * math.sin(self.phase * 4.0 + seed)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 228, 210, min(180, pulse_alpha)))
            p.drawEllipse(QPointF(qx, qy), 0.75 + 0.8 * strength, 0.75 + 0.8 * strength)

        # Faint vertical neural currents inside the mask area.
        p.setPen(Qt.NoPen)
        for col in range(7):
            xx = cx + (col - 3) * scale * 0.10
            yy = cy - scale * 0.62
            hh = scale * 1.18
            grad = QLinearGradient(xx, yy, xx, yy + hh)
            pulse = 0.42 + 0.58 * math.sin(self.phase * 1.8 + col * 0.7)
            grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            grad.setColorAt(0.35, QColor(accent.red(), accent.green(), accent.blue(), int(12 * pulse)))
            grad.setColorAt(0.5, QColor(255, 212, 200, int(14 * pulse)))
            grad.setColorAt(0.68, QColor(accent.red(), accent.green(), accent.blue(), int(10 * pulse)))
            grad.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            p.setBrush(grad)
            p.drawRoundedRect(QRectF(xx - scale * 0.012, yy, scale * 0.024, hh), scale * 0.01, scale * 0.01)

    def _draw_face(self, p: QPainter, w: int, h: int, accent: QColor):
        cx, cy = w * 0.5, h * 0.50
        scale = min(w, h) * 0.33

        jitter = {
            "READY": 0.12,
            "LISTENING": 0.18,
            "PROCESSING": 0.48,
            "SPEAKING": 0.22,
            "ERROR": 0.30,
        }.get(self.state, 0.14)

        coords = []
        for i, (fx, fy, tag) in enumerate(FACE_POINTS):
            amp = jitter * (1.35 if tag == 'mesh' and self.state == 'PROCESSING' else 1.0)
            if tag in {'head', 'brow', 'spine', 'cheek', 'chin'}:
                amp *= 0.75
            jx = math.sin(self.phase * 1.55 + i * 0.21) * amp
            jy = math.cos(self.phase * 1.25 + i * 0.17) * amp

            if self.state == 'PROCESSING':
                burst = scale * 0.012
                if tag == 'mesh':
                    jx += fx * burst * (0.55 + 0.45 * math.sin(self.phase * 3.7 + i * 0.11))
                    jy += fy * burst * (0.55 + 0.45 * math.cos(self.phase * 3.0 + i * 0.09))
                elif tag in {'cheek', 'chin', 'mouth'}:
                    jx += fx * burst * 0.35 * (0.6 + 0.4 * math.sin(self.phase * 2.9 + i * 0.08))
                    jy += fy * burst * 0.30 * (0.6 + 0.4 * math.cos(self.phase * 2.6 + i * 0.07))

            x = cx + fx * scale + jx
            y = cy + fy * scale + jy
            coords.append((x, y, tag))

        self._draw_neural_texture(p, coords, cx, cy, scale, accent)

        p.setBrush(Qt.NoBrush)
        for idx, (a, b) in enumerate(FACE_EDGES):
            x1, y1, t1 = coords[a]
            x2, y2, t2 = coords[b]
            if t1 == 'mesh' and t2 == 'mesh' and self.state == 'READY':
                continue
            base = 34 if self.state not in {'LISTENING', 'PROCESSING'} else 46 if self.state == 'LISTENING' else 68
            flow = 0.52 + 0.48 * math.sin(self.phase * 4.2 + idx * 0.045 + (y1 + y2) * 0.02)
            alpha = int(base * flow)
            width = 0.40 if t1 == 'mesh' and t2 == 'mesh' else 0.50
            if self.state == 'PROCESSING' and (t1 in {'mouth', 'cheek', 'chin'} or t2 in {'mouth', 'cheek', 'chin'}):
                width = 0.58
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), alpha), width))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        scan_y = cy - scale * 0.85 + ((math.sin(self.phase * 0.62) * 0.5 + 0.5) * scale * 1.75)
        scan = QLinearGradient(0, scan_y - scale * 0.10, 0, scan_y + scale * 0.10)
        scan.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        scan.setColorAt(0.5, QColor(accent.red(), accent.green(), accent.blue(), 28 if self.state != 'PROCESSING' else 44))
        scan.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(scan)
        p.drawRect(QRectF(cx - scale * 0.48, scan_y - scale * 0.10, scale * 0.96, scale * 0.20))

        eye_glow = 0.82 + 0.18 * math.sin(self.phase * (2.6 if self.state == 'LISTENING' else 2.05))
        if self.state == 'PROCESSING':
            eye_glow = 0.94 + 0.06 * math.sin(self.phase * 6.5)
        if self.state == 'ERROR':
            eye_glow = 1.0
        for side in (-1, 1):
            ex = cx + side * scale * 0.24
            ey = cy - scale * 0.18
            glow = QRadialGradient(QPointF(ex, ey), scale * 0.10)
            glow.setColorAt(0.0, QColor(255, 245, 235, int(180 * eye_glow)))
            glow.setColorAt(0.28, QColor(255, 72, 54, int(220 * eye_glow)))
            glow.setColorAt(1.0, QColor(255, 72, 54, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(ex, ey), scale * 0.108, scale * 0.050)
            p.setBrush(QColor(255, 228, 215, int(118 * eye_glow)))
            p.drawEllipse(QPointF(ex, ey), scale * 0.016, scale * 0.009)
            for j in range(3):
                ang = self.phase * (2.8 + j * 0.25) + j * 2.0 + (0 if side > 0 else 0.9)
                sx = ex + math.cos(ang) * scale * (0.040 + j * 0.006)
                sy = ey + math.sin(ang) * scale * (0.020 + j * 0.004)
                p.setBrush(QColor(255, 110, 92, int(82 * eye_glow)))
                p.drawEllipse(QPointF(sx, sy), 0.9, 0.9)

        talk = 0.5 + 0.5 * math.sin(self.phase * 9.0)
        mouth_y = cy + scale * 0.56
        mouth_w = scale * 0.090
        mouth_h = scale * (0.008 + (0.030 * talk if self.state == 'SPEAKING' else 0.007))
        mg = QRadialGradient(QPointF(cx, mouth_y), scale * 0.11)
        mg.setColorAt(0.0, QColor(255, 112, 78, 126 if self.state == 'SPEAKING' else 48))
        mg.setColorAt(1.0, QColor(255, 112, 78, 0))
        p.setBrush(mg)
        p.drawEllipse(QPointF(cx, mouth_y), mouth_w, max(scale * 0.018, mouth_h * 1.9))
        if self.state == 'SPEAKING':
            p.setPen(QPen(QColor(255, 214, 200, 118), 0.95))
            for i in range(6):
                xx = cx - scale * 0.048 + i * scale * 0.019
                hh = scale * 0.016 * (0.45 + 0.85 * abs(math.sin(self.phase * 8.2 + i * 0.7)))
                p.drawLine(QPointF(xx, mouth_y - hh), QPointF(xx, mouth_y + hh))
            p.setPen(QPen(QColor(255, 134, 106, 82), 0.8))
            p.drawArc(QRectF(cx - scale * 0.12, mouth_y - scale * 0.06, scale * 0.24, scale * 0.12), 200 * 16, 140 * 16)

        p.setPen(Qt.NoPen)
        for i, (x, y, tag) in enumerate(coords):
            base_alpha = {
                'head': 170, 'brow': 186, 'eye': 240, 'spine': 184,
                'cheek': 170, 'mouth': 198, 'chin': 174, 'mesh': 84,
            }.get(tag, 150)
            pulse = 0.70 + 0.30 * math.sin(self.phase * 2.4 + i * 0.09)
            alpha = int(base_alpha * pulse)
            if tag == 'eye':
                col = QColor(255, 72, 54, min(255, alpha))
            elif tag == 'mouth':
                col = QColor(255, 112, 78, min(255, alpha + (34 if self.state == 'SPEAKING' else 0)))
            else:
                col = QColor(accent.red(), accent.green(), accent.blue(), alpha)
            radius = 0.55 if tag == 'mesh' else 0.88
            if tag in {'eye', 'mouth'}:
                radius = 1.06
            if self.state == 'PROCESSING' and tag == 'mesh':
                radius = 0.68
            p.setBrush(col)
            p.drawEllipse(QPointF(x, y), radius, radius)

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            w, h = self.width(), self.height()
            accent = self._accent()
            self._draw_background(p, w, h, accent)
            self._draw_face(p, w, h, accent)

            font = p.font()
            font.setFamily('Segoe UI')
            font.setPointSize(9)
            font.setBold(True)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.2)
            p.setFont(font)
            p.setPen(QColor(236, 186, 92, 220))
            p.drawText(QRectF(0, 26, w, 28), Qt.AlignCenter, 'V  //  MODE 1 — 2D')

            sf = p.font()
            sf.setPointSize(7)
            sf.setBold(False)
            sf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.7)
            p.setFont(sf)
            status = {
                'READY': 'online',
                'LISTENING': 'ouvindo...',
                'PROCESSING': 'processando...',
                'SPEAKING': 'respondendo...',
                'ERROR': 'atenção',
            }.get(self.state, self.state.lower())
            p.setPen(QColor(accent.red(), accent.green(), accent.blue(), 210))
            p.drawText(QRectF(0, 51, w, 22), Qt.AlignCenter, status.upper())

            by = h - 56
            rg = QRadialGradient(QPointF(w * 0.5, by), 28)
            rg.setColorAt(0, QColor(accent.red(), accent.green(), accent.blue(), 58))
            rg.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(rg)
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 155), 1))
            p.drawEllipse(QPointF(w * 0.5, by), 22, 22)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(w * 0.5, by), 7, 7)
        finally:
            p.end()
