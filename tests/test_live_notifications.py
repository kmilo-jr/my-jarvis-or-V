import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import contextmanager
import unittest
from core.initiative import InitiativeStore
from core.live_notifications import LiveNotifications, gmail_delta, messages_delta


class LiveNotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = InitiativeStore(Path(self.temp.name)/'initiative.json')
        self.store.update_settings({'quiet_enabled': False, 'gap_seconds': 30})

    def tearDown(self): self.temp.cleanup()

    def test_cursor_and_notice_are_persisted_once_across_restart(self):
        first={'scope':'x','uid':10}; second={'scope':'x','uid':11}
        self.store.commit_notification('gmail',None,first,None)
        self.store.commit_notification('gmail',first,second,'Um novo e-mail')
        restarted=InitiativeStore(self.store.path)
        restarted.commit_notification('gmail',first,second,'Duplicado')
        data=restarted.snapshot(); self.assertEqual(len(data['events']),1)
        self.assertEqual(data['notification_cursors']['gmail'],second)

    def test_pausing_or_disabling_while_query_runs_prevents_delivery(self):
        for changes in ({'gmail':False},{'paused_until':time.time()+3600}):
            self.store.update_settings(dict(gmail=True,paused_until=0,**{})); self.store.update_settings(changes)
            self.store.commit_notification('gmail',None,{'uid':1},'Novo')
            self.assertEqual(self.store.snapshot()['events'],[])
            self.assertNotIn('gmail',self.store.snapshot().get('notification_cursors',{}))

    def test_pending_burst_is_coalesced_and_silence_is_respected(self):
        previous=None
        for i in range(50):
            cursor={'uid':i};self.store.commit_notification('gmail',previous,cursor,'Mensagem '+str(i));previous=cursor
        self.assertEqual(len(self.store.snapshot()['events']),1)
        self.store.update_settings({'quiet_enabled':True,'quiet_start':0,'quiet_end':0})
        self.assertIsNone(self.store.next_notice(busy=False))

    def test_failure_does_not_advance_cursor_and_backs_off(self):
        service=LiveNotifications(self.store,{'gmail':Mock(side_effect=TimeoutError('secret'))})
        service.busy.add('gmail');service._run('gmail')
        self.assertNotIn('gmail',self.store.snapshot().get('notification_cursors',{}))
        self.assertGreater(service.next_check['gmail']-time.monotonic(),55)
        self.assertNotIn('secret',service.status['gmail']);self.assertNotIn('gmail',service.busy)

    def test_close_discards_late_result(self):
        service=LiveNotifications(self.store,{'gmail':lambda previous:({'uid':1},'Novo')})
        service.close();service._run('gmail');self.assertEqual(self.store.snapshot()['events'],[])

    def test_no_duplicate_jobs_while_probe_is_blocked(self):
        import threading
        started=threading.Event();release=threading.Event()
        def probe(previous): started.set();release.wait(2);return {'uid':1},None
        probe=Mock(side_effect=probe);service=LiveNotifications(self.store,{'gmail':probe})
        try:
            service.tick();self.assertTrue(started.wait(1));service.tick();probe.assert_called_once()
        finally:service.close();release.set()

    def test_message_baseline_and_new_id_only(self):
        patcher = patch('mobile_bridge.notification_backend_status', return_value={'automatic':True})
        patcher.start(); self.addCleanup(patcher.stop)
        old={'id':'a','app':'WhatsApp','title':'Contato','body':'não deve ir ao aviso'}
        with patch('mobile_bridge.recent_notifications',return_value=[old]):
            cursor,title=messages_delta(None);self.assertIsNone(title)
            self.assertIsNone(messages_delta(cursor)[1])
        with patch('mobile_bridge.recent_notifications',return_value=[old,dict(old,id='b')]):
            _,title=messages_delta(cursor);self.assertIn('WhatsApp',title);self.assertNotIn(old['body'],title)

    def test_gmail_baseline_and_uid_range_ignores_old_result(self):
        client=Mock();client.response.return_value=('UIDNEXT',[b'11'])
        @contextmanager
        def connection():yield client,'test@example.com',[b'77']
        with patch('integrations.gmail_reader.GmailReader') as factory:
            factory.return_value.connection=connection
            cursor,title=gmail_delta(None);self.assertEqual(cursor['uid'],10);self.assertIsNone(title)
            client.uid.assert_not_called()
            client.uid.return_value=('OK',[b'10']);self.assertIsNone(gmail_delta(cursor)[1])
            client.uid.return_value=('OK',[b'11 12'])
            factory.return_value.fetch.return_value=b'Subject: Teste\r\nFrom: Pessoa\r\n\r\n'
            result,title=gmail_delta(cursor);self.assertEqual(result['uid'],12);self.assertIn('2 novo',title)
            self.assertIn('BODY.PEEK[HEADER',factory.return_value.fetch.call_args.args[2])

    def test_failed_write_preserves_cursor_for_retry(self):
        with patch.object(self.store,'_save',side_effect=OSError):
            with self.assertRaises(OSError):self.store.commit_notification('gmail',None,{'uid':1},'Novo')
        self.assertNotIn('notification_cursors',self.store.snapshot())

    def test_unavailable_capture_is_not_reported_as_successful_empty_poll(self):
        from core.live_notifications import CaptureUnavailable
        with patch('mobile_bridge.recent_notifications',return_value=[]), patch('mobile_bridge.notification_backend_status',return_value={'automatic':False}):
            with self.assertRaises(CaptureUnavailable): messages_delta(None)
