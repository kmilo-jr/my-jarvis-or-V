import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from voice.engine import VoiceEngine
from voice.robot_effect import process_audio


class RobotEffectTests(unittest.TestCase):
    def test_repeated_processing_does_not_share_filter_state(self):
        x = np.random.default_rng(3).normal(0, .1, 24000).astype('float32')
        first = process_audio(x, 24000)
        process_audio(x[::-1], 24000)
        np.testing.assert_array_equal(first, process_audio(x, 24000))

    def test_silence_and_bypass(self):
        x = np.zeros((24000, 1), dtype=np.float32)
        np.testing.assert_array_equal(process_audio(x, 24000), x)
        x = np.random.default_rng(4).normal(0, .1, (24000, 2)).astype('float32')
        np.testing.assert_array_equal(process_audio(x, 24000, 0), x)

    def test_duration_finite_and_peak_at_supported_rates(self):
        for rate in (16000, 24000, 44100, 48000):
            x = np.sin(2 * np.pi * 170 * np.arange(rate) / rate).astype('float32')
            for amount in (.35, 1):
                y = process_audio(x, rate, amount)
                self.assertEqual(y.shape, x.shape)
                self.assertTrue(np.isfinite(y).all())
                self.assertLessEqual(np.max(np.abs(y)), .98001)
                self.assertGreater(np.std(y), .01)
                self.assertFalse(np.allclose(x, y))

    def test_bad_input(self):
        for amount in (-1, 2, float('nan')):
            with self.assertRaises(ValueError):
                process_audio(np.ones(300), 24000, amount)

    def test_file_integration_cleanup_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'dry.wav'
            x = .2 * np.sin(2 * np.pi * 180 * np.arange(12000) / 24000)
            voice = VoiceEngine({'tts_robot_enabled': True})
            sf.write(path, x, 24000)
            with patch.object(voice, '_synthesize_eleven_file', return_value=str(path)):
                result = Path(voice._synthesize_eleven_effect_file('Teste'))
                try:
                    self.assertFalse(path.exists())
                    y, rate = sf.read(result)
                    self.assertEqual(rate, 24000)
                    self.assertEqual(len(y), len(x))
                finally:
                    result.unlink(missing_ok=True)
            sf.write(path, x, 24000)
            with patch.object(voice, '_synthesize_eleven_file', return_value=str(path)), \
                 patch('voice.robot_effect.process_file', side_effect=RuntimeError('DSP')):
                self.assertEqual(voice._synthesize_eleven_effect_file('Teste'), str(path))
                self.assertTrue(path.exists())
                self.assertEqual(voice.last_tts_metrics['robot_effect_error'], 'DSP')
            voice._active_cancel.set()
            with patch.object(voice, '_synthesize_eleven_file', return_value=str(path)):
                self.assertIsNone(voice._synthesize_eleven_effect_file('Teste'))
                self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
