"""Offline visual check of the default Orbital interface."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from voice.engine import VoiceEngine


def main():
    app = QApplication([])
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'segoeuisl.ttf'):
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font.exists(): QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Segoe UI', 10))
    voice = VoiceEngine({}); voice.speak = Mock()
    with patch.object(MainWindow, '_load_mics'), patch('ui.gmail_settings.load_account', return_value=None):
        window = InstagramExperimentWindow(SimpleNamespace(), SimpleNamespace(skills=[]), voice, startup_greeting=False)
    window.processing_sound.set_enabled(False); window._initiative_timer.stop(); window.tts_toggle.setChecked(False)
    window.append_v('A apresentação do seu dia está pronta. Você pode iniciá-la no botão Resumo do dia.')
    window.append_v('Você pode pedir para listar seus e-mails e escolher uma mensagem para ouvir. Configure sua conta em Controles → Gmail.')
    window.append_v('Como posso ajudar agora?\n\nPosso apresentar seu dia, ler seus e-mails ou buscar as notícias.\n\nDiga “V” ou escreva seu pedido abaixo.')
    window.resize(1180, 720); window.show(); app.processEvents()
    root = Path(__file__).resolve().parents[1]
    window.grab().save(str(root / 'orbital_principal_preview.png'))
    window._show_controls(3); app.processEvents()
    window.controls_dialog.grab().save(str(root / 'gmail_config_preview.png'))
    window.close()


if __name__ == '__main__': main()
