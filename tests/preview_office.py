"""Offline office preview; illustrative task, no account or model access."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontDatabase
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from voice.engine import VoiceEngine
app=QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)
app.setFont(QFont('Segoe UI',10))
voice=VoiceEngine({});voice.speak=Mock()
with patch.object(MainWindow,'_load_mics'),patch('ui.gmail_settings.load_account',return_value=None):
    w=InstagramExperimentWindow(SimpleNamespace(),SimpleNamespace(skills=[]),voice,startup_greeting=False,theme='red')
w._initiative_timer.stop();w.processing_sound.set_enabled(False)
w.resize(1500,900);w.show();app.processEvents()
w._active_request='Qual a filosofia de hoje?';w.neural.state='PROCESSING'
w.desktop_shell.select('office');app.processEvents()
out=Path('logs/office_preview');out.mkdir(exist_ok=True)
w.grab().save(str(out/'office.png'))
w.neural.state='READY';shell=w.desktop_shell
shell.office._idle_activity='sleep';shell.office.sync_activity(snap=True);shell.office.update();app.processEvents()
w.grab().save(str(out/'office_idle.png'))
w.resize(1100,720);app.processEvents();w.grab().save(str(out/'compact.png'))
w.close();app.processEvents()
