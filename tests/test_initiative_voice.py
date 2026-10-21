from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from core.initiative import InitiativeStore
from voice.engine import VoiceEngine


class NoticeVoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = InitiativeStore(Path(self.temp.name) / 'events.json')
        self.store.update_settings({'voice': True, 'quiet_enabled': False})
        self.now = time.time()

    def tearDown(self):
        self.temp.cleanup()

    def event(self, kind='reminders'):
        e = self.store.add('Teste de aviso', self.now - 1, kind=kind, now=self.now - 2)
        self.store.delivered(e['id'], now=self.now, voice_pending=True)
        return e

    def test_visual_delivery_does_not_confirm_voice_and_retry_survives_restart(self):
        e = self.event()
        self.assertIsNone(self.store.next_notice(busy=False, now=self.now + 200))
        self.assertIsNotNone(self.store.next_voice_notice(busy=False, now=self.now))
        self.store.voice_result(e['id'], 'failed', 'network', now=self.now)
        reopened = InitiativeStore(self.store.path)
        self.assertIsNone(reopened.next_voice_notice(busy=False, now=self.now + 59))
        self.assertIsNotNone(reopened.next_voice_notice(busy=False, now=self.now + 60))
        reopened.voice_result(e['id'], 'done', now=self.now + 60)
        self.assertIsNone(reopened.next_voice_notice(busy=False, now=self.now + 120))
        self.assertEqual(reopened.snapshot()['events'][0]['voice_state'], 'spoken')

    def test_busy_alarm_keeps_voice_requested_and_waits(self):
        self.store.add('Alarme', self.now - 1, kind='alarms', now=self.now - 2)
        notice = self.store.next_notice(busy=True, now=self.now)
        self.assertFalse(notice['voice'])
        self.assertTrue(notice['voice_requested'])
        self.store.delivered(notice['id'], voice_pending=notice['voice_requested'])
        self.assertIsNone(self.store.next_voice_notice(busy=True))
        self.assertIsNotNone(self.store.next_voice_notice(busy=False))

    def test_game_mode_defers_common_speech_but_preserves_alarms_and_resumes(self):
        common = self.event()
        self.assertIsNone(self.store.next_voice_notice(busy=False, defer_common=True))
        alarm = self.event('alarms')
        notice = self.store.next_voice_notice(busy=False, defer_common=True)
        self.assertEqual(notice['id'], alarm['id'])
        self.store.voice_result(alarm['id'], 'done')
        self.assertIsNone(self.store.next_voice_notice(busy=False, defer_common=True))
        self.assertEqual(self.store.next_voice_notice(busy=False)['id'], common['id'])

    def test_account_notification_is_visual_immediately_while_busy(self):
        import uuid
        data = self.store._load()
        event = {'id': uuid.uuid4().hex, 'title': 'Novo e-mail', 'due': self.now - 1,
                 'kind': 'gmail', 'state': 'pending', 'created': self.now - 2}
        data['events'].append(event)
        self.store._save(data)
        notice = self.store.next_notice(busy=True, now=self.now)
        self.assertEqual(notice['id'], event['id'])
        self.assertFalse(notice['voice'])
        self.assertTrue(notice['voice_requested'])

    def test_retries_bounded_and_intentional_cancel_not_repeated(self):
        e = self.event()
        for index in range(3):
            self.store.voice_result(e['id'], 'failed', 'offline', now=self.now + index * 60)
        self.assertEqual(self.store.snapshot()['events'][0]['voice_state'], 'failed')
        self.assertIsNone(self.store.next_voice_notice(busy=False, now=self.now + 999))
        e = self.event('alarms')
        self.store.voice_result(e['id'], 'cancelled')
        self.assertIsNone(self.store.next_voice_notice(busy=False, now=self.now + 999))

    def test_speech_receipts_confirm_success_failure_and_queue_cancellation(self):
        for success in (True, False):
            voice = VoiceEngine({'tts_profile': 'elevenlabs_custom', 'tts_eleven_fallback_edge': False})
            with patch.object(voice, '_ensure_tts_thread'):
                receipt = voice.speak_tracked('Teste')
            voice._tts_queue.put(None)
            with patch.object(voice, '_speak_elevenlabs', return_value=success), patch.object(voice, '_save_tts_diagnostic'):
                voice._tts_loop()
            self.assertEqual(receipt['state'], 'done' if success else 'failed')
        voice = VoiceEngine({})
        with patch.object(voice, '_ensure_tts_thread'):
            receipt = voice.speak_tracked('Teste')
            voice.stop_speaking()
        self.assertEqual(receipt['state'], 'cancelled')

    def test_muted_or_disabled_category_defers_voice(self):
        self.event()
        for settings in ({'voice': False}, {'voice': True, 'reminders': False}, {'reminders': True, 'paused_until': self.now + 300}):
            self.store.update_settings(settings)
            self.assertIsNone(self.store.next_voice_notice(busy=False, now=self.now))


if __name__ == '__main__':
    unittest.main()
