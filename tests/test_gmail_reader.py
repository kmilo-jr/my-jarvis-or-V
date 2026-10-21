import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from integrations.gmail_reader import GmailReader, mail_request, parse_message, save_account, load_account


class GmailTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.select.return_value = ('OK', [b'2'])
        self.client.response.return_value = ('UIDVALIDITY', [b'123'])
        def uid(command, *args):
            if command == 'search': return 'OK', [b'100 101']
            return 'OK', [(b'101', b'From: Example <test@example.org>\r\nSubject: Teste\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nTexto de teste.')]
        self.client.uid.side_effect = uid
        self.reader = GmailReader(lambda: {'address':'test@gmail.com','password':'fake'}, Mock(return_value=self.client))

    def test_list_and_read_use_readonly_and_peek(self):
        self.assertIn('1. De Example', self.reader.list_recent(True))
        self.client.select.assert_called_with('INBOX', readonly=True)
        self.client.uid.assert_any_call('search', None, 'UNSEEN')
        self.assertIn('Texto de teste.', self.reader.read(1))
        self.client.uid.assert_any_call('fetch', b'101', '(BODY.PEEK[]<0.262144>)')
        self.client.store.assert_not_called()

    def test_number_requires_snapshot_and_mailbox_identity(self):
        ok, text = self.reader.execute(('read', 1)); self.assertFalse(ok)
        self.reader.list_recent()
        self.client.response.return_value = ('UIDVALIDITY', [b'456'])
        ok, text = self.reader.execute(('read', 1)); self.assertFalse(ok)
        self.assertIn('mudou', text)

    def test_morning_reads_only_three_newest_unread_without_changing_snapshot(self):
        original = self.client.uid.side_effect
        self.client.uid.side_effect = lambda command, *args: (
            ('OK', [b'1 2 3 4 5']) if command == 'search' else original(command, *args))
        self.reader.snapshot = [b'old']
        items = self.reader.morning_messages()
        self.assertEqual(len(items), 3)
        self.assertNotIn('body', items[0])
        for call in self.client.uid.call_args_list:
            if call.args[0] == 'fetch':
                self.assertEqual(call.args[2], '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
        self.client.select.assert_called_with('INBOX', readonly=True)
        self.client.uid.assert_any_call('search', None, 'UNSEEN')
        fetched = [c.args[1] for c in self.client.uid.call_args_list if c.args[0] == 'fetch']
        self.assertEqual(fetched, [b'5', b'4', b'3'])
        self.assertEqual(self.reader.snapshot, [b'old'])
        self.client.store.assert_not_called()

    def test_morning_empty_and_excludes_body(self):
        self.client.uid.side_effect = lambda *args: ('OK', [b''])
        self.assertEqual(self.reader.morning_messages(), [])
        self.client.uid.side_effect = lambda *args: ('OK', [b'1'])
        with patch.object(self.reader, 'fetch', return_value=b'Subject: Long\r\n\r\n' + b'a'*900):
            item = self.reader.morning_messages()[0]
        self.assertNotIn('body', item)
        self.assertEqual(item['title'], 'Long')

    def test_auth_error_does_not_expose_credentials(self):
        import imaplib
        self.client.login.side_effect = imaplib.IMAP4.error('secret fake')
        ok, text = self.reader.execute(('list', False))
        self.assertFalse(ok); self.assertNotIn('secret', text)

    def test_command_scope(self):
        self.assertEqual(mail_request('V, leia meus e-mails'), ('list', False))
        self.assertEqual(mail_request('V, leia o e-mail 2'), ('read', 2))
        for text in ('não leia meus emails', 'apague o email 2', 'envie um email', 'o que é email?'):
            self.assertIsNone(mail_request(text))

    def test_html_is_text_without_scripts_or_external_requests(self):
        raw = b'Subject: Test\r\nContent-Type: text/html\r\n\r\n<p>Hello</p><script>bad()</script><img src="https://example.org/tracker">'
        self.assertEqual(parse_message(raw)['body'], 'Hello')

    def test_password_is_encrypted_for_windows_user(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'gmail.dat'
            save_account('test@gmail.com', 'abcdefghijklmnop', path)
            self.assertNotIn('abcdefghijklmnop', path.read_text())
            self.assertEqual(load_account(path)['address'], 'test@gmail.com')

    def test_core_reads_without_ai_planning(self):
        from core.functional_engine import FunctionalEngine
        engine = FunctionalEngine.__new__(FunctionalEngine)
        engine._append_history = Mock(); engine._gmail_reader = self.reader
        result = engine.handle('V, leia meus emails')[0]
        self.assertEqual(result.skill, 'GMAIL')
        self.assertEqual(engine._append_history.call_count, 1)


if __name__ == '__main__': unittest.main()
