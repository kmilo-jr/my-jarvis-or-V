from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from core.personal_assistant import PersonalAssistant, ListStore, parse_when
from core.initiative import InitiativeStore
from core.functional_engine import FunctionalEngine
from core.tool_router import ToolRouter
from core.tool_system import ToolSpec, ToolCall, ToolExecution
from core.system_watch import SystemWatch


class PersonalAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = InitiativeStore(self.root / 'initiative.json')
        self.lists = ListStore(self.root / 'lists.json')
        self.now = datetime(2026, 9, 29, 14).timestamp()
        self.service = PersonalAssistant(self.store, self.lists, clock=lambda: self.now)

    def tearDown(self):
        self.temp.cleanup()

    def engine(self):
        e = FunctionalEngine(memory_store=SimpleNamespace(get_memories=lambda: []), initiative_store=self.store, list_store=self.lists)
        e.history_path = self.root / 'history.json'
        e.history = []
        return e

    def test_lists_persist_accents_deduplicate_complete_and_remove(self):
        self.service.execute('adicione café à lista compras')
        self.service.execute('adicione café à lista compras')
        self.service.execute('adicione pão à lista compras')
        self.service.execute('conclua café na lista compras')
        self.service.execute('remova pão da lista compras')
        reopened = PersonalAssistant(self.store, ListStore(self.lists.path))
        self.assertIn('✓ café', reopened.execute('mostre a lista compras'))
        self.assertEqual(len(self.lists.load()['lists']['compras']['items']), 1)

    def test_corrupt_lists_preserved(self):
        self.lists.path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.service.execute('crie a lista tarefas')
        self.assertEqual(self.lists.path.read_text(), '{broken')

    def test_dates_and_missing_time(self):
        due, _ = parse_when('me lembre de revisar amanhã às 15h30', self.now)
        self.assertEqual(datetime.fromtimestamp(due), datetime(2026, 9, 30, 15, 30))
        due, _ = parse_when('alarme às 10h', self.now)
        self.assertEqual(datetime.fromtimestamp(due), datetime(2026, 9, 30, 10))
        due, _ = parse_when('alarme em dez minutos', self.now)
        self.assertEqual(due, self.now + 600)
        for text in ('alarme hoje às 10h', 'alarme amanhã', 'alarme às 25h', 'alarme 31/02 às 15h', 'alarme sexta às 15h', 'alarme às 15:999'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_when(text, self.now)

    def test_reminder_agenda_and_unique_cancellation(self):
        self.service.execute('me lembre de revisar o projeto amanhã às 15h')
        event = self.store.snapshot()['events'][0]
        self.assertEqual(event['title'], 'revisar o projeto')
        self.assertIn('revisar o projeto', self.service.execute('agenda amanhã'))
        self.assertIn('Nenhum', self.service.execute('agenda hoje'))
        self.service.execute('cancele o lembrete ' + event['id'][:8])
        self.assertEqual(self.store.snapshot()['events'][0]['state'], 'cancelled')

    def test_appointment_stays_in_agenda_after_early_notice(self):
        self.store.update_settings({'quiet_enabled': False})
        self.service.execute('agende um compromisso reunião amanhã às 15h')
        event = self.store.snapshot()['events'][0]
        self.assertIsNone(self.store.next_notice(busy=False, now=event['due'] - 601))
        self.assertEqual(self.store.next_notice(busy=False, now=event['due'] - 600)['id'], event['id'])
        self.store.delivered(event['id'], now=event['due'] - 600)
        self.assertIn('reunião', self.service.execute('agenda amanhã'))
        self.service.execute('cancele o compromisso ' + event['id'][:8])
        self.assertEqual(self.store.snapshot()['events'][0]['state'], 'cancelled')

    def test_alarm_bypasses_busy_and_quiet_but_respects_pause_and_disable(self):
        self.service.execute('crie um alarme em 1 minuto')
        self.store.update_settings({'quiet_start': 0, 'quiet_end': 0, 'voice': True})
        event = self.store.next_notice(busy=True, now=self.now + 60)
        self.assertEqual(event['kind'], 'alarms')
        self.assertFalse(event['voice'])
        self.store.update_settings({'paused_until': self.now + 120})
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now + 60))
        self.store.update_settings({'paused_until': 0, 'alarms': False})
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now + 60))

    def test_no_fake_recurring_schedule(self):
        with self.assertRaises(ValueError):
            self.service.execute('crie um alarme todo dia às 8h')
        self.assertEqual(self.store.snapshot()['events'], [])

    def test_natural_appointment_and_agenda_alias(self):
        self.assertTrue(ToolRouter().route('agende reunião amanhã às 15h').calls)
        self.service.execute('agende reunião amanhã às 15h')
        self.assertEqual(self.store.snapshot()['events'][0]['title'], 'reunião')
        self.assertIn('reunião', self.service.execute('minha agenda'))

    def test_invalid_volume_and_ambiguous_sequence_do_not_execute(self):
        e = self.engine()
        self.assertFalse(e.tools.validate(ToolCall('audio.set_volume', {'value': 200}), SimpleNamespace(user_text='volume 200'))[0])
        self.assertFalse(e.tools.validate(ToolCall('audio.set_volume'), SimpleNamespace(user_text='volume'))[0])
        self.assertEqual(ToolRouter().route('abra calculadora; algo indefinido').calls[0].name, 'request.clarify')

    def test_monitor_move_validates_target_without_touching_desktop(self):
        from core.desktop_controls import move_active_window
        screen = {'Work': (1920, 0, 3200, 720)}
        with patch('core.desktop_controls.monitors', return_value=[screen]), patch('win32gui.GetForegroundWindow', return_value=99), \
             patch('win32gui.GetDesktopWindow', return_value=1), patch('win32gui.GetWindowPlacement', return_value=(0, 1)), \
             patch('win32gui.GetWindowRect', return_value=(0, 0, 1600, 900)), patch('win32gui.SetWindowPos') as move:
            with self.assertRaises(ValueError):
                move_active_window(2)
            move.assert_not_called()
            move_active_window(1)
            self.assertEqual(move.call_args.args[2:6], (1920, 0, 1280, 720))

    def test_routing_and_no_accidental_capture_of_conversation(self):
        r = ToolRouter()
        self.assertEqual(r.route('V, me lembre de beber água em 10 minutos').calls[0].name, 'assistant.local')
        self.assertEqual(r.route('crie um alarme às 8h no iPhone').calls[0].name, 'mobile.alarm')
        self.assertEqual(r.route('explique listas em Python').mode, 'chat')
        self.assertEqual(r.route('mova a janela para o monitor 2').calls[0].name, 'window.move_monitor')
        self.assertEqual(r.route('feche a janela').calls[0].name, 'window.close')
        self.assertEqual(r.route('mostre os monitores').calls[0].name, 'monitor.list')

    def test_core_reminder_and_missing_time_followup_without_ai(self):
        e = self.engine()
        first = e.handle('V, me lembre de revisar o projeto')
        self.assertFalse(first[0].ok)
        self.assertEqual(self.store.snapshot()['events'], [])
        second = e.handle('amanhã às 15h')
        self.assertTrue(second[0].ok, second[0].message)
        self.assertEqual(self.store.snapshot()['events'][0]['title'], 'revisar o projeto')
        self.assertIn('revisar', e.handle('agenda de amanhã')[0].message)
        self.assertIn('Nenhum', e.handle('e hoje?')[0].message)

    def test_chain_all_steps_and_failure_stops_remaining(self):
        r = ToolRouter().route('abra o navegador e ajuste o volume para 25 e depois mostre os monitores')
        self.assertEqual([x.name for x in r.calls], ['app.open', 'audio.set_volume', 'monitor.list'])
        e = self.engine()
        first, second, third = Mock(return_value=ToolExecution('one', True, 'Feito')), Mock(return_value=ToolExecution('two', False, 'Falhou')), Mock()
        for name, handler in [('one', first), ('two', second), ('three', third)]:
            e.tools.register(ToolSpec(name, '', {}, handler))
        with patch('core.functional_engine.save_tool_trace'):
            results = e._execute_tool_calls([ToolCall(x) for x in ('one', 'two', 'three')], 'pedido', 'test')
        first.assert_called_once(); second.assert_called_once(); third.assert_not_called()
        self.assertTrue(results[2].data['skipped'])

    def test_invalid_later_step_blocks_whole_chain_and_limit_does_not_truncate(self):
        e = self.engine(); action = Mock()
        e.tools.register(ToolSpec('one', '', {}, action))
        with patch('core.functional_engine.save_tool_trace'):
            result = e._execute_tool_calls([ToolCall('one'), ToolCall('missing')], 'pedido', 'test')
        action.assert_not_called()
        self.assertTrue(all(not r.ok for r in result))
        route = ToolRouter().route('; '.join(['abra calculadora'] * 9))
        self.assertEqual(route.calls[0].name, 'request.limit')

    def test_sustained_system_alert_recovery_and_restart(self):
        watch = SystemWatch(self.store)
        for offset in range(0, 121, 15):
            watch.observe({'cpu': 99}, self.now + offset)
        self.assertEqual(len(self.store.snapshot()['events']), 1)
        watch.observe({'cpu': 99}, self.now + 135)
        self.assertEqual(len(self.store.snapshot()['events']), 1)
        restarted = SystemWatch(self.store)
        restarted.observe({'cpu': 10}, self.now + 150)
        self.assertEqual(self.store.snapshot()['events'][0]['state'], 'cancelled')

    def test_system_spike_and_sleep_do_not_count_as_sustained(self):
        watch = SystemWatch(self.store)
        watch.observe({'cpu': 99}, self.now)
        watch.observe({'cpu': 99}, self.now + 200)
        watch.observe({'cpu': 5}, self.now + 215)
        self.assertEqual(self.store.snapshot()['events'], [])


if __name__ == '__main__':
    unittest.main()
