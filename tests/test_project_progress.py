import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from core.project_progress import ProjectStore
from core.functional_engine import FunctionalEngine
from core.failure_help import explain


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = ProjectStore(Path(self.folder.name) / 'projects.json')

    def test_checkpoint_survives_restart_and_can_be_corrected_and_forgotten(self):
        self.store.command('criar projeto Meu V')
        self.store.command('concluído: câmera')
        self.store.command('pendente: voz')
        self.store.command('próximo passo: testar frase longa')
        other = ProjectStore(self.store.path)
        self.assertIn('testar frase longa', other.command('continua de onde paramos'))
        other.command('pendente: notificações')
        self.assertEqual(other.active()['pending'], 'notificações')
        other.command('esquecer projeto Meu V')
        self.assertIsNone(other.active())
        self.assertNotIn('Meu V', other.path.read_text())

    def test_creating_existing_project_does_not_erase_checkpoint(self):
        self.store.save('Câmera', next_step='validar')
        self.store.command('criar projeto camera')
        self.assertEqual(self.store.active()['next'], 'validar')
        self.store.save('Outro')
        self.store.command('retomar projeto Câmera')
        self.assertEqual(self.store.active()['next'], 'validar')

    def test_corrupt_file_and_failed_save_preserve_existing_bytes(self):
        self.store.save('V', done='feito')
        before = self.store.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                self.store.save('V', done='novo')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.store.path.write_text('{broken')
        with self.assertRaises(ValueError):
            self.store.save('Novo')
        self.assertEqual(self.store.path.read_text(), '{broken')

    def test_commands_work_without_ai_and_clear_stale_context(self):
        engine = FunctionalEngine.__new__(FunctionalEngine)
        engine.projects = self.store
        engine.history = []
        engine.last_tool_context = []
        engine._append_history = Mock()
        engine.reset_memory_context = Mock()
        engine.handle('V, criar projeto Revisão')
        engine.handle('V, próximo passo: validar áudio')
        result = engine.handle('V, continua de onde paramos')[0]
        self.assertIn('validar áudio', result.message)
        engine.reset_memory_context.assert_called()
        self.assertEqual(engine._project_context()['record']['next'], 'validar áudio')

    def test_invalid_names_and_large_fields_rejected(self):
        for name, done in [('', ''), ('x' * 101, ''), ('V', 'x' * 3001)]:
            with self.assertRaises(ValueError):
                self.store.save(name, done)


class FailureTests(unittest.TestCase):
    def test_raw_response_never_reaches_display_or_speech(self):
        report = explain('Gemini HTTP 401: secret-token private prompt https://private.test | Groq HTTP 403')
        self.assertIn('credencial', report['message'])
        self.assertIn('negou acesso', report['message'])
        self.assertNotIn('secret-token', str(report))
        self.assertNotIn('private', str(report))

    def test_engine_retains_safe_last_failure(self):
        engine = FunctionalEngine.__new__(FunctionalEngine)
        engine.brain = Mock(last_error='Groq: HTTP 429 private')
        result = engine._brain_unavailable_result()
        self.assertFalse(result.ok)
        self.assertIn('limite de uso', result.message)
        self.assertNotIn('private', result.message)
        self.assertEqual(result.data['speech_text'], engine.last_failure['speech_text'])
