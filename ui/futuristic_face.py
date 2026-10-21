"""Vector portrait for the second interface; no image or network dependency."""
import math
import time

from PySide6.QtCore import QPointF, QRectF, QLineF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient

from .mobile_face_core import MobileFaceCoreWidget


class FuturisticFaceWidget(MobileFaceCoreWidget):
    def __init__(self, parent=None, voice_engine=None):
        super().__init__(parent, voice_engine)
        self.setMinimumSize(320, 320)
        self._last_frame = time.monotonic()
        self.timer.setTimerType(Qt.PreciseTimer)
        self._polygons = {}
        self._graduations = {True: [], False: []}
        for i in range(96):
            angle = i * math.tau / 96
            r = 241 if i % 4 else 238
            self._graduations[i % 4 == 0].append(QLineF(
                math.cos(angle)*r, math.sin(angle)*r, math.cos(angle)*247, math.sin(angle)*247))
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def _tick(self):
        now = time.monotonic()
        dt = min(.08, now - self._last_frame)
        self._last_frame = now
        target = self._raw_speech_level()
        self.speech_level += (target - self.speech_level) * (1 - math.exp(-dt * (22 if target > self.speech_level else 9)))
        self.phase += dt * (1.6 if self.state == 'PROCESSING' else .55)
        self.update()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        self._last_frame = time.monotonic()
        game_mode = getattr(self.window(), 'game_mode', None)
        self.timer.start(100 if game_mode is not None and game_mode.enabled else 16)
        super().showEvent(event)

    def _accent(self):
        return QColor({'LISTENING': '#81e7d5', 'PROCESSING': '#ffb677',
                       'SPEAKING': '#ff8674', 'ERROR': '#ff4564'}.get(self.state, '#ec715f'))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor('#090e14'))
        a = self._accent()
        cx, cy = w * .5, h * .46
        scale = min(w / 690, h / 620)
        p.translate(cx, cy)
        p.scale(scale, scale)
        glow = QRadialGradient(0, 0, 300)
        glow.setColorAt(0, self._with_alpha(a, 26 + int(self.speech_level * 20)))
        glow.setColorAt(.6, self._with_alpha(a, 7))
        glow.setColorAt(1, QColor(9, 14, 20, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QPointF(0, 0), 300, 300)

        # Instrument ring with sparse radial graduations and moving segments.
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor('#243039'), .8))
        for r in (219, 232):
            p.drawEllipse(QPointF(0, 0), r, r)
        for major, lines in self._graduations.items():
            p.setPen(QPen(self._with_alpha(a, 90 if major else 32), 1))
            p.drawLines(lines)
        for offset in (0, 180):
            p.setPen(QPen(self._with_alpha(a, 160), 2))
            p.drawArc(QRectF(-232, -232, 464, 464), int((self.phase * 18 + offset) * 16), 35 * 16)
        for px, py, opacity, size, seed in self.dust[:38]:
            x = (px - .5) * 620
            y = (py - .5) * 490
            p.setPen(Qt.NoPen)
            p.setBrush(self._with_alpha(a, 25 + int(35 * (.5 + .5 * math.sin(self.phase + seed)))))
            p.drawEllipse(QPointF(x, y), size, size)

        def polygon(points, fill, edge='#46515a', width=1):
            p.setBrush(QColor(fill))
            p.setPen(QPen(QColor(edge), width))
            p.drawPolygon(self._polygon(points))

        # Stable silhouette, with bevelled plates rather than a moving jaw.
        outline = [(0,-190),(-83,-173),(-134,-118),(-148,-26),(-120,91),
                   (-69,155),(0,181),(69,155),(120,91),(148,-26),(134,-118),(83,-173)]
        polygon(outline, '#121c26', '#6a5551', 1.3)
        for side in (-1, 1):
            def mirror(points):
                return [(x * side, y) for x, y in points]
            polygon(mirror([(0,-190),(83,-173),(134,-118),(93,-66),(22,-96)]), '#26313a', '#526069')
            polygon(mirror([(22,-96),(93,-66),(127,-87),(134,-118),(83,-157)]), '#303941', '#555b5d')
            polygon(mirror([(134,-118),(148,-26),(120,91),(99,54),(115,-48)]), '#151f29', '#414a52')
            polygon(mirror([(29,-22),(104,-47),(115,-27),(93,45),(43,65)]), '#202c36', '#54616a')
            polygon(mirror([(43,65),(93,45),(120,91),(69,155),(0,181),(19,120)]), '#263039', '#5a5d61')
            polygon(mirror([(69,155),(93,45),(78,93),(39,133)]), '#394047', '#4d5359')
            polygon(mirror([(0,-99),(22,-96),(29,-22),(18,43),(0,56)]), '#38424a', '#637078')
            # Recessed eye sockets and narrow luminous eye blades.
            eye = mirror([(28,-57),(111,-80),(97,-39),(40,-24)])
            polygon(eye, '#02080e', '#64727a', 1.3)
            blade = mirror([(36,-52),(101,-69),(90,-47),(43,-35)])
            p.setPen(QPen(self._with_alpha(a, 30), 12 + self.speech_level * 4))
            p.setBrush(self._with_alpha(a, 245))
            p.drawPolygon(self._polygon(blade))
            p.setPen(QPen(QColor('#ffe6d2'), 1.6))
            p.drawLine(QPointF(side*40,-49), QPointF(side*95,-63))
            p.setPen(QPen(self._with_alpha(a, 170), 1.5))
            for j in range(3):
                p.drawLine(QPointF(side*(106-j*4), 7+j*12), QPointF(side*(121-j*4),-1+j*12))
            p.setPen(QPen(self._with_alpha(a, 125), 1))
            p.drawLine(QPointF(side*75,-155), QPointF(side*113,-116))

        polygon([(-18,-151),(0,-130),(18,-151),(0,-117)], '#ec715f', '#ffc4a3')
        polygon([(-42,76),(0,89),(42,76),(27,113),(0,128),(-27,113)], '#070d13', '#65717a')
        # Small channels follow the real voice envelope; only light changes.
        for i in range(13):
            x = (i - 6) * 4.3
            level = self.speech_level * (.55 + .45 * math.sin(self.phase * 11 + i * .9) ** 2)
            height = 2 + level * 17
            p.setPen(QPen(self._with_alpha(a, 100 + int(155 * level)), 2))
            p.drawLine(QPointF(x,101-height/2), QPointF(x,101+height/2))

        if self.state in ('LISTENING', 'PROCESSING'):
            p.save()
            p.setClipRegion(self._face_region(outline))
            y = -190 + (self.phase * 70 % 380)
            g = QLinearGradient(0, y-25, 0, y+2)
            g.setColorAt(0, self._with_alpha(a, 0))
            g.setColorAt(1, self._with_alpha(a, 45))
            p.fillRect(QRectF(-155,y-25,310,27),g)
            p.restore()

        p.setPen(QColor('#89959f'))
        p.setFont(QFont('Segoe UI', 9))
        p.drawText(QRectF(-220,268,440,25), Qt.AlignCenter, 'V  /  PRESENÇA DIGITAL')
        p.end()

    def _polygon(self, points):
        key = tuple(points)
        if key not in self._polygons:
            self._polygons[key] = QPolygonF([QPointF(x, y) for x, y in points])
        return self._polygons[key]

    @staticmethod
    def _face_region(points):
        from PySide6.QtGui import QRegion, QPolygon
        from PySide6.QtCore import QPoint
        return QRegion(QPolygon([QPoint(x, y) for x, y in points]))
