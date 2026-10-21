from __future__ import annotations
import math
from pathlib import Path
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget


class AmberNeuralWidget(QWidget):
    """Fluid particle emblem for the second V interface.

    The emblem is reconstructed from particles, not displayed as a bitmap.
    Its motion changes clearly with V's state while keeping the original symbol
    recognizable and the area around it clean.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = 'READY'
        self.phase = 0.0
        self.state_age = 0.0
        self._mx = 0.0
        self._my = 0.0
        self._activity = 0.12
        self._target_activity = 0.12
        self.setMinimumSize(620, 500)
        self.setMouseTracking(True)

        asset = Path(__file__).resolve().parent.parent / 'assets' / 'v_symbol_reference.png'
        self._symbol_image = QImage(str(asset))
        self._particles = self._extract_particles(self._symbol_image)
        self._links = self._build_links(self._particles)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 FPS only for the second interface

    def _extract_particles(self, img: QImage):
        raw = []
        if img.isNull():
            return raw
        w, h = img.width(), img.height()
        # Dense enough to look fluid while keeping PySide6 comfortably near 60 FPS.
        target = 1100
        step = max(3, int(math.sqrt((w * h) / max(1, target * 2.2))))
        idx = 0
        for y in range(0, h, step):
            for x in range(0, w, step):
                c = img.pixelColor(x, y)
                if c.red() > 72 and c.red() > c.green() * 1.48 and c.red() > c.blue() * 1.48:
                    raw.append((x / max(1, w - 1), y / max(1, h - 1), idx))
                    idx += 1
        if not raw:
            return []

        # Normalize to the actual red-symbol bounds instead of the full source image.
        min_x = min(v[0] for v in raw); max_x = max(v[0] for v in raw)
        min_y = min(v[1] for v in raw); max_y = max(v[1] for v in raw)
        span_x = max(1e-6, max_x - min_x)
        span_y = max(1e-6, max_y - min_y)
        particles = []
        for nx, ny, i in raw:
            x = (nx - min_x) / span_x
            y = (ny - min_y) / span_y
            dx = x - 0.5
            dy = y - 0.50
            radius = min(1.0, math.hypot(dx, dy) / 0.70)
            center_weight = max(0.15, 1.0 - radius)
            drift = 0.35 + 0.65 * ((i % 23) / 22.0)
            seed = i * 0.073 + (i % 11) * 0.19
            particles.append((x, y, center_weight, drift, seed, radius))
        return particles

    def _build_links(self, particles):
        links = []
        if not particles:
            return links
        cell = 0.055
        grid = {}
        for i, (x, y, *_rest) in enumerate(particles):
            grid.setdefault((int(x / cell), int(y / cell)), []).append((i, x, y))
        for i, (x, y, *_rest) in enumerate(particles):
            cx, cy = int(x / cell), int(y / cell)
            local = []
            for gx in range(cx - 1, cx + 2):
                for gy in range(cy - 1, cy + 2):
                    for j, px, py in grid.get((gx, gy), []):
                        if j <= i:
                            continue
                        d2 = (px - x) ** 2 + (py - y) ** 2
                        if d2 < 0.00155:
                            local.append((d2, j))
            local.sort(key=lambda item: item[0])
            for _dist, j in local[:2]:
                links.append((i, j))
        return links

    def mouseMoveEvent(self, event):
        if self.width() > 0 and self.height() > 0:
            self._mx = max(-1.0, min(1.0, (event.position().x() / self.width() - 0.5) * 2.0))
            self._my = max(-1.0, min(1.0, (event.position().y() / self.height() - 0.5) * 2.0))
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._mx *= 0.35
        self._my *= 0.35
        super().leaveEvent(event)

    def set_state(self, state: str):
        new_state = str(state or 'READY').upper()
        if new_state != self.state:
            self.state_age = 0.0
        self.state = new_state
        self._target_activity = {
            'READY': 0.12,
            'LISTENING': 0.42,
            'PROCESSING': 0.95,
            'SPEAKING': 0.78,
            'ERROR': 0.70,
        }.get(self.state, 0.20)
        self.update()

    def _tick(self):
        speed = {
            'READY': 0.015,
            'LISTENING': 0.024,
            'PROCESSING': 0.041,
            'SPEAKING': 0.034,
            'ERROR': 0.026,
        }.get(self.state, 0.017)
        self.phase = (self.phase + speed) % math.tau
        self.state_age += 1.0 / 60.0
        self._activity += (self._target_activity - self._activity) * 0.10
        self.update()

    def _accent(self):
        if self.state == 'ERROR':
            return QColor(255, 92, 92)
        if self.state == 'SPEAKING':
            return QColor(255, 88, 70)
        if self.state == 'PROCESSING':
            return QColor(255, 48, 48)
        if self.state == 'LISTENING':
            return QColor(255, 68, 68)
        return QColor(236, 52, 52)

    def _speech_envelope(self):
        # Natural-looking cadence instead of a constant robotic sine wave.
        v = (
            0.52
            + 0.22 * math.sin(self.phase * 8.6)
            + 0.13 * math.sin(self.phase * 13.7 + 1.1)
            + 0.08 * math.sin(self.phase * 4.1 + 0.35)
        )
        return max(0.08, min(1.0, v))

    def _draw_background(self, p: QPainter, w: int, h: int, accent: QColor):
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0.0, QColor(1, 2, 6))
        bg.setColorAt(0.52, QColor(4, 6, 12))
        bg.setColorAt(1.0, QColor(1, 2, 6))
        p.fillRect(self.rect(), bg)

        center = QPointF(w * 0.50, h * 0.44)
        halo = QRadialGradient(center, min(w, h) * 0.34)
        halo_alpha = 28 + int(44 * self._activity)
        halo.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), halo_alpha))
        halo.setColorAt(0.58, QColor(accent.red(), accent.green(), accent.blue(), 5))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(center, min(w, h) * 0.31, min(w, h) * 0.31)

        # Keep the canvas clean: only state-specific rings are drawn.
        if self.state == 'LISTENING':
            for i in range(2):
                wave = (self.phase * 0.35 + i * 0.5) % 1.0
                radius = min(w, h) * (0.20 + wave * 0.16)
                alpha = int(48 * (1.0 - wave))
                p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), alpha), 1.0))
                p.drawEllipse(center, radius, radius * 0.86)
        elif self.state == 'PROCESSING':
            r = min(w, h) * 0.345
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 50), 1.1))
            start = int((self.phase * 115.0) % 360 * 16)
            p.drawArc(QRectF(center.x() - r, center.y() - r * 0.86, r * 2, r * 1.72), start, 88 * 16)
            p.drawArc(QRectF(center.x() - r * 0.82, center.y() - r * 0.70, r * 1.64, r * 1.40), -start, 58 * 16)
        elif self.state == 'SPEAKING':
            env = self._speech_envelope()
            radius = min(w, h) * (0.27 + env * 0.025)
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), int(28 + 46 * env)), 1.0 + env * 0.5))
            p.drawEllipse(center, radius, radius * 0.84)

    def _particle_pos(self, part, box_x, box_y, box_w, box_h):
        nx, ny, center_weight, drift, seed, radius = part
        dx = nx - 0.5
        dy = ny - 0.5

        # Whole-symbol breathing keeps READY alive but calm.
        breath = 1.0 + 0.0045 * math.sin(self.phase * 1.15)
        x0 = 0.5 + dx * breath
        y0 = 0.5 + dy * breath

        # Base fluid motion shared by all states.
        base_amp = 0.55 + self._activity * 1.35
        fluid_x = math.sin(self.phase * (0.95 + drift * 0.55) + seed) * base_amp
        fluid_y = math.cos(self.phase * (0.78 + drift * 0.42) + seed * 1.27) * base_amp * 0.55

        # Slight cursor parallax, strongest near the visual center.
        parallax_x = self._mx * 5.5 * (0.35 + center_weight)
        parallax_y = self._my * 3.5 * (0.35 + center_weight)

        extra_x = 0.0
        extra_y = 0.0
        if self.state == 'LISTENING':
            # The symbol subtly focuses inward/outward, like attention locking on.
            focus = math.sin(self.phase * 3.0 + radius * 6.0) * 1.4
            extra_x += -dx * focus * 2.2
            extra_y += -dy * focus * 2.2
        elif self.state == 'PROCESSING':
            # Controlled swirl around each particle's home position.
            tang_x = -dy
            tang_y = dx
            swirl = (2.2 + 2.8 * radius) * math.sin(self.phase * 3.6 + seed * 0.8)
            extra_x += tang_x * swirl * 3.3
            extra_y += tang_y * swirl * 3.3
            # Small radial bursts travel through the emblem without destroying the silhouette.
            burst = math.sin(self.phase * 5.0 - radius * 14.0 + seed * 0.13)
            extra_x += dx * burst * 3.6
            extra_y += dy * burst * 3.6
        elif self.state == 'SPEAKING':
            env = self._speech_envelope()
            # Speech makes the emblem expand from the center with uneven cadence.
            radial = (1.8 + 4.2 * env) * (0.35 + radius)
            extra_x += dx * radial
            extra_y += dy * radial
            # A mild horizontal wave makes the lower 'jaw' region visibly react.
            lower = max(0.0, ny - 0.42)
            extra_y += math.sin(self.phase * 10.0 + nx * 8.0 + seed * 0.15) * env * lower * 6.0
        elif self.state == 'ERROR':
            extra_x += math.sin(self.phase * 17.0 + seed) * 1.8
            extra_y += math.cos(self.phase * 14.0 + seed * 1.3) * 1.2

        px = box_x + x0 * box_w + fluid_x + parallax_x + extra_x
        py = box_y + y0 * box_h + fluid_y + parallax_y + extra_y
        return QPointF(px, py)

    def _draw_symbol(self, p: QPainter, w: int, h: int, accent: QColor):
        if not self._particles:
            return

        box_h = h * 0.48
        box_w = box_h * 1.32
        box_x = (w - box_w) / 2.0
        box_y = h * 0.18
        positions = [self._particle_pos(part, box_x, box_y, box_w, box_h) for part in self._particles]

        # Network links remain subtle in READY and become more active while processing.
        for i, j in self._links:
            p1, p2 = positions[i], positions[j]
            d = math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
            if d > box_w * 0.058:
                continue
            base = max(0, 72 - int(d * 1.30))
            factor = {
                'READY': 0.52,
                'LISTENING': 0.72,
                'PROCESSING': 1.18,
                'SPEAKING': 0.90,
                'ERROR': 0.96,
            }.get(self.state, 0.45)
            alpha = int(base * factor)
            if alpha <= 2:
                continue
            p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), alpha), 0.65))
            p.drawLine(p1, p2)

        env = self._speech_envelope() if self.state == 'SPEAKING' else 0.0

        # Particle field. Glow is sampled on half the points for performance and a cleaner look.
        for idx, (part, pos) in enumerate(zip(self._particles, positions)):
            _nx, _ny, center_weight, drift, seed, radius = part
            shimmer = 0.5 + 0.5 * math.sin(self.phase * (1.75 + drift * 0.8) + seed)
            alpha = 150 + int(145 * shimmer * (0.45 + center_weight * 0.55))
            if self.state == 'READY':
                alpha = int(alpha * 0.92)
            elif self.state == 'PROCESSING':
                alpha = min(255, int(alpha * 1.20))
            elif self.state == 'SPEAKING':
                alpha = min(255, int(alpha * (0.82 + env * 0.35)))

            size = 1.25 + 1.45 * center_weight + 0.55 * shimmer
            if self.state == 'SPEAKING':
                size *= 0.90 + env * 0.35
            elif self.state == 'PROCESSING':
                size *= 1.05

            p.setPen(Qt.NoPen)
            if idx % 2 == 0:
                glow_alpha = int(alpha * (0.28 if self.state == 'READY' else 0.36))
                p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), glow_alpha))
                p.drawEllipse(pos, size * 3.35, size * 3.35)

            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), min(255, alpha)))
            p.drawEllipse(pos, size * 0.62, size * 0.62)
            if idx % 5 == 0:
                p.setBrush(QColor(255, 235, 235, min(235, int(alpha * 0.78))))
                p.drawEllipse(pos, max(0.6, size * 0.24), max(0.6, size * 0.24))

        center = QPointF(w * 0.50, box_y + box_h * 0.54)
        underglow = QRadialGradient(center, box_w * 0.28)
        underglow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 34 + int(self._activity * 46)))
        underglow.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setBrush(underglow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(center, box_w * 0.28, box_h * 0.18)

        # State-specific energy pass, deliberately outside the particle loop.
        if self.state == 'PROCESSING':
            scan_y = box_y + ((math.sin(self.phase * 1.05) * 0.5 + 0.5) * box_h)
            scan = QLinearGradient(0, scan_y - 14, 0, scan_y + 14)
            scan.setColorAt(0.0, QColor(255, 60, 60, 0))
            scan.setColorAt(0.5, QColor(255, 70, 70, 48))
            scan.setColorAt(1.0, QColor(255, 60, 60, 0))
            p.fillRect(QRectF(box_x - 10, scan_y - 14, box_w + 20, 28), scan)
        elif self.state == 'SPEAKING':
            # Two clean energy ripples synchronized to the synthetic speech envelope.
            for n in range(2):
                wave = (self.phase * 0.62 + n * 0.5) % 1.0
                r = box_w * (0.17 + wave * 0.18)
                alpha = int((1.0 - wave) * (42 + 58 * env))
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), alpha), 1.0 + env * 0.35))
                p.drawEllipse(center, r, r * 0.72)

    def _draw_label(self, p: QPainter, w: int, h: int, accent: QColor):
        labels = {
            'READY': 'STANDBY',
            'LISTENING': 'OUVINDO',
            'PROCESSING': 'PROCESSANDO',
            'SPEAKING': 'FALANDO',
            'ERROR': 'ATENÇÃO',
        }
        state_text = labels.get(self.state, self.state)
        font = QFont('Segoe UI', max(9, int(min(w, h) * 0.018)), QFont.Weight.Medium)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 3.5)
        p.setFont(font)
        p.setPen(QColor(232, 236, 242, 185))
        p.drawText(int(w * 0.30), int(h * 0.74), int(w * 0.40), 26, Qt.AlignCenter, state_text)

        # Tiny state pulse under the label, giving feedback without adding panel clutter.
        pulse = 0.5 + 0.5 * math.sin(self.phase * (2.0 if self.state == 'READY' else 4.0))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), int(90 + 100 * pulse * self._activity)))
        p.drawEllipse(QPointF(w * 0.50, h * 0.792), 2.0 + self._activity * 1.2, 2.0 + self._activity * 1.2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        accent = self._accent()
        self._draw_background(p, self.width(), self.height(), accent)
        self._draw_symbol(p, self.width(), self.height(), accent)
        self._draw_label(p, self.width(), self.height(), accent)
