from datetime import datetime
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from core.functional_engine import FunctionalEngine
from core.initiative import InitiativeStore
from core.personal_assistant import ListStore, PersonalAssistant, parse_when, merge_time_reply
from core.tool_router import ToolRouter


class ReminderConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = InitiativeStore(self.root / 'events.json')
        self.lists = ListStore(self.root / 'lists.json')
        self.now = datetime(2026, 9, 29, 13).timestamp()
        self.service = PersonalAssistant(self.store, self.lists, clock=lambda: self.now)
        self.engine = FunctionalEngine(memory_store=SimpleNamespace(get_memories=lambda: []), initiative_store=self.store, list_store=self.lists)
        self.engine.history = []
        self.engine.history_path = self.root / 'history.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_reported_failed_conversation(self):
        first = self.engine.handle('me lembre quando for 14:#')
        self.assertFalse(first[0].ok)
        second = self.engine.handle('hoje daqui 30 minutos')
        self.assertTrue(second[0].ok, second[0].message)
        events = self.store.snapshot()['events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['title'], 'Aviso de horário')
        self.assertNotIn('14:#', events[0]['title'])

    def test_avise_and_clock_only_reminder_have_meaningful_titles(self):
        for request in ('avise quando for 14:30', 'me avise quando der 14:30', 'me lembre quando for 14:00 horas', 'pode me avisar às 14h por favor?'):
            with self.subTest(request=request):
                self.assertEqual(ToolRouter().route(request).calls[0].name, 'assistant.local')
                self.service.execute(request)
                event = self.store.snapshot()['events'][-1]
                self.assertEqual(event['title'], 'Aviso de horário')
                self.assertEqual(datetime.fromtimestamp(event['due']).hour, 14)

    def test_relative_natural_phrases(self):
        for phrase, seconds in [('hoje daqui 30 minutos', 1800), ('daqui a 30 minutos', 1800), ('em seis minutos', 360), ('daqui meia hora', 1800), ('em vinte e cinco minutos', 1500), ('daqui uma hora e meia', 5400), ('em 1 hora e 30 minutos', 5400)]:
            due, _ = parse_when('me lembre de revisar ' + phrase, self.now)
            self.assertEqual(due, self.now + seconds, phrase)

    def test_short_duration_reply_completes_existing_reminder(self):
        self.engine.handle('me lembre de beber água')
        result = self.engine.handle('30 minutos')
        self.assertTrue(result[0].ok, result[0].message)
        self.assertEqual(self.store.snapshot()['events'][0]['title'], 'beber água')

    def test_spoken_and_spaced_hours(self):
        for phrase, hour, minute in [('às duas e meia da tarde', 14, 30), ('às vinte e uma', 21, 0), ('às vinte e uma e quinze', 21, 15), ('14 horas', 14, 0), ('às catorze', 14, 0)]:
            due, _ = parse_when('me lembre de revisar ' + phrase, self.now)
            got = datetime.fromtimestamp(due)
            self.assertEqual((got.hour, got.minute), (hour, minute), phrase)

    def test_correction_keeps_subject_but_replaces_invalid_time(self):
        request = merge_time_reply('me lembre de beber água amanhã às 25h', 'hoje daqui 30 minutos')
        self.service.execute(request)
        event = self.store.snapshot()['events'][0]
        self.assertEqual(event['title'], 'beber água')
        self.assertEqual(event['due'], self.now + 1800)

    def test_unrelated_reply_does_not_create_reminder(self):
        self.engine.handle('me lembre de revisar o projeto')
        self.engine.handle('olá')
        self.assertEqual(self.store.snapshot()['events'], [])

    def test_ambiguous_relative_date_not_silently_ignored(self):
        with self.assertRaises(ValueError):
            parse_when('me lembre amanhã em 30 minutos', self.now)


if __name__ == '__main__':
    unittest.main()
