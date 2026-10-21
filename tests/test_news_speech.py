import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from voice.news_speech import news_text, news_source
from voice.engine import VoiceEngine
from ui.main_window import MainWindow


class NewsSpeechTests(unittest.TestCase):
    def test_portuguese_notation_preserves_values(self):
        self.assertEqual(news_text('Pesquisa: 47% no 2º turno; 45,5% na 1ª etapa.'),
                         'Pesquisa: quarenta e sete por cento no segundo turno; quarenta e cinco vírgula cinco por cento na primeira etapa')
        self.assertEqual(news_text('25/09/2026: 1.250 pessoas.'),
                         'vinte e cinco de setembro de dois mil e vinte e seis: mil duzentos e cinquenta pessoas')

    def test_sources_and_acronyms_do_not_read_domains(self):
        self.assertEqual(news_source('cnnbrasil.com.br'), 'cê ene ene Brasil')
        self.assertEqual(news_source('unknown.com.br'), '')
        self.assertEqual(news_text('MPF e STF'), 'Ministério Público Federal e Supremo Tribunal Federal')
        self.assertEqual(news_text('G1'), 'gê um')

    def test_news_counter_does_not_generate_a_separate_short_phrase(self):
        item = {'title': 'Pesquisa registra 47% no 2º turno', 'source': 'cnnbrasil.com.br'}
        speech = MainWindow._news_slide_speech(item, 0, 6)
        self.assertTrue(speech.startswith('Pesquisa'))
        self.assertNotIn('Notícia um de seis', speech)
        self.assertNotIn('.com', speech)
        self.assertEqual(len(VoiceEngine({})._split_xtts_response(speech)), 1)
        self.assertEqual(item['title'], 'Pesquisa registra 47% no 2º turno')

    def test_pending_speech_keeps_current_news_slide(self):
        window = SimpleNamespace(_news_slide_items=[{}], _news_slide_wait_started=0,
                                 _news_slide_voice_seen=False,
                                 tts_toggle=Mock(), voice_engine=Mock(), _news_slide_timer=Mock())
        window.tts_toggle.isChecked.return_value = True
        window.voice_engine.is_speaking.return_value = False
        window.voice_engine.has_pending_speech.return_value = True
        MainWindow._poll_news_slideshow(window)
        self.assertTrue(window._news_slide_voice_seen)
        window._news_slide_timer.stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
