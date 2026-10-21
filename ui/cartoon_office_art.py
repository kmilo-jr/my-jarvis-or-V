"""Small vector room and character assets, rasterized once by the office."""
from PySide6.QtCore import Qt, QRectF
import math
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QLinearGradient, QPainterPath

OBJECTS = {
    'books': (QRectF(30,43,76,83), 'Estante · preparar uma pergunta de estudo'),
    'desk': (QRectF(145,57,108,65), 'Mesa · preparar um pedido'),
    'calendar': (QRectF(282,44,39,42), 'Calendário · preparar consulta da agenda'),
    'music': (QRectF(330,110,43,45), 'Rádio · preparar um pedido de música'),
    'sofa': (QRectF(32,173,105,54), 'Sofá · descansar'),
    'sleep': (QRectF(293,179,70,61), 'Cama · cochilar'),
    'tv': (QRectF(30,134,64,32), 'TV · assistir na sala'),
}


def rounded(p,x,y,w,h,color,r=3,outline=None):
    p.setPen(QPen(QColor(outline),.8) if outline else Qt.NoPen)
    base=QColor(color)
    shade=QLinearGradient(x,y,x+w*.25,y+h)
    shade.setColorAt(0,base.lighter(112));shade.setColorAt(.45,base)
    shade.setColorAt(1,base.darker(117))
    p.setBrush(shade);p.drawRoundedRect(QRectF(x,y,w,h),r,r)


def background():
    im=QImage(1200,800,QImage.Format_RGB32);im.fill(QColor('#171925'))
    p=QPainter(im);p.scale(3,3);p.setRenderHint(QPainter.Antialiasing)
    r=lambda x,y,w,h,c,rad=3:rounded(p,x,y,w,h,c,rad)
    r(17,29,371,228,'#0e111b',13)
    r(12,19,370,228,'#393447',12)
    r(22,58,350,178,'#aa8075',7)
    for y in range(75,235,20):
        p.setPen(QPen(QColor('#946d68'),.6));p.drawLine(23,y,371,y)
        for x in range(36+(y%40),360,54):
            p.drawLine(x,y,x,y+19)
            p.setPen(QPen(QColor('#bc9384'),.45));p.drawLine(x+5,y+7,x+31,y+7)
            p.setPen(QPen(QColor('#946d68'),.6))
    r(12,18,370,43,'#555068',8);r(12,50,11,186,'#60566b',2)
    r(372,50,10,186,'#443d54',2)
    r(23,58,348,3,'#e3a18f',1)
    # Wide evening window, deliberately graphic rather than textured.
    r(146,25,111,31,'#252c44',4);r(150,28,103,23,'#425572',2)
    for x,h in ((155,9),(169,15),(182,7),(215,13),(231,18),(245,11)):
        r(x,51-h,9,h,'#303c56',0);r(x+3,53-h,2,2,'#f3c799',0)
    r(199,26,3,29,'#b7969b',0)
    r(143,54,117,4,'#debda9',1)
    # Wall sconces and framed art give the room a lived-in silhouette.
    for x in (120,342):
        r(x,35,3,14,'#c9a08f',1);r(x-5,32,13,7,'#f8d79e',3)
    r(267,88,32,35,'#563e54',3);r(270,91,26,29,'#e2c1a7',2)
    r(273,94,20,23,'#52637c',1)
    p.setPen(Qt.NoPen);p.setBrush(QColor('#edb17e'));p.drawEllipse(QRectF(282,96,7,7))
    hill=QPainterPath();hill.moveTo(273,117);hill.lineTo(280,104);hill.lineTo(293,117);hill.closeSubpath()
    p.setBrush(QColor('#b57b83'));p.drawPath(hill)
    r(123,132,162,96,'#704152',12);r(127,136,154,88,'#c76878',10)
    r(134,142,140,76,'#ad5268',9)
    p.setPen(QPen(QColor('#e6a898'),.6));p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(132,140,144,80),9,9)
    for x in range(143,270,7):
        p.drawLine(x,145,x+2,145);p.drawLine(x,215,x+2,215)
    p.setPen(QPen(QColor('#eea590'),1));p.drawLine(194,177,203,186);p.drawLine(203,186,212,177)
    for key,(rect,_) in OBJECTS.items():
        p.setPen(Qt.NoPen);p.setBrush(QColor(35,25,42,35))
        p.drawRoundedRect(rect.translated(3,5),5,5)
        furniture(p,key)
    for x,y in ((274,55),(361,85),(267,226)):
        r(x-6,y,12,10,'#d69b87',3)
        p.setPen(QPen(QColor('#476e62'),1.5));p.drawLine(x,y,x,y-16)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#79aa8c'))
        p.drawEllipse(QRectF(x-11,y-16,11,7));p.drawEllipse(QRectF(x,y-21,10,9))
        p.setPen(QPen(QColor('#b7c9a4'),.6));p.drawLine(x-9,y-12,x-1,y-12)
    r(107,213,15,9,'#d7b192',2)
    for y,c in ((209,'#637c89'),(205,'#c68185')):
        r(109,y,16,4,c,1);r(110,y+1,12,1,'#eedbc0',0)
    p.end();return im


def furniture(p,key,active=False,phase=0):
    r=lambda x,y,w,h,c,rad=3:rounded(p,x,y,w,h,c,rad)
    if key=='books':
        r(33,49,76,81,'#81566a',4);r(30,43,76,79,'#e0ae91',4)
        for row in range(3):
            y=49+row*23;r(35,y,66,19,'#6f5263',1)
            for i,c in enumerate(('#be586c','#e3ad72','#719c9c','#8f83b0','#dd8276','#9bb094')):
                h=12+(i%3)*2;r(39+i*10,y+18-h,7,h,c,1)
                r(41+i*10,y+19-h,3,1,'#f7dec0',0)
        if active:r(63,96,8,20,'#ffe0a8',1)
        for y in (69,92,115):r(33,y,70,2,'#f0c8a3',.5)
        for row in range(3):
            for x in (40,60,80):r(x,58+row*23,4,1,'#d5c0ac',0)
    elif key=='desk':
        r(153,94,8,30,'#795563');r(238,94,8,30,'#795563')
        r(147,75,108,29,'#916173',5);r(145,71,108,25,'#e8b597',5)
        r(170,55,57,33,'#343348',4);r(173,58,51,24,'#536e81' if active else '#354759',2)
        if active:
            r(177,61,43,3,'#283b53',1); r(178,62,15,1,'#a8d5c4',0)
            for i,w in enumerate((26,34,18)): r(178,67+i*4,w,1,'#7bb6ac',0)
            for i,h in enumerate((4,8,6,10,5)): r(180+i*7,82-h,3,h,'#e09a82',1)
            r(199,62,11,2,'#e8b178',1)
        else:
            for i,w in enumerate((22,33,17)):r(179,63+i*5,w,2,'#658498',1)
        r(194,86,10,4,'#575166',1);r(181,91,37,4,'#886a79',1)
        r(234,78,9,10,'#fff0c9',2);r(244,80,3,5,'#fff0c9',1)
        r(236,79,5,2,'#84616b',1)
        for x in range(184,217,4):r(x,92,2,1,'#d8b6b4',.5)
        r(150,83,21,7,'#f3d9b9',1);r(153,85,14,1,'#ad8892',0)
        r(152,67,4,15,'#76637b',1);r(149,65,14,5,'#ffdfa1' if active else '#c39e88',2)
        r(147,94,103,1,'#f7c5a4',0)
        # Chair and lamp react within this object's existing redraw region.
        shift=math.sin(phase*1.5)*.8 if active else 0
        r(187+shift,104,29,16,'#55465f',5)
        r(190+shift,106,23,9,'#a15e77',4)
        r(200+shift,119,3,5,'#514157',1)
    elif key=='calendar':
        r(282,44,39,42,'#efd6b1',4);r(282,44,39,10,'#c56076',3)
        for y in (60,68,76):
            for x in (289,297,305,313):r(x,y,3,3,'#b59697',1)
        r(296,67,5,5,'#d26677',1)
    elif key=='music':
        r(330,118,43,37,'#785768',4);r(330,110,43,37,'#d69b83',4)
        r(335,116,20,24,'#665267',3)
        for y in range(119,139,4):r(338,y,14,1,'#a8878e',0)
        r(359,116,9,7,'#f1bd78',1);r(361,130,6,6,'#f4d6af',3)
    elif key=='sofa':
        squash=1.5+.3*math.sin(phase*2) if active else 0
        r(36,217,7,10,'#634858');r(124,217,7,10,'#634858')
        r(32,179,105,44,'#773e5c',8);r(36,173,97,34,'#d2788c',8)
        r(42,195+squash,39,22-squash,'#bd637e',5);r(84,195,39,22,'#bd637e',5)
        r(31,189,11,32,'#e197a0',5);r(127,189,11,32,'#e197a0',5)
        r(49,182,20,17,'#eed0a6',5);r(97,184,17,15,'#8ca9a1',4)
        p.setPen(QPen(QColor('#f0b3b4'),.6));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(45,198+squash,33,15-squash),3,3)
        p.drawRoundedRect(QRectF(87,198,33,15),3,3)
        r(107,200,17,22,'#8b859e',2)
        for x in (110,115,120):r(x,201,1,20,'#c9b4bd',.5)
    elif key=='sleep':
        r(293,184,70,56,'#775468',5);r(293,179,70,14,'#dba398',4)
        r(299,188,58,44,'#f1d3b7',4);r(304,190,22,11,'#fff0d5',4);r(330,190,22,11,'#fff0d5',4)
        r(299,204,58,29,'#8b6f98',4);r(299,203,58,6,'#b498b7',2)
        for y in (212,219,226):r(304,y,48,1,'#a88dab',.5)
        r(307,192,15,1,'#fff7de',.5);r(333,192,15,1,'#fff7de',.5)
    elif key=='tv':
        r(30,155,64,11,'#cc9d88',3);r(38,134,48,25,'#343348',3)
        r(41,137,42,18,'#668ca0' if active else '#445267',2)
        if active:
            r(44,140,12,12,'#d88483',3);r(47,142,6,5,'#f4c29f',2)
            r(59,140,21,3,'#f3d8a4',1);r(59,145,17,2,'#eab6a0',1);r(59,149,20,2,'#f0d8b0',1)
            ticker=47+int(phase*18)%18
            r(43,153,38,1,'#e9a16d',0);r(ticker,153,8,1,'#fff0be',0)


def character(direction,frame):
    im=QImage(144,144,QImage.Format_ARGB32_Premultiplied);im.fill(Qt.transparent)
    p=QPainter(im);p.scale(3,3);p.setRenderHint(QPainter.Antialiasing)
    r=lambda x,y,w,h,c,rad=3:rounded(p,x,y,w,h,c,rad,'#502d46')
    step=frame*2
    r(15,36+step,8,5,'#874157',2);r(26,38-step,8,5,'#874157',2)
    r(15,26,19,13,'#cd6379',5);r(10,28-step,6,10,'#e18a93',3);r(34,28+step,6,10,'#e18a93',3)
    r(9,7,32,25,'#e27c8c',9);r(12,8,26,5,'#f6b0a9',3)
    if direction!=2:
        face_x=11 if direction==1 else 19 if direction==3 else 13
        face_w=19 if direction in (1,3) else 24
        r(face_x,15,face_w,14,'#30394c',5)
        for x in ((face_x+5,) if direction in (1,3) else (19,29)):
            rounded(p,x,19,3,6,'#ffe7b7',1.5)
    else:r(17,17,17,8,'#c15b75',3)
    if direction==0:
        p.setPen(QPen(QColor('#ffe7b7'),1.3));p.drawLine(21,32,24,35);p.drawLine(24,35,27,32)
    r(7,17,4,9,'#af4d69',2);r(39,17,4,9,'#af4d69',2)
    rounded(p,8,19,1,4,'#f8c0b0',.5);rounded(p,41,19,1,4,'#f8c0b0',.5)
    p.setPen(QPen(QColor('#ffe1c4'),.7));p.drawLine(17,11,24,11)
    p.end();return im
