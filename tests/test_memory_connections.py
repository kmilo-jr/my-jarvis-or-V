import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from contextlib import contextmanager
import requests
from brain.memory_store import PersistentMemoryStore
from core.functional_engine import FunctionalEngine
from core.connections import probe


class MemoryTests(unittest.TestCase):
    def test_capacity_never_evicts_saved_facts(self):
        store = PersistentMemoryStore(self.path, max_items=10)
        for i in range(10): store.remember(f'Fato {i}')
        with self.assertRaisesRegex(ValueError, 'nada foi apagado'):
            store.remember('Novo fato')
        self.assertEqual(PersistentMemoryStore(self.path).get_memories(), [f'Fato {i}' for i in range(10)])

    def test_loading_above_limit_preserves_all_items_when_editing(self):
        for i in range(12): self.store.remember(f'Fato {i}')
        store = PersistentMemoryStore(self.path, max_items=10)
        self.assertEqual(store.count(),12)
        store.update(1,'Fato corrigido')
        self.assertEqual(PersistentMemoryStore(self.path).count(),12)
    def test_corrupt_file_is_not_overwritten_by_new_memory(self):
        self.path.write_text('{broken', encoding='utf-8')
        store = PersistentMemoryStore(self.path)
        with self.assertRaisesRegex(ValueError, 'preservar'):
            store.remember('nova informação')
        self.assertEqual(self.path.read_text(encoding='utf-8'), '{broken')
        self.assertEqual(store.count(), 0)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'memory.json'
        self.store = PersistentMemoryStore(self.path)

    def tearDown(self): self.temp.cleanup()

    def test_migration_edit_forget_and_reload(self):
        self.path.write_text(json.dumps({'version': 1, 'memories': [{'id': 7, 'text': 'Meu PC antigo', 'created_at': 'old'}]}), encoding='utf-8')
        store = PersistentMemoryStore(self.path)
        store.update(7, 'Meu PC tem 16 GB', 'equipamentos')
        loaded = PersistentMemoryStore(self.path)
        self.assertEqual(loaded.items()[0]['category'], 'equipamentos')
        self.assertEqual(loaded.items()[0]['created_at'], 'old')
        loaded.forget_id(7)
        self.assertEqual(PersistentMemoryStore(self.path).get_memories(), [])

    def test_old_relevant_fact_survives_recent_unrelated_items(self):
        self.store.remember('Minha GPU é GTX 1650', category='equipamentos')
        for i in range(35): self.store.remember(f'Receita favorita número {i}')
        result = self.store.relevant('GPU equipamentos', limit=3)
        self.assertIn('GTX 1650', result[0])
        self.assertLessEqual(len(result), 3)

    def test_failed_disk_writes_do_not_change_memory(self):
        item = self.store.remember('original')
        with patch.object(self.store, '_save', side_effect=OSError('disk')):
            for fn in (lambda: self.store.update(item.id, 'changed'), lambda: self.store.forget_id(item.id), lambda: self.store.remember('new'), lambda: self.store.forget('original')):
                with self.assertRaises(OSError): fn()
                self.assertEqual(self.store.get_memories(), ['original'])

    def test_ambiguous_forget_does_not_remove_a_fact(self):
        self.store.remember('PC da sala'); self.store.remember('PC do quarto')
        self.assertIsNone(self.store.forget('PC'))
        self.assertEqual(self.store.count(), 2)

    def test_deleted_id_is_not_reused_after_restart(self):
        item = self.store.remember('old')
        self.store.forget_id(item.id)
        new = PersistentMemoryStore(self.path).remember('new')
        self.assertGreater(new.id, item.id)

    def test_commands_correct_and_clear_stale_context(self):
        engine = FunctionalEngine.__new__(FunctionalEngine)
        engine.memory = self.store; engine.history = [{'role': 'user', 'content': 'old'}]; engine.last_tool_context = ['old']
        result = engine._memory_command('lembre equipamentos: minha GPU é GTX 1650')
        self.assertTrue(result[0].ok)
        self.assertEqual(self.store.items()[0]['category'], 'equipamentos')
        self.assertTrue(engine._memory_command('corrija memória 1 para minha GPU é RTX 4060')[0].ok)
        self.assertEqual(engine.history, [])
        self.assertEqual(engine.last_tool_context, [])
        self.assertTrue(engine._memory_command('esqueça memória 1')[0].ok)
        self.assertEqual(self.store.count(), 0)


class ConnectionTests(unittest.TestCase):
    def test_not_configured_does_not_probe(self):
        with patch('core.connections.configured', return_value=False), patch('core.connections.http_json') as http:
            result = probe('IA · Gemini')
        http.assert_not_called(); self.assertEqual(result.state, 'Não configurado')
        self.assertTrue(result.checked_at); self.assertTrue(result.next_action)

    def test_http_error_does_not_expose_key(self):
        response = requests.Response(); response.status_code = 401
        error = requests.HTTPError('secret-key-in-url', response=response)
        brain = SimpleNamespace(gemini_base_url='https://example.com', gemini_model='test', gemini_key='secret')
        with patch('core.connections.configured', return_value=True), patch('core.connections.http_json', side_effect=error):
            result = probe('IA · Gemini', brain)
        self.assertEqual(result.state, 'Indisponível'); self.assertIn('401', result.detail)
        self.assertNotIn('secret', str(result))

    def test_ollama_model_missing_is_not_connected(self):
        brain = SimpleNamespace(base_url='http://localhost', model='missing')
        with patch('core.connections.configured', return_value=True), patch('core.connections.http_json', return_value={'models': []}):
            self.assertEqual(probe('IA · Ollama', brain).state, 'Indisponível')

    def test_gmail_auth_noop_without_reading_messages(self):
        client = Mock(); client.noop.return_value = ('OK', [])
        @contextmanager
        def connection(): yield client, 'private', []
        with patch('core.connections.configured', return_value=True), patch('integrations.gmail_reader.GmailReader') as reader:
            reader.return_value.connection = connection
            self.assertEqual(probe('Gmail').state, 'Conectado')
        client.noop.assert_called_once(); client.uid.assert_not_called()

    def test_spotify_stale_heartbeat_requires_real_api_check(self):
        with patch('core.connections.configured', return_value=True), patch('spotify_bridge.health', return_value=(200, {'extension_seen': True, 'extension_age_s': 40})), patch('spotify_api.SpotifyClient') as client:
            client.return_value.devices.side_effect = RuntimeError('token secret')
            result = probe('Spotify')
        self.assertEqual(result.state, 'Indisponível'); self.assertNotIn('token secret', result.detail)

    def test_remote_live_endpoint_required(self):
        with patch('core.connections.configured', return_value=True), patch('core.connections.http_json', side_effect=requests.Timeout):
            result = probe('Remoto', remote={'server': True, 'url': 'http://192.168.1.2:8765'})
        self.assertEqual(result.state, 'Indisponível')


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_memory_panel_edits_and_deletes_selected_id(self):
        from PySide6.QtWidgets import QWidget
        from ui.memory_center import MemoryCenter
        with tempfile.TemporaryDirectory() as folder:
            store = PersistentMemoryStore(Path(folder)/'memory.json')
            window = QWidget(); window.command_thread = None
            window.orchestrator = SimpleNamespace(memory=store, reset_memory_context=Mock())
            panel = MemoryCenter(window); panel.text.setPlainText('Prefiro respostas curtas'); panel.category.setCurrentIndex(1); panel.save()
            self.assertEqual(store.count(), 1)
            panel.list.setCurrentRow(0); panel.text.setPlainText('Prefiro respostas detalhadas'); panel.save()
            self.assertEqual(store.get_memories(), ['Prefiro respostas detalhadas'])
            panel.list.setCurrentRow(0); panel.forget(); self.assertEqual(store.count(), 0)
            panel.close(); window.close()

    def test_connection_results_are_visible(self):
        from PySide6.QtWidgets import QWidget
        from ui.connections_center import ConnectionsCenter
        window = QWidget(); window.orchestrator = SimpleNamespace(brain=None)
        with patch('ui.connections_center.configured', return_value=False):
            panel = ConnectionsCenter(window)
        with patch('core.connections.configured', return_value=False):
            panel.show_result(probe('Gmail'))
        self.assertEqual(panel.table.item(0, 2).text(), 'Não configurado')
        self.assertIn('senha', panel.table.item(0, 5).text())
        panel.close(); window.close()

    def test_slow_probe_keeps_ui_responsive_and_prevents_duplicate_tests(self):
        import threading
        import time
        from PySide6.QtWidgets import QWidget
        from PySide6.QtTest import QTest
        from ui.connections_center import ConnectionsCenter
        from core.connections import ConnectionResult
        window = QWidget(); window.orchestrator = SimpleNamespace(brain=None)
        with patch('ui.connections_center.configured', return_value=False):
            panel = ConnectionsCenter(window)
        release = threading.Event()
        def slow(*args):
            release.wait(2)
            return ConnectionResult('Gmail', True, 'Conectado', '2026-10-03T10:00:00-03:00', 'OK', 'Pronto')
        with patch('ui.connections_center.probe', side_effect=slow) as check:
            panel.start(['Gmail']); panel.start(['Gmail'])
            self.assertTrue(panel.running); self.assertFalse(panel.test_button.isEnabled())
            self.assertEqual(panel.table.item(0, 2).text(), 'Testando…')
            release.set()
            deadline = time.monotonic()+2
            while panel.running and time.monotonic() < deadline: QTest.qWait(10)
            self.assertFalse(panel.running); check.assert_called_once()
            self.assertEqual(panel.table.item(0, 2).text(), 'Conectado')
        panel.close(); window.close()
