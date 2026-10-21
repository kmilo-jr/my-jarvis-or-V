"""Export illustrative screenshots without microphone, network or speech playback.

Run from the project directory: .venv/Scripts/python.exe -m tests.preview_daily_briefing
"""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from voice.engine import VoiceEngine
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from ui.daily_briefing import BriefingPanel
from core.daily_briefing import card


def main():
    app = QApplication([])
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'segoeuisl.ttf'):
        path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont('Segoe UI', 10))
    voice = VoiceEngine({}); voice.speak = Mock()
    with patch.object(MainWindow, '_load_mics'):
        window = InstagramExperimentWindow(SimpleNamespace(), SimpleNamespace(skills=[]), voice, startup_greeting=False)
    window.processing_sound.set_enabled(False)
    window._initiative_timer.stop(); window.tts_toggle.setChecked(False)
    window.resize(1500, 900); window.show(); app.processEvents()
    panel = BriefingPanel(window); window._briefing_panel = panel
    cards = [
        card('seu dia', 'Bom dia. Vamos ao seu dia.', 'Clima no Rio · agenda · pendências · mensagens · notícias', metric='08:00'),
        card('clima', 'O dia no Rio de Janeiro', 'Rio de Janeiro: 26 °C agora. Mínima de 22 °C e máxima de 30 °C hoje. Probabilidade máxima de chuva no dia: 20%.', metric='26°', source='Demonstração visual · valores ilustrativos'),
        card('agenda', 'Sua agenda de hoje', '09:30 · Revisar o protótipo\n14:00 · Reunião de planejamento', metric='2', source='Demonstração visual · compromissos ilustrativos'),
        card('pendências', 'O que ficou pendente', 'Projeto V · Revisar a apresentação\nTrabalho · Conferir os documentos', metric='2', source='Demonstração visual · itens ilustrativos'),
        card('mensagens', 'Mensagens recebidas', '01  TRABALHO\nReunião de planejamento confirmada para as 14:00.\n\n02  PROJETO V\nA revisão da interface está disponível para conferência.', metric='2', source='Demonstração visual · mensagens ilustrativas'),
    ]
    panel.start(cards)
    for i in range(1, len(cards)):
        panel.present(i)
    panel.toggle_pause()
    panel.fade.stop(); panel.effect.setOpacity(1)
    panel._stop_flight()
    panel.progress_animation.stop(); panel.progress.setValue(1000)
    app.processEvents()
    root = Path(__file__).resolve().parents[1]
    window.grab().save(str(root / 'resumo_do_dia_preview.png'))
    window.resize(1180, 720); app.processEvents(); panel.position(); app.processEvents()
    window.grab().save(str(root / 'resumo_do_dia_compacto.png'))
    panel.present(2, automatic=False); panel._stop_flight()
    panel._details = True; panel.paused = True
    panel.finish_details(panel._generation, 'Você tem dois compromissos neste exemplo.\n\nÀs 09:30, está prevista a revisão do protótipo. Às 14:00, há uma reunião de planejamento.\n\nOs registros não informam a duração dos compromissos. Ao retomar, o V volta ao cartão da agenda e continua a sequência.')
    panel.pause_button.setText('Retomar resumo')
    panel.fade.stop(); panel.effect.setOpacity(1); app.processEvents()
    window.grab().save(str(root / 'resumo_do_dia_detalhes.png'))
    window.close()


if __name__ == '__main__':
    main()
