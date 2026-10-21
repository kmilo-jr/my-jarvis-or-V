import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.routines import RoutineStore, RoutineRunner, is_work_request
from core.functional_engine import FunctionalEngine
from ui.routines import RoutinesDialog
from PySide6.QtWidgets import QApplication, QWidget


class RoutineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = RoutineStore(Path(self.temp.name) / "routines.json")
        self.cfg = self.store.defaults()
        self.cfg["folder"] = self.temp.name
        self.store.save(self.cfg)
        self.open_app = Mock(return_value="Abrindo o programa.")
        self.volume = Mock(return_value="Volume ajustado para 25%.")
        self.folder = Mock()
        self.browser = Mock(return_value=True)
        self.runner = RoutineRunner(self.store, self.open_app, self.volume, self.folder, self.browser)

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_commands_only(self):
        for text in ("V, modo trabalho", "ative o modo trabalho", "Jarvis, inicie modo trabalho por favor", "modo trabalho!"):
            self.assertTrue(is_work_request(text), text)
        for text in ("não ative modo trabalho", "o que faz o modo trabalho?", "modo música", "configure modo trabalho"):
            self.assertFalse(is_work_request(text), text)

    def test_default_actions_and_question(self):
        ok, message, data = self.runner.run()
        self.assertTrue(ok)
        self.volume.assert_called_once_with(25)
        self.folder.assert_called_once_with(self.temp.name)
        self.browser.assert_called_once()
        self.assertIn("Qual é a sua prioridade", data["speech_text"])
        self.assertEqual(len(data["steps"]), 3)

    def test_partial_failure_does_not_skip_remaining_steps(self):
        self.volume.return_value = "Não consegui controlar o volume."
        self.browser.side_effect = OSError("browser unavailable")
        ok, message, data = self.runner.run()
        self.assertFalse(ok)
        self.folder.assert_called_once()
        self.assertIn("pendências", message)
        self.assertIn("Volume", data["speech_text"])

    def test_missing_folder_does_not_open_a_file_or_stop_other_steps(self):
        self.cfg["folder"] = str(Path(self.temp.name) / "missing")
        with patch.object(self.store, "load", return_value=self.cfg):
            ok, _, data = self.runner.run()
        self.assertFalse(ok)
        self.folder.assert_not_called()
        self.browser.assert_called_once()

    def test_saved_choices_and_disabled_steps(self):
        self.cfg.update(browser_enabled=False, volume_enabled=False, folder_enabled=False,
                        ask_priority=False, apps=["discord", "discord", "bloco de notas"])
        self.store.save(self.cfg)
        ok, _, data = self.runner.run()
        self.assertTrue(ok)
        self.assertEqual(self.open_app.call_count, 2)
        self.browser.assert_not_called(); self.folder.assert_not_called(); self.volume.assert_not_called()
        self.assertNotIn("prioridade", data["speech_text"])

    def test_invalid_settings_do_not_overwrite_saved_routine(self):
        original = self.store.path.read_text(encoding="utf-8")
        for change in ({"volume": 101}, {"apps": ["powershell -command anything"]}, {"folder": "relative"}):
            with self.assertRaises(ValueError):
                self.store.save(dict(self.cfg, **change))
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), original)

    def test_core_dispatch_does_not_need_ai(self):
        engine = FunctionalEngine.__new__(FunctionalEngine)
        engine._append_history = Mock()
        with patch("core.routines.RoutineRunner", return_value=self.runner):
            results = engine.handle("V, modo trabalho")
        self.assertTrue(results[0].ok)
        self.assertEqual(results[0].skill, "MODO TRABALHO")
        self.assertEqual(engine._append_history.call_count, 2)

    def test_dialog_save_and_run_dispatch(self):
        parent = QWidget(); parent.enqueue_command = Mock()
        dialog = RoutinesDialog(parent, self.store)
        dialog.volume.setValue(35)
        self.assertTrue(dialog.save())
        self.assertEqual(self.store.load()["volume"], 35)
        parent.enqueue_command.assert_not_called()
        dialog.run()
        parent.enqueue_command.assert_called_once_with("modo trabalho", source="text")
        dialog.close(); parent.close()


if __name__ == "__main__":
    unittest.main()
