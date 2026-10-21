r"""Prévia visual independente. Não inicia voz, IA nem serviços do V.

Execute com .venv\Scripts\python.exe examples/avatar_25d/preview.py
Acrescente --snapshot para salvar uma captura sem abrir a janela.
A arte é um recorte visual da prancha de conceitos, ainda sem animação.
"""
import os
import sys
from pathlib import Path

if '--snapshot' in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

HERE = Path(__file__).resolve().parent


class AvatarPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('V / conceito 2.5D')
        self.setFixedSize(940, 600)
        # Carregado uma única vez. A prévia não precisa de temporizador.
        self.art = QPixmap(str(HERE / 'conceitos.png'))
        if self.art.isNull():
            raise RuntimeError('Não foi possível carregar conceitos.png')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor('#101014'))

        def text(x, y, value, size=12, color='#e7dfe3', bold=False):
            font = QFont('Segoe UI', size)
            font.setBold(bold)
            p.setFont(font)
            p.setPen(QColor(color))
            p.drawText(x, y, value)

        text(36, 44, 'V / COMPANHEIRO', 13, '#ff8b9f', True)
        text(36, 71, 'Estudo visual · personagem em 2.5D', 10, '#a59ca7')

        # Usa apenas a área do personagem 3 da prancha, sem alterar o arquivo.
        source = QRectF(0, self.art.height() * .515,
                        self.art.width() * .497, self.art.height() * .430)
        target = QRectF(24, 106, 490, 490 * source.height() / source.width())
        p.drawPixmap(target, self.art, source)

        p.setPen(QColor('#57303d'))
        p.setBrush(QColor('#1c1720'))
        p.drawRoundedRect(QRectF(544, 154, 360, 304), 20, 20)
        text(570, 193, 'SEU COMPANHEIRO', 10, '#ff8b9f', True)
        text(570, 240, 'Vamos aprender algo?', 20, bold=True)
        text(570, 279, 'Posso acompanhar seus estudos,', 12)
        text(570, 306, 'leituras e projetos.', 12)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#992e50'))
        p.drawRoundedRect(QRectF(570, 350, 308, 56), 12, 12)
        text(609, 385, 'Vermelho · grafite · luz suave', 11, '#fff0f3')
        text(36, 553, 'PRÉVIA ESTÁTICA', 10, '#ff8b9f', True)
        text(36, 578, 'Imagem desenhada pelo PySide6. Poses e animações ainda serão produzidas.', 10, '#a59ca7')
        p.end()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    for name in ('segoeui.ttf', 'segoeuib.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
    window = AvatarPreview()
    if '--snapshot' in sys.argv:
        if not window.grab().save(str(HERE / 'preview.png')):
            raise RuntimeError('Não foi possível salvar a captura')
    else:
        window.show()
        sys.exit(app.exec())
