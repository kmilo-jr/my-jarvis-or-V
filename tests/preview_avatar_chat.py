"""Render an illustrative avatar conversation without starting V services."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtGui import QFontDatabase,QImage,QPainter,QColor
from ui.floating_orb import FloatingOrb
from ui.avatar_chat import AvatarChat

if __name__ == '__main__':
    app=QApplication([])
    for font in ('segoeui.ttf','segoeuib.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
    orb=FloatingOrb(lambda:('READY',False))
    window=SimpleNamespace(voice_enabled=False,voice_status=QLabel(''),neural=SimpleNamespace(state='READY'))
    panel=AvatarChat(window,orb)
    panel.add_message('VOCÊ','Me ajude a organizar meus estudos.')
    panel.set_reply('Vamos começar pelo que merece mais atenção.\n\nQual matéria você quer revisar primeiro?')
    panel.show();app.processEvents()
    canvas=QImage(540,480,QImage.Format_RGB32);canvas.fill(QColor('#09090f'))
    p=QPainter(canvas);p.drawPixmap(16,18,panel.grab());p.drawPixmap(423,333,orb.grab());p.end()
    canvas.save('logs/reference_shell/avatar_chat_refined.png')
    panel.hide()
