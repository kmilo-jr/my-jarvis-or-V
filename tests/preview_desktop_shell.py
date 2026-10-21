"""Offline preview with explicit sample data; does not access connected accounts."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from voice.engine import VoiceEngine
from core.daily_briefing import card

app=QApplication.instance() or QApplication([])
for name in ('segoeui.ttf','segoeuib.ttf','segoeuisl.ttf'):
    QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/name))
app.setFont(QFont('Segoe UI',10))
v=VoiceEngine({}); v.speak=Mock()
with patch.object(MainWindow,'_load_mics'), patch('ui.gmail_settings.load_account',return_value=None):
    w=InstagramExperimentWindow(SimpleNamespace(),SimpleNamespace(skills=[]),v,startup_greeting=False,theme='red')
w.processing_sound.set_enabled(False); w._initiative_timer.stop(); w.tts_toggle.setChecked(False)
w.resize(1500,900); w.show(); app.processEvents()
shell=w.desktop_shell
shell.update_briefing([
    card('agenda','Agenda de exemplo','09:30 · Revisar projeto\n14:00 · Estudar inglês',metric='2'),
    card('gmail','E-mails de exemplo','Ana · Reunião do projeto\nFaculdade · Material da aula',metric='2'),
    card('notícias','Notícia ilustrativa','As manchetes e fontes reais aparecem ao gerar o briefing.'),
    card('clima','Cidade de exemplo','Valores apenas para conferir o layout.',metric='26°'),
])
shell.summary.setText('PRÉVIA VISUAL · dados ilustrativos, sem consulta às contas.')
out=Path('logs/reference_shell'); out.mkdir(parents=True,exist_ok=True)
for page in ('briefing','chat','stage','settings','editor','notices','monitor'):
    shell.select(page); app.processEvents(); w.grab().save(str(out/(page+'.png')))
w.resize(1180,720); shell.select('briefing'); app.processEvents(); w.grab().save(str(out/'compact.png'))
w.close()
print('Preview complete')
