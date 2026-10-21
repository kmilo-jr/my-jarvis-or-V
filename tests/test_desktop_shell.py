import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui.instagram_window import InstagramExperimentWindow
from voice.engine import VoiceEngine
from core.daily_briefing import card

class DesktopShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        with patch.object(MainWindow,'_load_mics'):
            self.w=InstagramExperimentWindow(SimpleNamespace(),SimpleNamespace(skills=[]),VoiceEngine({}),startup_greeting=False,theme='red')
        self.w._initiative_timer.stop(); self.w.processing_sound.set_enabled(False)
        self.w.show(); self.app.processEvents()
    def tearDown(self):
        self.w.close(); self.w.deleteLater(); self.app.processEvents()
    def test_navigation_stops_hidden_orb_and_chat_uses_command_queue(self):
        shell=self.w.desktop_shell
        shell.select('stage'); self.app.processEvents(); self.assertTrue(self.w.neural.timer.isActive())
        shell.select('chat'); self.app.processEvents(); self.assertFalse(self.w.neural.timer.isActive())
        self.w.enqueue_command=Mock(); shell.chat_input.setText('agenda de hoje'); shell.submit()
        self.w.enqueue_command.assert_called_once_with('agenda de hoje',source='text')
        self.assertEqual(shell.chat_input.text(),'')
    def test_snapshot_distinguishes_failed_and_missing_sources_and_plain_text(self):
        shell=self.w.desktop_shell
        shell.update_briefing([card('gmail','Falha','Não foi possível consultar',ok=False),card('notícias','<b>Texto</b>','Teste')])
        self.assertEqual(shell.metrics['gmail'][0].text(),'Indisponível')
        self.assertEqual(shell.metrics['agenda'][1].text(),'Não incluído no resumo')
        self.assertIn('<b>Texto</b>',shell.detail_labels['notícias'].toPlainText())

    def test_office_lifecycle_and_input_routes_existing_queue(self):
        shell=self.w.desktop_shell
        self.assertFalse(hasattr(shell,'office'))
        shell.select('office');self.app.processEvents()
        self.assertTrue(shell.office.timer.isActive())
        self.w.enqueue_command=Mock()
        shell.office_input.setText('qual a filosofia de hoje')
        shell.office_input.returnPressed.emit()
        self.w.enqueue_command.assert_called_once_with('qual a filosofia de hoje',source='text')
        shell.select('chat');self.app.processEvents()
        self.assertFalse(shell.office.timer.isActive())
        shell.select('office');self.app.processEvents()
        self.w.game_mode.set_enabled(True);self.app.processEvents()
        self.assertFalse(shell.office.timer.isActive())
        self.w.game_mode.restore();self.app.processEvents()
        self.assertTrue(self.w.game_mode.enabled)
        self.assertTrue(shell.office.timer.isActive())
        self.w.game_mode.set_enabled(False);self.app.processEvents()
        self.assertTrue(shell.office.timer.isActive())

    def test_real_fast_philosophy_command_reaches_the_books(self):
        from PySide6.QtTest import QTest
        from core.functional_engine import FunctionalResult
        self.w.orchestrator.handle=Mock(return_value=[FunctionalResult(True,True,'Reflexão de teste.','FILOSOFIA')])
        self.w.tts_toggle.setChecked(False)
        self.w.desktop_shell.select('office');self.app.processEvents()
        office=self.w.desktop_shell.office
        origin=(office.x,office.y)
        self.w.enqueue_command('Qual a filosofia de hoje?')
        for _ in range(100):
            QTest.qWait(20)
            if self.w.command_thread is None: break
        self.assertIsNone(self.w.command_thread)
        self.assertEqual(office.activity,'books')
        QTest.qWait(3500)
        self.assertNotEqual((office.x,office.y),origin)
        self.assertAlmostEqual(office.x,office.TARGETS['books'][0],delta=1)
        self.assertAlmostEqual(office.y,office.TARGETS['books'][1],delta=1)

    def test_office_click_prepares_request_without_sending_or_replacing_draft(self):
        self.w.desktop_shell.select('office');self.app.processEvents()
        shell=self.w.desktop_shell
        self.w.enqueue_command=Mock()
        shell.office.activate_object('books')
        self.assertIn('estudar',shell.office_input.text())
        shell.office_input.setText('meu rascunho')
        shell.office.activate_object('music')
        self.assertEqual(shell.office_input.text(),'meu rascunho')
        self.w.enqueue_command.assert_not_called()

    def test_real_window_idle_moves_even_with_stale_speaking_label(self):
        from PySide6.QtTest import QTest
        self.w.desktop_shell.select('office');self.app.processEvents()
        office=self.w.desktop_shell.office
        self.w.set_state('SPEAKING')
        self.w._voice_capture_busy=False
        origin=(office.x,office.y)
        QTest.qWait(4000)
        self.assertTrue(office.timer.isActive())
        self.assertIn(office.activity,office.IDLE_ACTIVITIES)
        self.assertNotEqual(origin,(office.x,office.y))
        self.w.desktop_shell.select('chat');self.app.processEvents()
        frames=office.frame_count
        QTest.qWait(250)
        self.assertFalse(office.timer.isActive())
        self.assertEqual(frames,office.frame_count)
    def test_notifications_preserve_existing_inbox_when_opening_page(self):
        from ui.notification_center import NotificationCenter
        center=NotificationCenter(self.w); self.w._notification_center=center
        center.add_notice('gmail','Teste',show_center=False)
        self.w.show_notification_center()
        self.assertIs(self.w.desktop_shell.dialogs['notices'],center)
        self.assertEqual(center.list.count(),1)

if __name__=='__main__': unittest.main()
