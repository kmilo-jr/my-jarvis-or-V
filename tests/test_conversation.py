import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from voice.conversation import ConversationWindow, action_acknowledgement
from voice.engine import VoiceEngine
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow


class ConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.voice = VoiceEngine({})
        self.voice.speak = Mock()
        with patch.object(MainWindow, "_load_mics"):
            self.window = InstagramExperimentWindow(SimpleNamespace(), SimpleNamespace(skills=[]), self.voice, startup_greeting=False)
        self.window.processing_sound.set_enabled(False)
        self.window.voice_enabled = True
        self.window.enqueue_command = Mock()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_no_wake_word_outside_window_is_ignored(self):
        self.window._continuous_heard("abra o navegador", {})
        self.window.enqueue_command.assert_not_called()
        self.window._continuous_heard("V, abra o navegador", {})
        self.window.enqueue_command.assert_called_once()

    def test_uncertain_or_incomplete_voice_never_executes(self):
        for reason in ('uncertain_speech', 'audio_overflow', 'cancelled', 'tts_overlap'):
            self.window._continuous_heard('V, abra o navegador', {'reason': reason})
        self.window.enqueue_command.assert_not_called()

    def test_followup_uses_speech_start_not_transcription_finish(self):
        w = self.window
        w._conversation.wait_for_reply()
        w._conversation.open(time.monotonic() - 10)
        w._continuous_heard("e amanhã?", {"speech_started_at": w._conversation.opened_at + 7})
        w.enqueue_command.assert_called_once_with("e amanhã?", source="voice", input_meta=unittest.mock.ANY)
        self.assertEqual(w._conversation.deadline, 0)

    def test_expired_and_pre_reply_speech_are_ignored(self):
        for start in (99, 109):
            self.window._conversation.wait_for_reply()
            self.window._conversation.open(100)
            self.window._continuous_heard("e amanhã?", {"speech_started_at": start})
        self.window.enqueue_command.assert_not_called()

    def test_reply_waits_for_audio_and_cooldown(self):
        w = self.window
        w._conversation.wait_for_reply()
        with patch.object(self.voice, "has_pending_speech", return_value=True):
            w._settle_state_after_audio()
            self.assertEqual(w._conversation.deadline, 0)
        self.voice._last_tts_end = time.monotonic()
        w._settle_state_after_audio()
        self.assertEqual(w._conversation.deadline, 0)
        self.voice._last_tts_end = 0
        w._settle_state_after_audio()
        self.assertGreater(w._conversation.deadline, time.monotonic())

    def test_stop_and_opt_out_cancel_window(self):
        w = self.window
        w._continuous_heard("V", {})
        self.assertGreater(w._conversation.deadline, 0)
        w._continuous_heard("encerrar conversa", {})
        self.assertEqual(w._conversation.deadline, 0)
        w.enqueue_command.assert_not_called()
        w._continuous_heard("V", {})
        w.followup_toggle.setChecked(False)
        w._continuous_heard("e amanhã?", {})
        w.enqueue_command.assert_not_called()

    def test_interrupt_cancels_pending_followup(self):
        self.window._conversation.wait_for_reply()
        self.window.interrupt_speech()
        self.assertFalse(self.window._conversation.pending)

    def test_action_progress_once_and_never_after_completion(self):
        w = self.window
        w._command_complete = False
        w._progress_message = "TOOL 1/1 • app.open"
        ack = action_acknowledgement(w._progress_message)
        w._speak_action_progress(0, w._progress_message, ack)
        w._speak_action_progress(0, w._progress_message, ack)
        self.voice.speak.assert_called_once_with("Vou tentar abrir agora.")
        self.voice.speak.reset_mock()
        w._acknowledged = False
        w._command_complete = True
        w._speak_action_progress(0, w._progress_message, ack)
        self.voice.speak.assert_not_called()

    def test_old_command_and_muted_acknowledgements_are_ignored(self):
        w = self.window
        w._command_complete = False
        w._command_serial = 2
        w._progress_message = "TOOL 1/1 • app.open"
        w._speak_action_progress(1, w._progress_message, "Vou tentar abrir agora.")
        w.tts_toggle.setChecked(False)
        w._speak_action_progress(2, w._progress_message, "Vou tentar abrir agora.")
        self.voice.speak.assert_not_called()
        self.assertEqual(action_acknowledgement("AI BRAIN • conversa"), "")


if __name__ == "__main__":
    unittest.main()
