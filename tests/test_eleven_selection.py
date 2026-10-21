import unittest
from unittest.mock import patch, Mock

from voice.engine import VoiceEngine
from voice.preferences import selection_settings, voice_preferences


class ElevenSelectionTests(unittest.TestCase):
    def test_quota_failure_explains_why_voice_is_unavailable(self):
        voice = VoiceEngine({'tts_eleven_voice_id': 'test-voice'})
        voice._eleven_session = Mock()
        response = voice._eleven_session.post.return_value
        response.status_code = 401
        response.json.return_value = {'detail': {'status': 'quota_exceeded'}}
        with patch('voice.eleven_auth.load_key', return_value='test-key'):
            self.assertIsNone(voice._synthesize_eleven_file('Teste.'))
        self.assertIn('cota de voz esgotada', voice.last_tts_error)
        self.assertIn('quota_exceeded', voice.last_tts_error)
        self.assertNotIn('test-key', voice.last_tts_error)

    def test_voice_error_is_shown_once_and_can_reappear_after_recovery(self):
        from types import SimpleNamespace
        from ui.main_window import MainWindow
        window = SimpleNamespace(voice_engine=SimpleNamespace(last_tts_error='Cota esgotada'), append_v=Mock())
        MainWindow._report_tts_failure(window)
        MainWindow._report_tts_failure(window)
        self.assertEqual(window.append_v.call_count, 1)
        window.voice_engine.last_tts_error = ''
        MainWindow._report_tts_failure(window)
        window.voice_engine.last_tts_error = 'Cota esgotada'
        MainWindow._report_tts_failure(window)
        self.assertEqual(window.append_v.call_count, 2)

    def test_saving_preferences_keeps_eleven_and_disables_local_clone(self):
        config = voice_preferences(100, False, False, xtts_voice='elevenlabs')
        self.assertEqual(config['tts_profile'], 'elevenlabs_custom')
        self.assertFalse(config['tts_xtts_enabled'])
        self.assertFalse(config['tts_eleven_fallback_edge'])

    def test_failed_custom_voice_does_not_switch_to_another_voice(self):
        voice = VoiceEngine(selection_settings('elevenlabs'))
        voice._tts_queue.put(('Olá.', voice._speech_generation))
        voice._tts_queue.put(None)
        with patch.object(voice, '_speak_elevenlabs', return_value=False), \
             patch.object(voice, '_save_tts_diagnostic'), \
             patch.object(voice, '_speak_edge_tts') as edge, \
             patch.object(voice, '_speak_piper') as piper, \
             patch('win32com.client.Dispatch') as sapi:
            voice._tts_loop()
        edge.assert_not_called()
        piper.assert_not_called()
        sapi.assert_not_called()
        self.assertIn('ElevenLabs', voice.last_tts_error)


if __name__ == '__main__':
    unittest.main()
