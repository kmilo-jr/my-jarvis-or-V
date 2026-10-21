import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from ui.game_mode import GameModeController


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.neural = QWidget(self)
        self.setCentralWidget(self.neural)
        self.neural.timer = QTimer(self.neural)
        self.neural.timer.start(16)
        self.timer = QTimer(self)
        self.timer.start(1000)
        self.voice_timer = QTimer(self)
        self.voice_timer.start(200)
        self.messages = []
        self.append_v = self.messages.append
        self.game_mode = GameModeController(self, self.addToolBar('V'))


class GameModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Window()
        self.window.resize(500, 400)
        self.window.move(100, 100)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.game_mode.shutdown()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_hidden_animation_stops_without_stopping_voice(self):
        self.window.hide()
        self.app.processEvents()
        self.assertFalse(self.window.neural.timer.isActive())
        self.assertTrue(self.window.voice_timer.isActive())
        self.assertEqual(self.window.voice_timer.interval(), 200)
        self.window.game_mode.restore()
        self.app.processEvents()
        self.assertTrue(self.window.neural.timer.isActive())
        self.assertEqual(self.window.neural.timer.interval(), 16)

    def test_one_monitor_fallback_and_geometry_restoration(self):
        original = self.window.geometry()
        with patch('ui.game_mode.QApplication.screens', return_value=[self.window.screen()]), patch('ui.game_mode.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
            self.window.game_mode.set_enabled(True)
        self.app.processEvents()
        self.assertTrue(self.window.isMinimized())
        self.assertFalse(self.window.neural.timer.isActive())
        self.window.game_mode.restore()
        self.app.processEvents()
        self.assertEqual(self.window.neural.timer.interval(), 100)
        self.assertEqual(self.window.timer.interval(), 2000)
        self.window.game_mode.set_enabled(False)
        self.app.processEvents()
        self.assertEqual(self.window.geometry(), original)
        self.assertEqual(self.window.neural.timer.interval(), 16)
        self.assertEqual(self.window.timer.interval(), 1000)

    def test_tray_hide_can_be_recovered(self):
        with patch('ui.game_mode.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
            self.window.game_mode.minimize()
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.game_mode.tray.isVisible())
        self.window.game_mode.restore()
        self.assertTrue(self.window.isVisible())

    def test_repeated_activation_preserves_original_geometry(self):
        with patch('ui.game_mode.QApplication.screens', return_value=[self.window.screen()]):
            self.window.game_mode.set_enabled(True)
            original = self.window.game_mode._geometry
            self.window.game_mode.set_enabled(True)
        self.assertEqual(self.window.game_mode._geometry, original)
        self.window.game_mode.shutdown()
        self.assertFalse(self.window.game_mode.tray.isVisible())

    def test_two_monitors_still_collapse_and_avatar_stops_when_restored(self):
        with patch('ui.game_mode.QApplication.screens', return_value=[self.window.screen(), object()]):
            self.window.game_mode.set_enabled(True)
        self.app.processEvents()
        game = self.window.game_mode
        self.assertTrue(self.window.isMinimized() or not self.window.isVisible())
        self.assertTrue(game.orb.isVisible())
        self.assertTrue(game.orb.timer.isActive())
        game.restore()
        self.app.processEvents()
        self.assertFalse(game.orb.isVisible())
        self.assertFalse(game.orb.timer.isActive())
        game.set_enabled(True)
        self.app.processEvents()
        self.assertTrue(game.orb.isVisible())

    def test_avatar_state_and_idle_budget(self):
        orb = self.window.game_mode.orb
        self.window.neural.state = 'SPEAKING'
        orb._tick()
        self.assertEqual(orb.state, 'SPEAKING')
        self.assertEqual(orb.timer.interval(), 100)
        self.window.neural.state = 'READY'
        orb._tick()
        self.assertEqual(orb.timer.interval(), 500)

    def test_avatar_opens_compact_chat_and_routes_input_without_restoring(self):
        from unittest.mock import Mock
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        self.window.enqueue_command = Mock()
        self.window.toggle_continuous_voice = Mock()
        game = self.window.game_mode
        game.minimize()
        self.app.processEvents()
        QTest.mouseClick(game.orb, Qt.LeftButton)
        self.app.processEvents()
        panel = game.quick_chat
        self.assertTrue(panel.isVisible())
        self.assertTrue(self.window.isMinimized() or not self.window.isVisible())
        panel.input.setText('qual a filosofia de hoje')
        QTest.keyClick(panel.input, Qt.Key_Return)
        self.window.enqueue_command.assert_called_once_with('qual a filosofia de hoje')
        self.assertEqual(panel.input.text(), '')
        panel.mic.click()
        self.window.toggle_continuous_voice.assert_called_once()
        QTest.qWait(750)
        self.assertEqual(game.orb.greeting.state(), game.orb.greeting.State.Stopped)
        game.restore()
        self.app.processEvents()
        self.assertFalse(panel.isVisible())
        self.assertFalse(panel.timer.isActive())

    def test_game_mode_restores_voice_policy_without_changing_saved_config(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        backend = Mock()
        voice = SimpleNamespace(config={'tts_qwen_idle_seconds': 120}, _qwen=backend)
        self.window.voice_engine = voice
        self.window.game_mode.set_enabled(True)
        self.assertTrue(voice._game_mode)
        self.assertTrue(backend.game_mode)
        self.window.game_mode.set_enabled(False)
        self.assertFalse(voice._game_mode)
        self.assertFalse(backend.game_mode)
        self.assertEqual(voice.config, {'tts_qwen_idle_seconds': 120})

    def test_real_interfaces_route_commands_and_keep_throttling_after_show(self):
        from types import SimpleNamespace
        from voice.engine import VoiceEngine
        from ui.main_window import MainWindow
        from ui.instagram_window import InstagramExperimentWindow
        from ui.amber_window import AmberExperimentWindow
        for window_type in (MainWindow, InstagramExperimentWindow, AmberExperimentWindow):
            with self.subTest(window=window_type.__name__):
                with patch.object(MainWindow, '_load_mics'):
                    w = window_type(SimpleNamespace(), SimpleNamespace(skills=[]), VoiceEngine({}), startup_greeting=False)
                try:
                    w.show()
                    self.app.processEvents()

                    with patch.object(w, '_pump_commands') as pump:
                        w.enqueue_command('V, vou jogar')
                        self.assertTrue(w.game_mode.enabled)
                        w.game_mode.restore()
                        self.app.processEvents()
                        self.assertGreaterEqual(w.neural.timer.interval(), 100)
                        w.enqueue_command('V, modo normal')
                        self.assertFalse(w.game_mode.enabled)
                        for command in ('V, ir ao modo jogo', 'V, vá para o modo jogo', 'V, entre no modo jogo'):
                            w.enqueue_command(command)
                            self.assertTrue(w.game_mode.enabled)
                            self.assertTrue(w.isMinimized() or not w.isVisible())
                            w.enqueue_command('V, modo normal')
                        w.enqueue_command('V, recolher')
                        self.assertTrue(w.isMinimized() or not w.isVisible())
                        w.enqueue_command('V, abrir interface')
                        pump.assert_not_called()
                    self.app.processEvents()
                    self.assertEqual(w.neural.timer.interval(), w.game_mode._frame_interval)
                finally:
                    w.close()
                    w.deleteLater()
                    self.app.processEvents()

    def test_failed_result_is_available_in_help_without_raw_body(self):
        from types import SimpleNamespace
        from voice.engine import VoiceEngine
        from ui.main_window import MainWindow
        from core.functional_engine import FunctionalResult
        with patch.object(MainWindow, '_load_mics'):
            w = MainWindow(SimpleNamespace(), SimpleNamespace(skills=[]), VoiceEngine({}), startup_greeting=False)
        try:
            w.tts_toggle.setChecked(False)
            with patch.object(w, '_initiative_completion'):
                w._command_done([FunctionalResult(True, False, 'Groq HTTP 403 private-body', 'AI BRAIN')])
            w.enqueue_command('V, o que aconteceu?')
            self.assertIn('negou acesso', w._failure_help.message.text())
            self.assertNotIn('private-body', w._failure_help.message.text())
        finally:
            w.close(); w.deleteLater(); self.app.processEvents()

    def test_briefing_pauses_covered_animation_and_resumes_it(self):
        from types import SimpleNamespace
        from PySide6.QtWidgets import QWidget
        panel = QWidget(self.window)
        backdrop_timer = QTimer(panel)
        panel.backdrop = SimpleNamespace(timer=backdrop_timer)
        panel.active = True
        self.window._briefing_panel = panel
        panel.show()
        self.window.game_mode.refresh_rendering()
        self.assertFalse(self.window.neural.timer.isActive())
        self.assertTrue(backdrop_timer.isActive())
        self.assertEqual(backdrop_timer.interval(), 33)
        self.window.hide()
        self.window.game_mode.refresh_rendering()
        self.assertFalse(backdrop_timer.isActive())
        self.window.show()
        self.window.game_mode.refresh_rendering()
        self.assertTrue(backdrop_timer.isActive())
        panel.hide()
        backdrop_timer.stop()
        self.window.game_mode.refresh_rendering()
        self.assertTrue(self.window.neural.timer.isActive())

    def test_dual_interface_switch_preserves_game_session(self):
        from types import SimpleNamespace
        from PySide6.QtTest import QTest
        from voice.engine import VoiceEngine
        from ui.main_window import MainWindow
        from main_dual_ui import UiModeManager
        with patch.object(MainWindow, '_load_mics'), patch.object(MainWindow, '_startup_greeting'), \
             patch.object(UiModeManager, '_load_mode', return_value='orbital'), \
             patch.object(UiModeManager, '_save_mode'), \
             patch.object(UiModeManager, '_setup_notification_reader'), \
             patch.object(UiModeManager, '_start_remote_server'), \
             patch.object(UiModeManager, '_start_p2p_remote'):
            manager = UiModeManager(self.app, SimpleNamespace(), SimpleNamespace(skills=[]), VoiceEngine({}))
            try:
                self.app.processEvents()
                manager.window.game_mode.set_enabled(True)
                saved = manager.window.game_mode._geometry
                manager.switch_mode()
                # Switching is queued on Qt; allow pending layout/paint events
                # from the desktop pages to finish instead of assuming 100 ms.
                for _ in range(40):
                    if manager.mode == 'amber' and not manager._switch_pending:
                        break
                    QTest.qWait(50)
                self.assertEqual(manager.mode, 'amber')
                self.assertTrue(manager.window.game_mode.enabled)
                self.assertEqual(manager.window.game_mode._geometry, saved)
                manager.window.game_mode.restore()
                self.app.processEvents()
                self.assertEqual(manager.window.neural.timer.interval(), 100)
                manager.window.game_mode.set_enabled(False)
                self.app.processEvents()
                self.assertEqual(manager.window.neural.timer.interval(), 16)
            finally:
                manager._remote_timer.stop()
                manager._notification_timer.stop()
                manager.window.close()
                manager.window.deleteLater()
                manager.deleteLater()
                self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
