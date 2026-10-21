import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QCheckBox
from core.daily_briefing import DailyBriefing, card, is_briefing_request, rio_weather, explain_card
from core.initiative import InitiativeStore
from core.personal_assistant import ListStore
from core.functional_engine import FunctionalEngine
from ui.daily_briefing import BriefingPanel


class BriefingDataTests(unittest.TestCase):
    def test_explanation_uses_snapshot_without_action_router(self):
        brain = Mock()
        brain.chat.return_value = 'Seu compromisso começa às dez.'
        item = card('agenda', 'Agenda', 'Reunião às dez.')
        self.assertEqual(explain_card(item, brain), brain.chat.return_value)
        self.assertEqual(brain.chat.call_args.args[2]['assunto']['body'], item['body'])
        brain.plan.assert_not_called()

    def test_explanation_falls_back_to_available_data(self):
        brain = Mock(); brain.chat.side_effect = TimeoutError
        item = card('notícias', 'Manchete', 'Trecho disponível')
        text = explain_card(item, brain)
        self.assertIn('Trecho disponível', text)
        self.assertIn('Abra a fonte', text)
        brain.reset_mock()
        explain_card(card('clima', 'Indisponível', 'Consulta falhou', ok=False), brain)
        brain.chat.assert_not_called()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.events = InitiativeStore(root / 'events.json')
        self.lists = ListStore(root / 'lists.json')
        self.now = datetime(2026, 9, 30, 8)
        self.builder = DailyBriefing(self.events, self.lists, now=self.now,
            weather=lambda: card('clima', 'Rio', '26 graus'),
            news=lambda: [{'title': 'Manchete de teste', 'url': 'https://example.org', 'source': 'Teste'}],
            messages=lambda: ([], {'automatic': False}), emails=lambda: [])

    def test_gmail_failure_keeps_news_and_does_not_claim_empty(self):
        self.builder.emails = Mock(side_effect=TimeoutError)
        cards = self.builder.build()
        email = next(c for c in cards if c['kind'] == 'gmail')
        self.assertFalse(email['ok'])
        self.assertIn('Não consegui', email['body'])
        self.assertEqual(cards[-1]['title'], 'Manchete de teste')

    def test_gmail_only_sender_and_subject_are_spoken(self):
        from core.daily_briefing import gmail_cards
        with patch('integrations.gmail_reader.load_account', return_value=True), patch(
                'integrations.gmail_reader.GmailReader') as reader:
            reader.return_value.morning_messages.return_value = [
                {'sender': 'Ana', 'title': 'Reunião', 'body': 'Às dez.'}]
            self.builder.emails = gmail_cards
            item = next(c for c in self.builder.build() if c['kind'] == 'gmail')
        self.assertIn('Ana', item['speech'])
        self.assertIn('Reunião', item['speech'])
        self.assertNotIn('Às dez.', item['speech'])
        self.assertNotIn('Às dez.', item['body'])
        brain = Mock()
        self.assertNotIn('Às dez.', explain_card(item, brain))
        brain.chat.assert_not_called()

    def test_unconfigured_gmail_does_not_connect(self):
        from core.daily_briefing import gmail_cards
        with patch('integrations.gmail_reader.load_account', return_value=None), patch(
                'integrations.gmail_reader.GmailReader') as reader:
            self.assertIn('Controles', gmail_cards()[0]['body'])
            reader.assert_not_called()

    def tearDown(self):
        self.temp.cleanup()

    def test_greeting_does_not_capture_requests_or_negations(self):
        for text in ('V, bom dia!', 'bom dia V', 'bom dia, V!', 'me dê o resumo do dia', 'inicie a rotina da manhã'):
            # Article "a" is intentionally supported for the feminine routine.
            self.assertTrue(is_briefing_request(text), text)
        for text in ('bom dia, toque música', 'não inicie o resumo do dia', 'o que faz a rotina da manhã?', 'boa tarde'):
            self.assertFalse(is_briefing_request(text), text)

    def test_snapshot_only_today_and_pending_without_mutating_data(self):
        now = self.now.timestamp()
        self.events.add('Reunião hoje', now+3600, 'appointments', now=now)
        self.events.add('Reunião amanhã', now+86400, 'appointments', now=now)
        self.lists.execute('add', 'Trabalho', 'Revisar protótipo')
        before = (self.events.path.read_bytes(), self.lists.path.read_bytes())
        cards = self.builder.build()
        self.assertEqual([c['kind'] for c in cards], ['seu dia', 'clima', 'agenda', 'pendências', 'mensagens', 'notícias'])
        agenda = cards[2]
        self.assertIn('Reunião hoje', agenda['body'])
        self.assertNotIn('Reunião amanhã', agenda['body'])
        self.assertIn('Revisar protótipo', cards[3]['body'])
        self.assertEqual(before, (self.events.path.read_bytes(), self.lists.path.read_bytes()))

    def test_provider_failure_keeps_other_topics_and_never_claims_empty_agenda(self):
        self.builder.weather = Mock(side_effect=TimeoutError)
        self.builder.initiative = Mock()
        self.builder.initiative.snapshot.side_effect = ValueError('corrupt store')
        cards = self.builder.build()
        self.assertFalse(cards[1]['ok']); self.assertFalse(cards[2]['ok'])
        self.assertIn('Não consegui', cards[2]['body'])
        self.assertEqual(cards[-1]['title'], 'Manchete de teste')

    def test_five_news_cards_are_presented(self):
        self.builder.news = lambda: [{'title': f'Notícia {i}'} for i in range(8)]
        self.assertEqual(len(self.builder.news_cards()), 5)

    def test_stale_notifications_not_presented_as_current(self):
        self.builder.messages = lambda: ([
            {'received_at': (self.now-timedelta(days=2)).isoformat(), 'body': 'Antiga'},
            {'received_at': self.now.isoformat(), 'body': 'Atual', 'app': 'Teste'},
            {'received_at': 'invalid', 'body': 'Data inválida'},
        ], {'automatic': True})
        result = self.builder.message_cards()
        self.assertIn('Atual', result['body']); self.assertNotIn('Antiga', result['body'])
        self.assertEqual(result['metric'], '1')

    def test_weather_uses_rio_and_handles_unknown_rain(self):
        response = Mock()
        response.json.return_value = {'current': {'temperature_2m': 26, 'time': '2026-09-30T08:00'},
            'daily': {'temperature_2m_min': [20], 'temperature_2m_max': [29], 'precipitation_probability_max': [None]}}
        with patch('requests.get', return_value=response) as get:
            result = rio_weather()
        self.assertEqual(get.call_args.kwargs['params']['latitude'], -22.9068)
        self.assertIn('26', result['speech']); self.assertNotIn('chuva', result['speech'])

    def test_core_dispatch_before_ai_and_preserves_structured_cards(self):
        engine = FunctionalEngine.__new__(FunctionalEngine)
        engine._append_history = Mock()
        with patch('core.daily_briefing.DailyBriefing', return_value=self.builder), patch(
                'core.briefing_music.start_music', return_value=card('música', 'Spotify', 'Música iniciada.')) as music:
            results = engine.handle('V, bom dia')
        self.assertEqual(results[0].data['kind'], 'daily_briefing')
        self.assertEqual(len(results[0].data['items']), 7)
        music.assert_called_once()
        self.assertEqual(engine._append_history.call_count, 2)


class BriefingPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = QMainWindow(); self.window.setCentralWidget(QWidget())
        self.window.resize(1180, 720)
        self.window.voice_engine = Mock()
        self.window.voice_engine.speak_tracked.side_effect = lambda text, **kw: {'state': 'queued', 'error': '', **kw}
        self.window.processing_sound = Mock()
        self.window.tts_toggle = QCheckBox(); self.window.tts_toggle.setChecked(True)
        self.window.set_state = Mock(); self.window._settle_state_after_audio = Mock()
        self.window.request_briefing_details = Mock()
        self.window.show()
        self.panel = BriefingPanel(self.window)
        self.cards = [card('agenda', 'Sua agenda', 'Compromisso às dez.'),
                      card('notícias', 'Notícia de teste', 'Texto da notícia.', url='https://example.org')]
        self.panel.start(self.cards)
        self.app.processEvents()

    def tearDown(self):
        self.panel.cancel(); self.window.close(); self.window.deleteLater()
        self.app.processEvents()

    def test_waits_for_own_audio_receipt_even_after_long_synthesis(self):
        self.panel._started = time.monotonic()-60
        with patch('ui.daily_briefing.QTimer.singleShot') as schedule:
            self.panel.poll(); schedule.assert_not_called()
            self.panel._receipt['state'] = 'speaking'
            self.panel.poll(); schedule.assert_not_called()
            self.panel._receipt['state'] = 'done'
            self.panel.poll(); schedule.assert_called_once()
            schedule.call_args.args[1]()
        self.assertEqual(self.panel.index, 1)

    def test_details_pause_and_resume_same_topic(self):
        self.panel.handle_command('me explique melhor')
        self.assertTrue(self.panel.paused)
        generation = self.panel._generation
        self.panel.explain()
        self.window.request_briefing_details.assert_called_once()
        self.assertTrue(self.panel.finish_details(generation, 'Explicação do compromisso.'))
        self.assertEqual(self.panel.body.toPlainText(), 'Explicação do compromisso.')
        self.panel._receipt['state'] = 'done'; self.panel.poll()
        self.assertEqual(self.panel.index, 0)
        self.panel.handle_command('retomar resumo')
        self.assertFalse(self.panel.paused)
        self.assertEqual(self.panel.index, 0)
        self.assertEqual(self.panel.body.toPlainText(), self.cards[0]['body'])

    def test_late_details_do_not_override_navigation_close_or_pause(self):
        for action in (lambda: self.panel.navigate(1), self.panel.close_briefing,
                       lambda: self.panel.handle_command('para')):
            self.panel.start(self.cards); self.panel.explain()
            generation = self.panel._generation
            action()
            self.window.voice_engine.speak_tracked.reset_mock()
            self.assertFalse(self.panel.finish_details(generation, 'Resposta atrasada'))
            self.window.voice_engine.speak_tracked.assert_not_called()

    def test_paused_navigation_and_boundaries_preserve_position(self):
        self.panel.toggle_pause()
        self.panel.navigate(1)
        self.assertTrue(self.panel.paused)
        generation = self.panel._generation
        self.panel.navigate(1)
        self.assertEqual(self.panel._generation, generation)

    def test_open_source_stops_explanation_audio(self):
        self.panel.present(1); self.panel.explain()
        self.panel.finish_details(self.panel._generation, 'Detalhes')
        self.window.voice_engine.stop_speaking.reset_mock()
        with patch('webbrowser.open') as opened:
            self.panel.open_source()
        opened.assert_called_once_with('https://example.org')
        self.window.voice_engine.stop_speaking.assert_called_once()

    def test_old_transition_cannot_skip_new_topic_or_restart_after_cancel(self):
        generation = self.panel._generation
        self.panel.navigate(1)
        self.panel._advance(generation)
        self.assertEqual(self.panel.index, 1)
        generation = self.panel._generation
        self.panel.cancel(); self.panel._advance(generation)
        self.assertFalse(self.panel.active)

    def test_manual_navigation_retains_visited_cards_and_pause_resumes_current(self):
        self.assertTrue(self.panel._buttons[1].isVisible())
        self.assertEqual(self.panel._receipt['state'], 'queued')
        self.panel.navigate(1); self.panel.navigate(-1)
        self.assertTrue(self.panel._buttons[1].isVisible())
        self.panel.toggle_pause()
        self.assertTrue(self.panel.paused); self.assertFalse(self.panel.timer.isActive())
        self.panel.toggle_pause()
        self.assertFalse(self.panel.paused); self.assertEqual(self.panel.index, 0)

    def test_v_introduction_then_colleague_z(self):
        from voice.briefing_cache import GREETINGS
        self.panel.start([card('seu dia', 'Bom dia', 'Resumo', speech=GREETINGS[0]), self.cards[0]])
        self.window.voice_engine.speak_tracked.assert_called_with(GREETINGS[0], profile='qwen_local')
        self.panel.navigate(1)
        self.window.voice_engine.speak_tracked.assert_called_with(self.cards[0]['speech'], profile='piper')
        self.assertIn('COLEGA Z', self.panel.voice_label.text())

    def test_voice_failure_falls_back_to_reading_time(self):
        self.panel._receipt['state'] = 'failed'
        self.panel.poll()
        self.assertTrue(self.panel._silent); self.assertEqual(self.panel.index, 0)
        self.assertIn('VOZ INDISPONÍVEL', self.panel.status.text())

    def test_revisited_topic_finishes_speech_without_advancing(self):
        self.panel.present(1, automatic=False)
        self.panel._receipt['state'] = 'done'
        self.panel.poll()
        self.window._settle_state_after_audio.assert_called()
        self.assertFalse(self.panel.timer.isActive())
        self.assertTrue(self.panel.paused)
        self.assertEqual(self.panel.index, 1)

    def test_silent_mode_and_finished_cards_remain_accessible(self):
        self.window.tts_toggle.setChecked(False)
        self.panel.start(self.cards)
        self.panel._started = time.monotonic()-30
        with patch('ui.daily_briefing.QTimer.singleShot') as schedule:
            self.panel.poll(); schedule.call_args.args[1]()
        self.panel._advance(self.panel._generation)
        self.assertFalse(self.panel.active)
        self.assertTrue(self.panel.isVisible())

    def test_plain_text_and_source_scheme_validation(self):
        self.panel.start([card('notícias', '<b>literal</b>', '<a href="file:///test">texto</a>', url='file:///test')])
        self.assertIn('<a href=', self.panel.body.toPlainText())
        self.assertFalse(self.panel.open_button.isEnabled())

    def test_scene_shows_previous_content_and_stops_animation_on_close(self):
        self.panel.navigate(1)
        self.assertTrue(self.panel._buttons[0].isVisible())
        self.assertEqual(self.panel._buttons[0].item['body'], self.cards[0]['body'])
        self.assertTrue(self.panel._buttons[1].isHidden())
        self.assertIsNotNone(self.panel._flight)
        self.panel.close_briefing()
        self.assertIsNone(self.panel._flight)
        self.assertFalse(self.panel.backdrop.timer.isActive())

    def test_card_flight_finishes_and_removes_temporary_overlay(self):
        from PySide6.QtTest import QTest
        self.panel.navigate(1)
        self.assertIsNotNone(self.panel._ghost)
        QTest.qWait(650)
        self.assertIsNone(self.panel._ghost)
        self.assertIsNone(self.panel._flight)
        self.assertEqual(self.panel.index, 1)

    def test_reference_scene_covers_window_and_restores_toolbar(self):
        bar = self.window.addToolBar('Controles')
        self.app.processEvents()
        self.panel.start(self.cards); self.app.processEvents(); self.panel.position()
        self.assertFalse(bar.isVisible())
        self.assertEqual(self.panel.geometry(), self.window.centralWidget().rect())
        self.panel.close_briefing(); self.app.processEvents()
        self.assertTrue(bar.isVisible())

    def test_news_picture_cache_and_invalid_scheme(self):
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        pixmap = QPixmap(400, 220); pixmap.fill(Qt.blue)
        self.panel._image_cache['https://example.org/image.png'] = pixmap
        item = card('notícias', 'Notícia', 'Texto', image_url='https://example.org/image.png')
        self.panel.start([item]); self.app.processEvents()
        self.assertTrue(self.panel.news_image.isVisible())
        self.assertIsNotNone(self.panel._buttons[0].picture)
        with patch.object(self.panel.network, 'get') as get:
            self.panel.start([card('notícias', 'Teste', 'Texto', image_url='file:///local.png')])
            get.assert_not_called()
        self.assertTrue(self.panel.news_image.isHidden())

    def test_controls_and_minimum_window_fit(self):
        self.assertTrue(self.panel.handle_command('proximo'))
        self.assertEqual(self.panel.index, 1)
        self.assertFalse(self.panel.handle_command('pause a musica'))
        self.assertLessEqual(self.panel.width(), self.window.centralWidget().width())
        self.assertLessEqual(self.panel.height(), self.window.centralWidget().height())


class BriefingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_result_opens_in_all_three_interfaces_and_new_command_cancels(self):
        from ui.main_window import MainWindow
        from ui.instagram_window import InstagramExperimentWindow
        from ui.amber_window import AmberExperimentWindow
        from voice.engine import VoiceEngine
        from core.functional_engine import FunctionalResult
        for window_class in (MainWindow, InstagramExperimentWindow, AmberExperimentWindow):
            with self.subTest(window=window_class.__name__):
                voice = VoiceEngine({}); voice.speak = Mock()
                with patch.object(MainWindow, '_load_mics'):
                    window = window_class(SimpleNamespace(), SimpleNamespace(skills=[]), voice, startup_greeting=False)
                window.processing_sound.set_enabled(False)
                window._initiative_timer.stop()
                window.tts_toggle.setChecked(False)
                window.show(); self.app.processEvents()
                items = [card('agenda', 'Agenda local', 'Sem compromissos.'), card('clima', 'Rio', '26 graus')]
                result = FunctionalResult(True, True, 'Resumo', 'RESUMO DO DIA', {'kind': 'daily_briefing', 'items': items})
                with patch.object(window, '_initiative_completion'), patch('ui.main_window.Path'):
                    window._command_done([result])
                self.assertTrue(window._briefing_panel.isVisible())
                with patch.object(window, '_pump_commands'):
                    window.enqueue_command('V, me explique melhor')
                detail_text, _, metadata, _ = window.pending_commands.popleft()
                from ui.main_window import CommandWorker
                worker = CommandWorker(window.orchestrator, detail_text,
                                       briefing_context=metadata['briefing_context'])
                worker.finished.connect(window._command_done)
                worker.run()
                self.assertIn('Sem compromissos.', window._briefing_panel.body.toPlainText())
                self.assertTrue(window._briefing_panel.paused)
                window.enqueue_command('V, retomar resumo')
                self.assertFalse(window._briefing_panel.paused)
                with patch.object(window, '_pump_commands') as pump:
                    window.enqueue_command('V, próximo')
                    self.assertEqual(window._briefing_panel.index, 1)
                    pump.assert_not_called()
                    window.enqueue_command('abra o navegador')
                    self.assertFalse(window._briefing_panel.isVisible())
                    self.assertFalse(window._briefing_panel.active)
                    pump.assert_called_once()
                window.close(); window.deleteLater(); self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
