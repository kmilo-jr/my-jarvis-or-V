import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import QThread, Qt
from tests.test_game_mode import Window

class AvatarFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_completion_expression_expires_and_error_does_not_celebrate(self):
        from ui.floating_orb import FloatingOrb
        state=['PROCESSING']
        orb=FloatingOrb(lambda:(state[0],False))
        try:
            with patch('ui.floating_orb.time.monotonic',return_value=100):
                orb._tick();state[0]='READY';orb._tick()
                self.assertEqual(orb._pleased_until,102)
            with patch('ui.floating_orb.time.monotonic',return_value=103):
                orb._tick();self.assertEqual(orb._pleased_until,0)
                state[0]='ERROR';orb._tick();state[0]='READY';orb._tick()
                self.assertEqual(orb._pleased_until,0)
        finally:
            orb.close();orb.deleteLater();self.app.processEvents()

    def test_send_failure_keeps_text_and_mic_failure_is_visible(self):
        w=Window()
        try:
            w.enqueue_command=Mock(side_effect=RuntimeError('indisponível'))
            w.toggle_continuous_voice=Mock(side_effect=RuntimeError('microfone ausente'))
            panel=w.game_mode.quick_chat
            panel.input.setText('meu pedido'); panel.submit()
            self.assertEqual(panel.input.text(),'meu pedido')
            self.assertIn('indisponível',panel.reply.toPlainText())
            panel.toggle_voice()
            self.assertIn('microfone ausente',panel.status.text())
            panel.sync_voice()
            self.assertIn('microfone ausente',panel.status.text())
        finally:
            w.game_mode.shutdown(); w.close(); w.deleteLater(); self.app.processEvents()

    def test_history_escapes_content_and_draft_survives_hiding(self):
        w=Window()
        try:
            panel=w.game_mode.quick_chat
            panel.set_reply('<script>literal</script>')
            self.assertIn('<script>literal</script>',panel.reply.toPlainText())
            for i in range(25): panel.set_reply(f'Resposta {i}')
            self.assertEqual(len(panel._messages),16)
            self.assertNotIn('Resposta 0\n',panel.reply.toPlainText())
            panel.input.setText('rascunho')
            w.game_mode.minimize(); self.app.processEvents()
            panel.present(); QTest.qWait(210)
            panel.hide(); panel.present()
            self.assertEqual(panel.input.text(),'rascunho')
            self.assertTrue(panel.send_button.isEnabled())
            panel.clear_conversation()
            self.assertEqual(len(panel._messages),0)
            self.assertFalse(panel.copy_button.isEnabled())
            panel.hide()
            self.assertFalse(panel.timer.isActive())
            self.assertEqual(panel.appear.state(),panel.appear.State.Stopped)
        finally:
            w.game_mode.shutdown(); w.close(); w.deleteLater(); self.app.processEvents()

    def test_greeting_varies_and_panel_follows_without_leaving_screen(self):
        w=Window()
        try:
            game=w.game_mode
            game.minimize(); self.app.processEvents(); game.open_quick_chat()
            for _ in range(15):
                previous=game.orb._greeting_kind
                game.orb.play_greeting()
                self.assertNotEqual(previous,game.orb._greeting_kind)
            area=game.orb.screen().availableGeometry()
            game.orb.move(area.topLeft()); self.app.processEvents()
            self.assertTrue(area.contains(game.quick_chat.geometry()))
            game.quick_chat.hide()
            self.assertFalse(game.orb.chat_open)
        finally:
            w.game_mode.shutdown(); w.close(); w.deleteLater(); self.app.processEvents()

    def test_real_worker_returns_response_while_main_window_hidden(self):
        from ui.main_window import MainWindow
        from ui.instagram_window import InstagramExperimentWindow
        from ui.amber_window import AmberExperimentWindow
        from voice.engine import VoiceEngine
        from core.functional_engine import FunctionalResult
        for cls in (MainWindow,InstagramExperimentWindow,AmberExperimentWindow):
            with self.subTest(interface=cls.__name__):
                orch=SimpleNamespace(handle=Mock(return_value=[FunctionalResult(True,True,'Resposta de teste','TESTE')]))
                with patch.object(MainWindow,'_load_mics'):
                    w=cls(orch,SimpleNamespace(skills=[]),VoiceEngine({}),startup_greeting=False)
                try:
                    w.tts_toggle.setChecked(False)
                    w.game_mode.minimize(); self.app.processEvents()
                    w.game_mode.open_quick_chat()
                    panel=w.game_mode.quick_chat
                    update_threads=[]
                    panel.reply.textChanged.connect(lambda: update_threads.append(QThread.currentThread()), Qt.DirectConnection)
                    panel.input.setText('pedido de teste'); panel.submit()
                    for _ in range(100):
                        QTest.qWait(20)
                        if w.command_thread is None: break
                    self.assertIsNone(w.command_thread)
                    self.assertIn('Resposta de teste',panel.reply.toPlainText())
                    self.assertTrue(update_threads)
                    self.assertTrue(all(thread == self.app.thread() for thread in update_threads))
                    self.assertTrue(w.isMinimized() or not w.isVisible())
                finally:
                    w.close(); w.deleteLater(); self.app.processEvents()

if __name__=='__main__': unittest.main()
