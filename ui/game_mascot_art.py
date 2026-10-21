"""Ultron-style pixel armor for the game avatar; cached transparent frames."""
from functools import lru_cache
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPainter, QColor, QPolygon


@lru_cache(maxsize=96)
def mascot_frame(state='READY', motion=0, greeting=0, amount=0, pleased=False, hover=False):
    image=QImage(52,52,QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p=QPainter(image)
    def box(x,y,w,h,c):p.fillRect(x,y,w,h,QColor(c))
    def plate(points,c):
        p.setPen(Qt.NoPen);p.setBrush(QColor(c))
        p.drawPolygon(QPolygon([QPoint(x,y) for x,y in points]))
    ink='#171b24';dark='#333c49';steel='#788692';silver='#b6c1c8';light='#e2e7e5'
    red='#ff3b46' if state!='ERROR' else '#ff8a75'
    # Shadow stays anchored while the character greets.
    box(15,48,24,2,'#20212a')
    p.save();p.translate(0,-(amount if greeting==1 else 0))
    for x in (18,28):
        plate([(x,38),(x+7,38),(x+6,45),(x+8,47),(x-1,47),(x,43)],ink)
        box(x+1,39,5,5,steel);box(x+1,39,2,4,silver)
        box(x,45,7,2,dark);box(x+1,45,4,1,light)
    # Layered chest plates and red V-shaped reactor.
    plate([(14,29),(38,29),(35,38),(31,42),(21,42),(17,38)],ink)
    plate([(15,30),(25,32),(24,38),(19,37)],silver)
    plate([(37,30),(27,32),(28,38),(33,37)],steel)
    plate([(18,31),(24,33),(23,35),(18,34)],light)
    plate([(34,31),(28,33),(29,35),(34,34)],silver)
    box(23,37,6,4,dark);box(24,38,4,1,steel)
    plate([(22,32),(26,35),(30,32),(26,38)],'#772b38')
    box(25,34,2,3,red)
    for x,lift in ((10,amount if greeting==2 else 0),(36,amount*2 if greeting in (0,2) else 0)):
        plate([(x,29-lift),(x+6,28-lift),(x+7,34-lift),(x+5,43-lift),(x,42-lift),(x-1,35-lift)],ink)
        box(x,30-lift,6,5,steel);box(x,30-lift,4,2,light)
        box(x+1,36-lift,4,5,dark);box(x+1,37-lift,2,3,silver)
        box(x+4,32-lift,1,3,red)
    # Angular skull, segmented forehead and mechanical cheek/jaw plates.
    p.save();p.translate(-1 if state=='LISTENING' else 0,0)
    plate([(19,4),(33,4),(39,10),(39,22),(35,29),(29,33),(23,33),(17,29),(13,22),(13,10)],ink)
    plate([(20,5),(32,5),(37,10),(36,18),(31,17),(26,14),(21,17),(16,18),(15,10)],steel)
    plate([(20,5),(26,5),(24,13),(20,16),(16,12)],silver)
    plate([(27,5),(32,6),(36,10),(33,12),(28,11)],'#9aa7b2')
    box(21,6,4,1,light);box(27,6,4,1,light)
    plate([(24,8),(28,8),(28,14),(26,17),(24,14)],dark)
    plate([(13,9),(16,12),(17,22),(14,24),(11,18),(11,10)],dark)
    plate([(39,9),(36,12),(35,22),(38,24),(41,18),(41,10)],dark)
    box(12,12,1,7,silver);box(39,12,1,7,steel)
    plate([(16,17),(21,16),(25,19),(23,23),(17,21)],ink)
    plate([(36,17),(31,16),(27,19),(29,23),(35,21)],ink)
    eye='#ff867e' if pleased else red
    height=2 if state in ('LISTENING','ERROR') or hover else 1
    box(17,18,4,height,eye);box(20,19,3,1,eye)
    if not (greeting==3 and amount>1):box(31,18,4,height,eye)
    box(29,19,3,1,eye)
    if state=='PROCESSING':
        box(18+motion,18,1,1,'#ffd2c5');box(33-motion,18,1,1,'#ffd2c5')
    plate([(16,22),(20,23),(23,27),(21,30),(17,27)],silver)
    plate([(36,22),(32,23),(29,27),(31,30),(35,27)],steel)
    plate([(25,19),(27,19),(29,24),(26,25),(23,24)],silver)
    plate([(22,25),(30,25),(29,29),(26,31),(23,29)],dark)
    box(23,26,6,1,'#a34b52')
    for i in range(3):
        box(23+i*2,27,1,2 if state=='SPEAKING' and i==motion else 1,red)
    box(24,30,4,1,silver)
    p.restore();p.restore();p.end()
    return image
