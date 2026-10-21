import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import unittest
from core.briefing_preferences import defaults, validate, save, load, find_cities
from core.daily_briefing import DailyBriefing, city_weather, card
from core.briefing_news import current_news
from integrations.gmail_reader import GmailReader


class PreferenceTests(unittest.TestCase):
    def test_entrypoint_applies_saved_order_and_does_not_start_disabled_music(self):
        from core.functional_engine import FunctionalEngine
        engine = FunctionalEngine.__new__(FunctionalEngine); engine._append_history = Mock()
        settings = defaults(); settings.update(music_enabled=False, order=list(reversed(settings['order'])))
        builder = Mock(); builder.build.return_value = [card('seu dia','Olá','Olá'), card('clima','Clima','Clima'), card('agenda','Agenda','Agenda')]
        with patch('core.briefing_preferences.load', return_value=settings), patch('core.daily_briefing.DailyBriefing', return_value=builder) as factory, patch('core.briefing_music.start_music') as music:
            result = engine.handle('bom dia')[0]
        music.assert_not_called(); self.assertEqual(factory.call_args.kwargs['settings'], settings)
        self.assertEqual([c['kind'] for c in result.data['items']], ['seu dia','agenda','clima'])

    def test_music_uses_chosen_ceiling(self):
        from core.briefing_music import start_music
        command = Mock(return_value=(True, {'status': {'uri':'spotify:track:test','playing':True,'shuffle':True,'volume':.7}}))
        self.assertTrue(start_music(command, playlist_uri='', volume_limit=.25)['ok'])
        self.assertEqual(command.call_args_list[1].args[1], {'level': .25})

    def test_defaults_have_no_inferred_city(self):
        self.assertIsNone(defaults()['city'])
        with patch('requests.get') as get:
            self.assertFalse(city_weather(None)['ok'])
        get.assert_not_called()

    def test_roundtrip_and_invalid_save_preserves_previous(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'preferences.json'
            data = defaults(); data.update(news_count=7, email_count=1, music_volume=22, topics='ciência', sources=['g1'])
            save(data, path); self.assertEqual(load(path), data)
            data['order'] = ['gmail']
            with self.assertRaises(ValueError): save(data, path)
            self.assertEqual(load(path)['news_count'], 7)

    def test_validation_rejects_invalid_ranges_and_coordinates(self):
        for changes in ({'news_count': -1}, {'email_count': 11}, {'music_volume': 101}, {'sources': []}, {'sources': ['inventada']}, {'city': {'label': 'X', 'latitude': float('nan'), 'longitude': 0}}):
            with self.assertRaises(ValueError): validate(dict(defaults(), **changes))

    def test_selected_coordinates_and_timezone_are_used(self):
        response = Mock(); response.json.return_value = {'current': {'temperature_2m': 28, 'time': '2026-10-03T08:00'}, 'daily': {'temperature_2m_min': [20], 'temperature_2m_max': [30], 'precipitation_probability_max': [10]}}
        with patch('requests.get', return_value=response) as get:
            result = city_weather({'label': 'Minha cidade', 'latitude': -7.2, 'longitude': -48.2})
        self.assertIn('Minha cidade', result['body'])
        self.assertEqual(get.call_args.kwargs['params']['latitude'], -7.2)
        self.assertEqual(get.call_args.kwargs['params']['timezone'], 'auto')

    def test_city_search_preserves_disambiguating_labels(self):
        response = Mock(); response.json.return_value = {'results': [{'name': 'Palmas', 'admin1': 'Tocantins', 'country': 'Brasil', 'latitude': -10, 'longitude': -48}]}
        with patch('requests.get', return_value=response):
            self.assertEqual(find_cities('Palmas')[0]['label'], 'Palmas, Tocantins, Brasil')

    def test_disabled_news_and_email_do_not_contact_providers(self):
        settings = defaults(); settings.update(news_count=0, email_count=0, order=list(reversed(settings['order'])))
        builder = DailyBriefing(initiative=Mock(), lists=Mock(), settings=settings,
                               weather=lambda: card('clima','x','x'), news=Mock(), emails=Mock(), messages=lambda:([],{}))
        builder.agenda = lambda: card('agenda','x','x'); builder.pending = lambda: card('pendências','x','x')
        cards = builder.build(); builder.news.assert_not_called(); builder.emails.assert_not_called()
        self.assertEqual([x['kind'] for x in cards[1:]], ['mensagens','pendências','agenda','clima'])

    def test_news_count_and_filters_respect_selected_sources(self):
        items = [{'title':'Ciência brasileira', 'url':'https://example.org/1'}, {'title':'Futebol', 'url':'https://example.org/2'}]
        with tempfile.TemporaryDirectory() as folder, patch('core.briefing_news.fetch_feed', return_value=items) as fetch, patch('core.news_images.with_images', side_effect=lambda x:x), patch('core.briefing_news.preload_image', side_effect=lambda x:x):
            result = current_news(Path(folder)/'seen.json', count=1, sources=['g1'], topics='ciencia')
        self.assertEqual(len(result),1); self.assertEqual(result[0]['title'], 'Ciência brasileira')
        self.assertEqual(fetch.call_count,1); self.assertEqual(fetch.call_args.args[0][0],'g1')

    def test_no_silent_source_fallback_and_zero_emails(self):
        with patch('core.briefing_news.fetch_feed', return_value=[]), patch('web_research.fetch_news') as fallback:
            self.assertEqual(current_news(sources=['g1']), [])
        fallback.assert_not_called()
        loader=Mock(); self.assertEqual(GmailReader(account_loader=loader).morning_messages(0), []); loader.assert_not_called()

    def test_editor_saves_and_moves_cards_without_external_side_effects(self):
        from PySide6.QtWidgets import QApplication, QWidget
        from ui.briefing_editor import BriefingEditor
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'; window=QWidget(); editor=BriefingEditor(window,path)
            editor.news_count.setValue(8); editor.email_count.setValue(0); editor.music.setChecked(False)
            editor.order.setCurrentRow(1); editor.move(-1); editor.save()
            result=load(path); self.assertEqual(result['news_count'],8); self.assertEqual(result['order'][0],'clima'); self.assertFalse(result['music_enabled'])
            editor.city.addItem('Cidade salva',dict(label='Cidade salva',latitude=0,longitude=0)); editor.city.setCurrentIndex(1)
            editor.show_cities([], 'Falhou'); self.assertEqual(editor.city.currentData()['label'],'Cidade salva')
            editor.close(); window.close()
