import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from voice.engine import VoiceEngine
from voice.preferences import VOICE_PRESETS, save_preferences, save_xtts_voice, voice_preferences
from voice.task_feedback import progress_label
from core.functional_engine import FunctionalEngine, FunctionalResult
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from ui.task_interaction import TaskInteractionDialog


class VoiceLatencyTests(unittest.TestCase):
    def test_saving_offline_voice_preserves_sample_without_reactivating_xtts(self):
        engine = VoiceEngine({'tts_profile': 'windows_sapi', 'tts_xtts_voice': 'v_alt', 'tts_xtts_enabled': False})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text(json.dumps({'voice': engine.config}), encoding='utf-8')
            save_preferences(engine, 100, False, False, path, xtts_voice='windows')
            self.assertEqual(engine.config['tts_profile'], 'windows_sapi')
            self.assertEqual(engine.config['tts_xtts_voice'], 'v_alt')
            self.assertFalse(engine.config['tts_xtts_enabled'])
            with patch.object(engine, '_load_xtts') as load:
                self.assertFalse(engine.warmup_tts())
            load.assert_not_called()

    def test_first_chunk_small_later_sentences_combined(self):
        engine = VoiceEngine({"tts_chunk_max_chars": 240, "tts_first_chunk_chars": 100})
        text = "Primeira frase curta. " + "Uma outra frase completa para continuar a explicação. " * 8
        chunks = engine._split_tts_chunks(text)
        self.assertLessEqual(len(chunks[0]), 100)
        self.assertGreater(len(chunks[1]), 100)
        self.assertTrue(all(len(c) <= 240 for c in chunks))
        self.assertEqual(" ".join(chunks), text.strip())

    def test_cache_skips_network_but_voice_settings_invalidate_it(self):
        engine = VoiceEngine({"tts_eleven_voice_id": "test", "tts_eleven_model": "test"})
        engine._eleven_session = Mock()
        engine._eleven_session.post.return_value = SimpleNamespace(status_code=200, content=b"fake-audio")
        paths = []
        try:
            with patch("voice.eleven_auth.load_key", return_value="test-only"):
                paths.append(engine._synthesize_eleven_file("Abrindo o navegador."))
                paths.append(engine._synthesize_eleven_file("Abrindo o navegador."))
                self.assertNotEqual(paths[0], paths[1])
                self.assertEqual(Path(paths[0]).read_bytes(), Path(paths[1]).read_bytes())
                self.assertEqual(engine._eleven_session.post.call_count, 1)
                engine.config["tts_eleven_speed"] = 0.95
                paths.append(engine._synthesize_eleven_file("Abrindo o navegador."))
                self.assertEqual(engine._eleven_session.post.call_count, 2)
        finally:
            for path in paths:
                if path: Path(path).unlink(missing_ok=True)

    def test_preferences_preserve_voice_identity_and_other_settings(self):
        engine = VoiceEngine({"tts_eleven_voice_id": "my-voice"})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"voice": engine.config, "ui": {"theme": "blue"}}), encoding="utf-8")
            save_preferences(engine, 100, False, False, path)
            cfg = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(cfg["ui"], {"theme": "blue"})
            self.assertEqual(engine.config["tts_eleven_voice_id"], "my-voice")
            self.assertEqual(engine._eleven_voice_settings("Oi.")["speed"], 1.0)

    def test_voice_presets_change_style_without_changing_voice_id(self):
        jarvis = voice_preferences(98, True, False, "jarvis")
        ultron = voice_preferences(91, False, False, "ultron")
        self.assertEqual(jarvis["tts_voice_preset"], "jarvis")
        self.assertEqual(ultron["tts_voice_preset"], "ultron")
        self.assertLess(float(ultron["tts_eleven_speed"]), float(jarvis["tts_eleven_speed"]))
        self.assertLess(int(ultron["tts_short_pitch"].replace("Hz", "")), int(jarvis["tts_short_pitch"].replace("Hz", "")))
        self.assertEqual(VOICE_PRESETS["jarvis"]["label"], "Jarvis · elegante e controlado")
        prime = voice_preferences(99, True, False, "v_prime")
        self.assertEqual(prime["tts_voice_preset"], "v_prime")
        self.assertAlmostEqual(prime["tts_eleven_speed"], 0.99)
        self.assertEqual(prime["tts_edge_pitch"], "-16Hz")

    def test_xtts_sample_selection_is_persisted_without_overwriting_other_voice_settings(self):
        engine = VoiceEngine({"tts_eleven_voice_id": "keep-me", "tts_xtts_voice": "v_prime"})
        previous = engine._speech_generation
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps({"voice": engine.config, "ui": {"theme": "blue"}}), encoding="utf-8")
            self.assertEqual(save_xtts_voice(engine, "v_alt", path), "v_alt")
            cfg = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(cfg["voice"]["tts_xtts_voice"], "v_alt")
            self.assertEqual(cfg["voice"]["tts_eleven_voice_id"], "keep-me")
            self.assertEqual(cfg["ui"], {"theme": "blue"})
            self.assertTrue(previous.is_set())
            self.assertFalse(engine._speech_generation.is_set())

    def test_spoken_markdown_keeps_link_label(self):
        self.assertEqual(VoiceEngine._prepare_spoken_text("# Resultado\n1. Abra [o site](https://example.org)."), "Resultado Abra o site.")

    def test_fast_actions_preserve_facts_without_ai(self):
        engine = FunctionalEngine.__new__(FunctionalEngine)
        results = [FunctionalResult(True, True, "Abrindo o navegador.", "APP.OPEN"), FunctionalResult(True, True, "Volume ajustado para 25%.", "AUDIO.SET_VOLUME")]
        answer = engine._fast_local_presentation("pedido", results)[0]
        self.assertIn("Abrindo o navegador.", answer.message)
        self.assertIn("25%", answer.data["speech_text"])
        self.assertNotIn("Já abri", answer.message)

    def test_human_progress_has_real_step_numbers(self):
        self.assertEqual(progress_label("TOOL 2/3 • app.open"), "Etapa 2 de 3 · Vou tentar abrir agora.")
        self.assertNotIn("AI BRAIN", progress_label("AI BRAIN • entendendo intenção"))


class TaskInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.voice = VoiceEngine({}); self.voice.speak = Mock()
        with patch.object(MainWindow, "_load_mics"):
            self.w = InstagramExperimentWindow(SimpleNamespace(), SimpleNamespace(skills=[]), self.voice, startup_greeting=False)
        self.w.processing_sound.set_enabled(False)

    def tearDown(self): self.w.close(); self.w.deleteLater()

    def test_dialog_displays_offline_voice_and_saves_the_same_engine(self):
        self.voice.config.update(tts_profile='windows_sapi', tts_xtts_enabled=False, tts_xtts_voice='v_alt')
        dialog = TaskInteractionDialog(self.w)
        self.assertEqual(dialog.xtts_voice.currentData(), 'windows')
        with patch('ui.task_interaction.save_preferences') as save:
            self.assertTrue(dialog.save())
        self.assertEqual(save.call_args.kwargs['xtts_voice'], 'windows')
        dialog.close()

    def test_sample_selectors_stay_in_sync_in_both_directions(self):
        from PySide6.QtWidgets import QComboBox
        self.w.xtts_voice_combo = QComboBox(self.w)
        self.w.xtts_voice_combo.addItem('Prime', 'v_prime')
        self.w.xtts_voice_combo.addItem('Alt', 'v_alt')
        self.w.xtts_voice_combo.currentIndexChanged.connect(self.w._change_xtts_voice)
        self.voice.config.update(tts_xtts_speed=1.0, tts_xtts_speed_alt=1.08)
        dialog = TaskInteractionDialog(self.w)
        self.w._task_dialog = dialog
        dialog.show()
        def save(engine, key):
            engine.config['tts_xtts_voice'] = key
        with patch('ui.task_interaction.save_xtts_voice', side_effect=save), \
             patch('voice.preferences.save_xtts_voice', side_effect=save):
            dialog.xtts_voice.setCurrentIndex(1)
            self.assertEqual(self.w.xtts_voice_combo.currentData(), 'v_alt')
            self.assertEqual(self.voice.config['tts_xtts_voice'], 'v_alt')
            self.assertEqual(dialog.speed.value(), 108)
            self.w.xtts_voice_combo.setCurrentIndex(0)
            self.assertEqual(dialog.xtts_voice.currentData(), 'v_prime')
            self.assertEqual(dialog.speed.value(), 100)
        dialog.close()

    def test_remove_queued_request_does_not_touch_active_task(self):
        self.w._active_request = "pedido atual"
        self.w.pending_commands.extend([("primeiro", "text", {}, 1.0), ("segundo", "text", {}, 2.0)])
        dialog = TaskInteractionDialog(self.w)
        dialog.queue.setCurrentRow(0); dialog.remove()
        self.assertEqual(self.w.pending_commands[0][0], "segundo")
        self.assertEqual(self.w._active_request, "pedido atual")
        dialog.close()

    def test_repeat_does_not_execute_command_again(self):
        self.w._last_response_spoken = "Abrindo o navegador."
        with patch.object(self.w, "_pump_commands") as pump:
            self.w.enqueue_command("V, repita a última resposta")
        pump.assert_not_called()
        self.voice.speak.assert_called_once_with("Abrindo o navegador.")

    def test_progress_voice_can_be_disabled(self):
        self.w._command_complete = False
        self.w._progress_message = "TOOL 1/1 • app.open"
        self.voice.config["task_progress_voice"] = False
        self.w._speak_action_progress(0, self.w._progress_message, "Vou tentar abrir agora.")
        self.voice.speak.assert_not_called()


if __name__ == "__main__": unittest.main()
