"""Video-reference briefing visuals, painted locally without bitmap dependencies."""
import math
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient, QLinearGradient, QPixmap, QRegion
from PySide6.QtWidgets import QWidget, QPushButton
from .animation_clock import AnimationClock


class BriefingBackdrop(QWidget):
    def __init__(self, parent, theme='blue'):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.phase = 0.0
        self.state = 'READY'
        self.speaking = False
        self._clock = AnimationClock()
        self._background = None
        self._background_key = None
        self.theme = str(theme or 'blue').lower()
        # The angular basis never changes. Keep every original vertex/ring.
        self._rings = [[(math.cos(a), math.sin(a), math.sin(3*a+ring*.8),
                         math.cos(3*a+ring*.8), math.sin(5*a+ring), math.cos(5*a+ring))
                        for a in (math.tau*n/160 for n in range(161))] for ring in range(9)]
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)

    def set_theme(self, theme):
        theme = str(theme or 'blue').lower()
        if theme not in {'blue', 'red'}:
            theme = 'blue'
        if theme != self.theme:
            self.theme = theme
            self._background = None
            self._background_key = None
            self.update()

    def _colors(self):
        if self.theme == 'red':
            return {
                'bg': '#0d0c14', 'deep': '#291323', 'glow': '#5f152c',
                'grid': (105, 39, 68), 'halo': (255, 60, 98),
                'ring_outer': (178, 25, 51), 'ring': (255, 72, 90),
                'point': '#b51a35', 'point_bright': '#ff6570',
            }
        return {
            'bg': '#02091d', 'deep': '#052566', 'glow': '#034cc4',
            'grid': (55, 133, 226), 'halo': (0, 143, 255),
            'ring_outer': (0, 119, 255), 'ring': (29, 196, 255),
            'point': '#137ceb', 'point_bright': '#39d9ff',
        }

    def set_state(self, state):
        self.state = str(state).upper()
        self.speaking = str(state).upper() == 'SPEAKING'
        self.update()

    def showEvent(self, event):
        self._clock.reset()
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def tick(self):
        self.phase = (self.phase + self._clock.step() * (.875 if self.speaking else .3)) % math.tau
        w, h = self.width(), self.height()
        extent = min(w*.28, h*(.27 if self.theme == 'red' else .35))*1.16 + 6
        ring = QRectF(w*.5-extent, h*.49-extent, extent*2, extent*2).toAlignedRect()
        self.update(QRegion(ring).united(QRegion(QRect(w//2-18, h-44, 36, 36))))

    def _static_background(self):
        w, h = self.width(), self.height()
        dpr = self.devicePixelRatioF()
        key = (w, h, dpr, self.theme)
        if self._background_key == key and self._background is not None:
            return self._background
        pixmap = QPixmap(max(1, math.ceil(w*dpr)), max(1, math.ceil(h*dpr)))
        pixmap.setDevicePixelRatio(dpr)
        p = QPainter(pixmap); p.setRenderHint(QPainter.Antialiasing)
        colors = self._colors()
        p.fillRect(self.rect(), QColor(colors['bg']))
        center = QPointF(w * .5, h * .49)
        radius = min(w * .28, h * (.27 if self.theme == 'red' else .35))
        glow = QRadialGradient(center, max(w * .57, h * .7))
        glow.setColorAt(0, QColor(colors['glow'])); glow.setColorAt(.42, QColor(colors['deep']))
        glow.setColorAt(1, QColor(colors['bg']))
        p.fillRect(self.rect(), glow)
        for x in range(0, w, 28):
            p.setPen(QPen(QColor(*colors['grid'], 48 if x % 112 else 75), .6))
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 28):
            p.setPen(QPen(QColor(*colors['grid'], 48 if y % 112 else 75), .6))
            p.drawLine(0, y, w, y)
        halo = QRadialGradient(center, radius * 1.25)
        hr, hg, hb = colors['halo']
        halo.setColorAt(0, QColor(hr, hg, hb, 0)); halo.setColorAt(.70, QColor(hr, hg, hb, 12))
        halo.setColorAt(.84, QColor(hr, hg, hb, 50)); halo.setColorAt(1, QColor(hr, hg, hb, 0))
        p.setPen(Qt.NoPen); p.setBrush(halo)
        p.drawEllipse(center, radius * 1.25, radius * 1.25)
        p.end()
        self._background, self._background_key = pixmap, key
        return pixmap

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(0, 0, self._static_background())
        w, h = self.width(), self.height()
        center = QPointF(w*.5, h*.49)
        radius = min(w*.28, h*(.27 if self.theme == 'red' else .35))
        colors = self._colors()
        p.setBrush(Qt.NoBrush)
        sp, cp = math.sin(self.phase), math.cos(self.phase)
        sp2, cp2 = math.sin(self.phase*1.4), math.cos(self.phase*1.4)
        for ring in range(9):
            path = QPainterPath()
            for n, (ca, sa, s3, c3, s5, c5) in enumerate(self._rings[ring]):
                ripple = .048 * (s3*cp + c3*sp)
                ripple += .028 * (c5*cp2 + s5*sp2)
                if self.theme == 'red': ripple *= 1.6
                r = radius * (.91 + ring * .011 + ripple)
                point = QPointF(center.x() + r * ca, center.y() + r * sa)
                if n == 0: path.moveTo(point)
                else: path.lineTo(point)
            ro = colors['ring_outer']; ri = colors['ring']
            p.setPen(QPen(QColor(*ro, 25), 7)); p.drawPath(path)
            p.setPen(QPen(QColor(*ri, 70 + ring * 11), .8)); p.drawPath(path)
        # Small luminous listening point, as in the reference.
        c = QPointF(w / 2, h - 26)
        p.setPen(QPen(QColor(colors['point']), 1)); p.drawEllipse(c, 15, 15)
        p.setPen(QPen(QColor(colors['point_bright']), 1.4)); p.drawEllipse(c, 10, 10)
        for i in range(-3, 4):
            length = 2 + abs(math.sin(self.phase * 3 + i)) * (5 if self.speaking else 2)
            p.drawLine(QPointF(c.x() + i * 2, c.y() - length), QPointF(c.x() + i * 2, c.y() + length))


class TopicThumbnail(QPushButton):
    """A real content preview, not just a navigation label."""
    def __init__(self, item, parent=None, theme='blue'):
        super().__init__(parent)
        self.item = item
        self.theme = str(theme or 'blue').lower()
        self.picture = None
        self.setCheckable(True)
        self.setFixedSize(166, 122)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(item['title'])
        self.setAccessibleName(item['kind'] + ': ' + item['title'])

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if self.theme == 'red':
            gradient.setColorAt(0, QColor(61, 7, 18, 246))
            gradient.setColorAt(.5, QColor(102, 12, 28, 231))
            gradient.setColorAt(1, QColor(24, 3, 10, 247))
            border, kind, title, metric, body = '#ff6875', '#ff8790', '#fff0f1', '#ff9da5', '#f4c8cc'
        else:
            gradient.setColorAt(0, QColor(3, 32, 72, 246))
            gradient.setColorAt(.5, QColor(5, 45, 108, 231))
            gradient.setColorAt(1, QColor(2, 13, 37, 247))
            border, kind, title, metric, body = '#43cfff', '#4cceff', '#dbf7ff', '#80e5ff', '#a5d4f5'
        p.setBrush(gradient)
        p.setPen(QPen(QColor(border if self.underMouse() or self.hasFocus() else ('#a62a43' if self.theme == 'red' else '#2866a2')), 1))
        p.drawRoundedRect(rect, 6, 6)
        p.setClipRect(rect.adjusted(9, 7, -9, -7))
        p.setFont(QFont('Segoe UI', 7)); p.setPen(QColor(kind))
        p.drawText(11, 18, self.item['kind'].upper())
        p.setFont(QFont('Segoe UI', 9, QFont.DemiBold)); p.setPen(QColor(title))
        title = p.fontMetrics().elidedText(self.item['title'], Qt.ElideRight, self.width()-22)
        p.drawText(11, 35, title)
        body_y = 43
        if self.picture is not None:
            p.drawPixmap(11, 42, self.width()-22, 42, self.picture)
            body_y = 87
        elif self.item.get('metric'):
            p.setFont(QFont('Segoe UI', 21)); p.setPen(QColor(metric))
            p.drawText(11, 69, str(self.item['metric']))
            body_y = 78
        p.setFont(QFont('Segoe UI', 7)); p.setPen(QColor(body))
        p.drawText(QRectF(11, body_y, self.width()-22, self.height()-body_y-9),
                   Qt.TextWordWrap | Qt.AlignTop, self.item['body'])
