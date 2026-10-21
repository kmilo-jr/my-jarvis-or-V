import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from voice.commands import is_stop_request
from voice.engine import VoiceEngine


class SpeechControlsTests(unittest.TestCase):
    def test_stop_controls_do_not_capture_media_requests(self):
        for text in ('V, para!', 'V, pare de falar.', 'silêncio'):
            self.assertTrue(is_stop_request(text), text)
        for text in ('V, pause a música', 'V, para o Spotify', 'para amanhã', 'toque Para'):
            self.assertFalse(is_stop_request(text), text)

    def test_cancel_clears_old_audio_but_accepts_future_speech(self):
        voice = VoiceEngine({})
        with patch.object(voice, '_ensure_tts_thread'):
            voice.speak('primeiro')
            _, old = voice._tts_queue.get_nowait()
            voice.speak('segundo')
            voice.stop_speaking()
            self.assertTrue(old.is_set())
            self.assertTrue(voice._tts_queue.empty())
            voice.speak('novo pedido')
            text, new = voice._tts_queue.get_nowait()
            self.assertEqual(text, 'novo pedido')
            self.assertFalse(new.is_set())

    def test_barge_in_is_opt_in_and_processing_audio_still_blocks(self):
        voice = VoiceEngine({})
        voice._tts_speaking.set()
        self.assertFalse(voice.voice_input_allowed())
        voice.config['barge_in_enabled'] = True
        self.assertTrue(voice.voice_input_allowed())
        voice.set_external_audio_active(True)
        self.assertFalse(voice.voice_input_allowed())

    def test_cancellation_during_synthesis_does_not_play_and_cleans_file(self):
        voice = VoiceEngine({})
        started, release, synthesized = threading.Event(), threading.Event(), threading.Event()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'audio.mp3'
            def synthesize(_):
                started.set()
                release.wait(2)
                path.write_bytes(b'fake')
                synthesized.set()
                return str(path)
            with patch.object(voice, '_play_mp3_windows') as play:
                worker = threading.Thread(target=lambda: voice._speak_chunks(['a', 'b'], synthesize))
                worker.start()
                self.assertTrue(started.wait(1))
                voice.stop_speaking()
                worker.join(1)
                self.assertFalse(worker.is_alive())
                release.set()
                self.assertTrue(synthesized.wait(1))
                deadline = time.monotonic() + 1
                while path.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertFalse(path.exists())
                play.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows MCI')
    def test_playback_cancellation_closes_mci_device(self):
        voice = VoiceEngine({})
        calls = []
        def mci(command, output, size, callback):
            calls.append(command)
            if command.startswith('play '):
                voice.stop_speaking()
            return 0
        with patch('ctypes.windll.winmm.mciSendStringW', side_effect=mci):
            self.assertTrue(voice._play_mp3_windows('test.mp3'))
        self.assertTrue(calls[-1].startswith('close '))


if __name__ == '__main__':
    unittest.main()
