"""Offline UI check using a public YOLOX example, never a webcam."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, patch
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QFont, QFontDatabase
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from ui.camera_panel import CameraPanel
from voice.engine import VoiceEngine


def main():
    app = QApplication([])
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'segoeuisl.ttf'):
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Segoe UI', 10))
    voice = VoiceEngine({})
    voice.speak = Mock()
    root = Path(__file__).resolve().parents[1]
    with patch.object(MainWindow, '_load_mics'), patch('ui.gmail_settings.load_account', return_value=None):
        window = InstagramExperimentWindow(SimpleNamespace(), SimpleNamespace(skills=[]), voice, startup_greeting=False)
    window.processing_sound.set_enabled(False)
    window._initiative_timer.stop()
    window.tts_toggle.setChecked(False)
    window.show()
    with patch('ui.camera_panel.QMediaDevices.videoInputs', return_value=[]):
        panel = window.show_camera()
    panel.selector.addItem('Imagem pública de teste / câmera desligada', b'test')
    panel.show()
    app.processEvents()
    image = QImage(str(root / 'logs/vision/sample_dog.jpg'))
    assert not image.isNull()
    result = panel.processor.run(image, None)
    panel.camera = Mock()
    panel.frame_at = time.monotonic()
    panel.future_generation = panel.generation
    panel.future = Future()
    panel.future.set_result(result)
    panel._tick()
    panel._show_image(image)
    panel.status.setText('Verificação com imagem pública de teste · câmera real desligada')
    app.processEvents()
    panel.grab().save(str(root / 'logs/vision/camera_preview.png'))
    # Exercise both routes: these must never reach the planner.
    window.enqueue_command('V, desligue a câmera')
    assert panel.camera is None
    window.enqueue_command('V, o que você está vendo?')
    assert panel.camera is None
    assert not window.pending_commands
    panel.close()
    app.processEvents()
    window.grab().save(str(root / 'logs/vision/orbital_camera_preview.png'))
    window.close()
    print('Camera UI, command dispatch and close verified without webcam capture.')


if __name__ == '__main__':
    main()
