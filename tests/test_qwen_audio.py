import unittest
import numpy as np
from voice.qwen_audio import shorten_phrase_silence


class PhraseSilenceTests(unittest.TestCase):
    def test_preserves_speech_and_internal_pause_exactly(self):
        speech = np.concatenate([np.full(2000, .1), np.zeros(6000), np.full(2000, .02)])
        original = np.concatenate([np.zeros(6000), speech, np.zeros(8000)])
        result = shorten_phrase_silence(original, 10000)
        np.testing.assert_array_equal(result, np.concatenate([np.zeros(800), speech, np.zeros(1600)]))

    def test_quiet_empty_and_continuous_audio_unchanged(self):
        for audio in (np.zeros(10000), np.array([]), np.full(10000, .0001), np.full((480, 1), .1)):
            np.testing.assert_array_equal(shorten_phrase_silence(audio, 24000), audio)

    def test_retains_quiet_consonant_and_channel_shape(self):
        audio = np.concatenate([np.zeros(4000), np.full(1000, .0007), np.full(1000, .1), np.zeros(4000)])[:, None]
        result = shorten_phrase_silence(audio, 10000)
        self.assertEqual(result.shape, (4400, 1))
        np.testing.assert_array_equal(result[800:2800], audio[4000:6000])
