import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from ui.notification_center import NotificationCenter
from ui.main_window import MainWindow


class NotificationCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_email_opens_center_and_keeps_history_entry(self):
        window = None
        center = NotificationCenter(window)
        center.add_notice('gmail', 'Gmail: 1 novo e-mail. Assunto: Teste')
        self.assertTrue(center.isVisible())
        self.assertEqual(center.list.count(), 1)
        self.assertIn('GMAIL', center.list.item(0).text())
        self.assertIn('Assunto: Teste', center.list.item(0).text())
        self.assertEqual(center.unread, 1)
        center.mark_read()
        self.assertEqual(center.unread, 0)
        center.close()

    def test_notice_text_keeps_email_title_without_reading_body(self):
        notice = {'kind': 'gmail', 'title': 'Gmail: 1 novo e-mail. Assunto: Relatório', 'due': 0}
        self.assertEqual(MainWindow._notice_text(notice), notice['title'])

    def test_second_email_is_new_row_and_not_replaced(self):
        center = NotificationCenter(None)
        center.add_notice('gmail', 'Assunto: Um')
        center.add_notice('gmail', 'Assunto: Dois')
        self.assertEqual(center.list.count(), 2)
        self.assertIn('Dois', center.list.item(0).text())
        self.assertIn('Um', center.list.item(1).text())
        center.close()


if __name__ == '__main__':
    unittest.main()
