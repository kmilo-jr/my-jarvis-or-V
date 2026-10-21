"""Original isometric office artwork inspired by the user's second reference.

All geometry is 2D. Furniture tiles and character poses are cached, not 3D.
"""
from functools import lru_cache
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QTransform


def iso(x,y,z=0):
    return QPointF(200+20*x-22*y,75+10*x+11*y-z)


def poly(p,points,color,edge='#353541'):
    p.setPen(QPen(QColor(edge),.5) if edge else Qt.NoPen)
    p.setBrush(QColor(color));p.drawPolygon(QPolygonF(points))


def slab(p,x,y,w,d,z,h,color):
    c=QColor(color)
    a,b,c1,d1=[iso(u,v,z+h) for u,v in ((x,y),(x+w,y),(x+w,y+d),(x,y+d))]
    poly(p,[d1,c1,iso(x+w,y+d,z),iso(x,y+d,z)],c.darker(130).name())
    poly(p,[b,c1,iso(x+w,y+d,z),iso(x+w,y,z)],c.darker(153).name())
    poly(p,[a,b,c1,d1],c.lighter(110).name())


def face(p,x,y,z,w,h,side='x',color='#ddd7c9'):
    a=iso(x,y,z)
    b=iso(x+w,y,z) if side=='x' else iso(x,y+w,z)
    poly(p,[a,b,b+QPointF(0,-h),a+QPointF(0,-h)],color)


def line(p,a,b,color,width=.5):
    p.setPen(QPen(QColor(color),width));p.drawLine(a,b)


# Local coordinates correspond to the same isometric floor used for navigation.
TARGET_WORLD={'rest':(3.5,3.3),'listen':(3.5,3.3),'books':(1.3,2.9),
              'read':(1.3,2.9),'desk':(5.1,2.0),'calendar':(6.8,1.0),
              'music':(6.7,3.2),'sofa':(1.4,5.4),'tv':(1.4,5.4),
              'sleep':(6.4,5.8),'wander':(4.1,4.3)}
TARGETS={k:(iso(*v).x(),iso(*v).y()) for k,v in TARGET_WORLD.items()}
OBJECTS={
    'books':(QRectF(114,45,67,80),'Estante · preparar uma pergunta de estudo'),
    'desk':(QRectF(230,74,111,90),'Mesa · preparar um pedido'),
    'calendar':(QRectF(325,80,30,37),'Calendário · preparar consulta da agenda'),
    'music':(QRectF(266,138,57,52),'Rádio · preparar um pedido de música'),
    'sofa':(QRectF(55,104,82,65),'Sofá · descansar'),
    'sleep':(QRectF(165,158,100,86),'Cama · cochilar'),
    'tv':(QRectF(128,141,66,80),'TV · assistir na sala'),
}
DEPTHS={'books':123,'desk':160,'calendar':116,'music':188,'sofa':166,'sleep':223,'tv':198}


def background():
    im=QImage(1200,800,QImage.Format_RGB32);im.fill(QColor('#171b26'))
    p=QPainter(im);p.scale(3,3);p.setRenderHint(QPainter.Antialiasing)
    slab(p,0,0,8,7,-9,9,'#64716e')
    # Pale walls and warm graphite trim, like an inhabited miniature room.
    poly(p,[iso(0,0),iso(0,7),iso(0,7,63),iso(0,0,63)],'#aabbb4')
    poly(p,[iso(0,0),iso(8,0),iso(8,0,63),iso(0,0,63)],'#c6d1c3')
    for x in range(8):
        for y in range(7):
            slab(p,x,y,1,1,0,0,'#b1c0b6' if (x+y)%2 else '#bec9bc')
            line(p,iso(x+.08,y+.08),iso(x+.85,y+.08),'#d9dfcd',.35)
    for end in ((8,0),(0,7)):
        line(p,iso(0,0,63),iso(*end,63),'#e3e7d8',2)
        line(p,iso(0,0,3),iso(*end,3),'#6d7f79',2)
    # Glazed windows on the back wall with geometric outdoor skyline.
    for x in (1.0,2.8,4.6):
        face(p,x,0,23,1.4,31,color='#596760')
        face(p,x+.09,0,25,1.22,27,color='#8db2ae')
        line(p,iso(x+.7,0,25),iso(x+.7,0,52),'#dae1c9',1.2)
        line(p,iso(x+.1,0,38),iso(x+1.3,0,38),'#dae1c9',1)
        slab(p,x-.05,0,1.5,.22,22,2,'#dec3a2')
    # Wall pinboard, clock and ventilation slats.
    face(p,0,4.55,27,1.5,22,'y','#695746')
    face(p,0,4.67,29,1.25,18,'y','#b18a63')
    for y,z in ((4.8,40),(5.4,39),(5.1,33)):
        face(p,0,y,z,.35,4,'y','#ecd49b')
    a=iso(0,1.0,43);p.setBrush(QColor('#ece4ce'));p.setPen(QPen(QColor('#485451'),1))
    p.drawEllipse(QRectF(a.x()-5,a.y()-6,10,12))
    line(p,a,a+QPointF(0,-3),'#485451',.7);line(p,a,a+QPointF(3,1),'#485451',.7)
    for y in (6.05,6.22,6.39):face(p,0,y,48,.12,6,'y','#60766f')
    # Burgundy carpet in the central walkable area.
    slab(p,2.2,2.65,3.2,2.65,.2,.2,'#85495a')
    for x in (2.3,5.3):line(p,iso(x,2.75,1),iso(x,5.2,1),'#d39a91',.7)
    for y in (2.75,5.2):line(p,iso(2.3,y,1),iso(5.3,y,1),'#d39a91',.7)
    for x,y in ((.5,.5),(.4,6.55),(7.5,.35),(7.55,6.5)):
        plant(p,x,y)
    p.end();return im


def plant(p,x,y):
    slab(p,x,y,.35,.35,0,6,'#b48866')
    for dx,dy,z in ((0,0,12),(.2,0,16),(0,.2,20),(-.1,.1,15)):
        a=iso(x+dx,y+dy,z)
        poly(p,[a+QPointF(-5,0),a+QPointF(0,-5),a+QPointF(5,0),a+QPointF(0,3)],'#678e74')


def _furniture(p,key,active,phase):
    if key=='books':
        slab(p,.05,1.7,.55,2.0,0,45,'#97714f')
        # Three shelves facing into the room, individual spines and labels.
        for z in (3,17,31):slab(p,.0,1.7,.66,2.0,z,1.4,'#be956b')
        for z in (3,17,31):
            face(p,.70,1.79,z+2,1.8,11,'y','#4b423b')
            for i,color in enumerate(('#a84e54','#c6aa73','#687b98','#89997d','#b78167','#667b7e')):
                face(p,.72,1.84+i*.28,z+2.3,.20,7+i%3,'y',color)
                face(p,.73,1.86+i*.28,z+5,.13,.5,'y','#ead6ab')
        if active:face(p,.74,2.25,18,.21,10,'y','#ead29b')
    elif key=='desk':
        for x in (4.1,6.6):
            for y in (.6,1.5):slab(p,x,y,.12,.13,0,18,'#515653')
        slab(p,4,.4,2.9,1.4,17,3,'#b77c54')
        slab(p,6.15,.6,.6,.8,0,15,'#99704f')
        for z in (5,10):face(p,6.15,1.41,z,.6,.8,color='#4f4945')
        slab(p,4.55,.9,.72,.35,20,1,'#39454c')
        face(p,4.5,.86,24,1.35,16,color='#29343c')
        # Transform into the slanted monitor plane for miniature system UI.
        p.save();a=iso(4.56,.87,38)
        p.setTransform(QTransform(1,.5,0,1,a.x(),a.y()),True)
        screen(p,'desktop',25,12,phase);p.restore()
        slab(p,4.5,1.35,.95,.3,20,.4,'#414c4e')
        for i in range(6):line(p,iso(4.57+i*.13,1.39,21),iso(4.57+i*.13,1.58,21),'#b9c3b5',.45)
        slab(p,6.25,.9,.2,.2,20,4,'#dfd5b3')
        slab(p,4.05,1.15,.3,.45,20,1,'#ded8bf')
        for y in (1.20,1.30,1.40):line(p,iso(4.09,y,22),iso(4.30,y,22),'#959585',.4)
        # Chair, swiveling slightly only while occupied.
        d=.025*math.sin(phase) if active else 0
        slab(p,4.95+d,1.8,.65,.65,4,3,'#45494c')
        slab(p,4.95+d,2.35,.65,.12,7,12,'#874b5b')
    elif key=='calendar':
        face(p,6.45,.01,34,1.25,22,color='#f0e7ce')
        face(p,6.45,.02,49,1.25,7,color='#954b59')
        for x in range(4):
            for z in (37,41,45):face(p,6.58+x*.26,.03,z,.12,1.2,color='#9b978b')
    elif key=='music':
        slab(p,6.95,1.9,.8,1.25,0,17,'#9b7359')
        slab(p,7.05,2.05,.55,.75,17,9,'#4e4845')
        for z in (19,21,23):face(p,7.04,2.15,z,.55,.6,'y','#b6a183')
        face(p,7.04,2.15,24,.55,2,'y','#e5b36e')
        for y in (2.08,2.72):face(p,7.77,y,5,.28,7,'y','#604e48')
    elif key=='sofa':
        slab(p,.55,4.8,1.2,1.85,0,7,'#623f48')
        slab(p,.5,4.7,.18,2.05,7,16,'#a25c66')
        for y in (4.75,6.55):slab(p,.55,y,1.2,.20,7,9,'#c18080')
        for y in (5.04,5.80):
            slab(p,.75,y,.93,.7,7,3-(.4 if active else 0),'#b46d76')
            line(p,iso(.8,y+.05,11),iso(1.6,y+.05,11),'#deb0a1',.5)
        slab(p,.76,5.13,.35,.4,11,6,'#c8b59b')
        for y in (5.1,5.9):face(p,1.68,y,8,.45,.6,'y','#d2999b')
    elif key=='sleep':
        slab(p,5.85,4.7,1.45,2.05,0,6,'#795849')
        slab(p,5.82,4.65,1.52,.15,4,18,'#a98065')
        slab(p,5.93,4.8,1.27,1.85,6,4,'#e5d9bc')
        slab(p,6.10,4.95,.88,.4,10,2,'#f4eacf')
        slab(p,5.93,5.55,1.27,1.10,10,1,'#9b5969')
        for y in (5.72,6.1,6.45):line(p,iso(6,y,12),iso(7.13,y,12),'#bf8992',.6)
    elif key=='tv':
        slab(p,3.8,5.65,1.55,.62,0,10,'#9e785b')
        face(p,3.93,5.70,13,1.3,18,color='#303b43')
        p.save();a=iso(3.99,5.71,29)
        p.setTransform(QTransform(1,.5,0,1,a.x(),a.y()),True)
        screen(p,'news',24,14,phase);p.restore()


def screen(p,kind,w,h,phase):
    p.fillRect(QRectF(0,0,w,h),QColor('#314b62'))
    if kind=='desktop':
        p.fillRect(QRectF(0,0,w,2),QColor('#7798a4'))
        p.fillRect(QRectF(1,3,5,h-4),QColor('#213b50'))
        for i in range(3):p.fillRect(QRectF(2,4+i*2,3,.5),QColor('#b2c7c0'))
        p.fillRect(QRectF(7,3,16,3),QColor('#607d8c'))
        for i in range(5):
            height=2+1.3*math.sin(phase+i)
            p.fillRect(QRectF(8+i*3,10-height,1.8,height),QColor('#d2967e'))
    else:
        p.fillRect(QRectF(1,2,9,9),QColor('#657e98'))
        p.fillRect(QRectF(3,7,5,4),QColor('#b07a7b'))
        p.setPen(Qt.NoPen);p.setBrush(QColor('#efd0a7'));p.drawEllipse(QRectF(4,3,3,4))
        for y in (3,6,9):p.fillRect(QRectF(12,y,10,1),QColor('#e4d4b1'))
        p.fillRect(QRectF(0,h-2,w,2),QColor('#a94f5f'))
        p.save();p.setClipRect(QRectF(0,h-2,w,2))
        for i in range(4):p.fillRect(QRectF((i*8-phase*4)%32-8,h-1.4,5,.6),QColor('#f7e5ca'))
        p.restore()


@lru_cache(maxsize=128)
def tile(key,active=False,frame=0):
    rect=OBJECTS[key][0].adjusted(-3,-3,3,3)
    im=QImage(round(rect.width()*3),round(rect.height()*3),QImage.Format_ARGB32_Premultiplied)
    im.fill(Qt.transparent);p=QPainter(im);p.scale(3,3);p.translate(-rect.x(),-rect.y())
    p.setRenderHint(QPainter.Antialiasing,False)
    _furniture(p,key,active,frame/6);p.end();return rect,im


def furniture(p,key,active=False,phase=0):
    frame=int(phase*6)%12 if key in ('tv','desk') else 0
    rect,im=tile(key,active,frame);p.drawImage(rect,im)


def character(direction,frame):
    # Tiny red resident with a stepped silhouette and flat, three-tone shading.
    im=QImage(144,144,QImage.Format_ARGB32_Premultiplied);im.fill(Qt.transparent)
    p=QPainter(im);p.scale(3,3)
    def b(x,y,w,h,c):p.fillRect(QRectF(x,y,w,h),QColor(c))
    b(15,34+frame,7,7,'#343942');b(26,35-frame,7,7,'#343942')
    b(15,39+frame,8,2,'#7a4452');b(26,40-frame,8,2,'#7a4452')
    b(16,26,17,13,'#994953');b(18,27,10,10,'#ba6670');b(29,28,4,10,'#703b4d')
    b(11,28-frame,5,10,'#c18184');b(33,28+frame,5,10,'#7e495b')
    b(12,9,24,22,'#583b4d');b(9,12,31,16,'#633f50')
    b(12,8,24,4,'#d5918a');b(11,12,27,15,'#b46870');b(35,12,4,16,'#804959')
    if direction!=2:
        fx=11 if direction==1 else 22 if direction==3 else 14
        fw=14 if direction in (1,3) else 20
        b(fx,16,fw,11,'#273744');b(fx+1,17,fw-2,1,'#516371')
        for x in ([fx+4] if direction in (1,3) else [18,28]):b(x,20,2,4,'#f4d8a1')
    else:
        b(17,17,13,7,'#994954');b(19,23,9,1,'#dfaa98')
    b(22,30,2,2,'#efc9a0');b(24,32,2,2,'#efc9a0');b(26,30,2,2,'#efc9a0')
    p.end();return im
