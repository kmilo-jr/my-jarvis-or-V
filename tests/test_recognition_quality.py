import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import threading

import numpy as np

from voice.engine import VoiceEngine
from voice.endpoint import AdaptiveEndpointDetector


def segment(text, score, silence=0.1):
    return SimpleNamespace(text=text, avg_logprob=score, no_speech_prob=silence)


class RecognitionQualityTests(unittest.TestCase):
    def test_word_error_metric_counts_lost_negation(self):
        from voice.recognition_eval import word_errors
        result = word_errors('V, não desligue o computador.', 'V desligue o computador')
        self.assertEqual(result['errors'], 1)
        self.assertEqual(result['wer_percent'], 20)
        self.assertEqual(word_errors('V, BOM DIA!', 'v bom dia')['errors'], 0)

    def engine(self, results):
        engine = VoiceEngine({})
        info = SimpleNamespace(language="pt", language_probability=1.0)
        engine._model = Mock()
        engine._model.transcribe.side_effect = [(iter(parts), info) if isinstance(parts, list) else parts for parts in results]
        return engine

    def test_confident_speech_needs_only_one_pass(self):
        engine = self.engine([[segment("V, abra o navegador", -0.2)]])
        text, meta = engine.transcribe(np.ones(16000))
        self.assertEqual(text, "V, abra o navegador")
        self.assertFalse(meta["recognition_retry"])
        self.assertEqual(engine._model.transcribe.call_count, 1)

    def test_uncertain_speech_uses_better_second_result(self):
        engine = self.engine([[segment("texto errado", -1.2)], [segment("V, abra o Spotify", -0.3)]])
        text, meta = engine.transcribe(np.ones(16000))
        self.assertEqual(text, "V, abra o Spotify")
        self.assertTrue(meta["recognition_retry"])
        self.assertEqual(engine._model.transcribe.call_args.kwargs["beam_size"], 5)

    def test_worse_retry_keeps_first_result(self):
        engine = self.engine([[segment("original", -0.9)], [segment("pior", -1.2)]])
        self.assertEqual(engine.transcribe(np.ones(16000))[0], "original")

    def test_failed_retry_preserves_recognition(self):
        engine = self.engine([[segment("original", -0.9)], RuntimeError("unavailable")])
        self.assertEqual(engine.transcribe(np.ones(16000))[0], "original")

    def test_silence_and_empty_vad_do_not_trigger_retry(self):
        for parts in ([], [segment("ruído", -1.2, 0.95)]):
            engine = self.engine([parts])
            text, meta = engine.transcribe(np.ones(16000))
            self.assertEqual(text, '')
            self.assertEqual(engine._model.transcribe.call_count, 1)

    def test_bad_segment_does_not_leave_a_partial_command(self):
        engine = self.engine([[segment('não', -1.8), segment('desligue o computador', -0.2)]])
        engine.config['recognition_retry_enabled'] = False
        text, meta = engine.transcribe(np.ones(16000))
        self.assertEqual(text, '')
        self.assertEqual(meta['reason'], 'uncertain_speech')
        self.assertTrue(meta['needs_repeat'])

    def test_retry_cannot_replace_original_with_repetitive_text(self):
        repeated = segment('V V V V V', -0.6)
        repeated.compression_ratio = 3.1
        engine = self.engine([[segment('original', -0.9)], [repeated]])
        self.assertEqual(engine.transcribe(np.ones(16000))[0], 'original')

    def test_retry_can_recover_a_low_confidence_utterance(self):
        engine = self.engine([[segment('incerto', -1.8)], [segment('V, bom dia', -0.3)]])
        text, meta = engine.transcribe(np.ones(16000))
        self.assertEqual(text, 'V, bom dia')
        self.assertFalse(meta['needs_repeat'])

    def test_valid_short_speech_is_not_removed_by_silence_probability_alone(self):
        engine = self.engine([[segment('V, pare', -0.2, 0.8)]])
        self.assertEqual(engine.transcribe(np.ones(16000))[0], 'V, pare')

    def test_nonfinite_confidence_does_not_reach_commands(self):
        engine = self.engine([[segment('V, abra', float('nan'))]])
        self.assertEqual(engine.transcribe(np.ones(16000))[0], '')

    def test_cancellation_during_inference_discards_late_result(self):
        engine = VoiceEngine({})
        stop = threading.Event()
        engine.capture_phrase = Mock(return_value=(np.ones(16000), {}))
        def transcribe(*args, **kwargs):
            stop.set()
            return 'V, abra o navegador', {'reason': 'ok'}
        engine.transcribe = Mock(side_effect=transcribe)
        text, meta = engine.listen_and_transcribe(stop_event=stop)
        self.assertEqual(text, '')
        self.assertEqual(meta['reason'], 'cancelled')

    def capture_with(self, feed):
        engine = VoiceEngine({})
        engine._device_info = Mock(return_value=({'name': 'Test mic'}, 16000))
        engine._profile_key = Mock(return_value='test')
        engine._ambient_profiles['test'] = {'noise_rms': 0.0001}
        stream = Mock()
        def factory(**kwargs):
            stream.__enter__ = Mock(side_effect=lambda: feed(engine, kwargs['callback']))
            stream.__exit__ = Mock(return_value=False)
            return stream
        with patch('sounddevice.InputStream', side_effect=factory), patch('sounddevice.check_input_settings'):
            return engine.capture_phrase()

    def test_queue_overflow_is_reported_instead_of_transcribing_gaps(self):
        def feed(engine, callback):
            for _ in range(121):
                callback(np.zeros((480, 1)), 480, None, SimpleNamespace(input_overflow=False))
        audio, meta = self.capture_with(feed)
        self.assertEqual(audio.size, 0)
        self.assertEqual(meta['reason'], 'audio_overflow')
        self.assertTrue(meta['needs_repeat'])

    def test_driver_overflow_is_reported(self):
        def feed(engine, callback):
            callback(np.zeros((480, 1)), 480, None, SimpleNamespace(input_overflow=True))
        self.assertEqual(self.capture_with(feed)[1]['reason'], 'audio_overflow')

    def test_brief_tts_during_capture_is_detected_after_playback_ends(self):
        def feed(engine, callback):
            engine._tts_epoch += 1
        self.assertEqual(self.capture_with(feed)[1]['reason'], 'tts_overlap')

    def test_silero_failure_keeps_fallback(self):
        engine = self.engine([RuntimeError("ONNX VAD unavailable"), [segment("Olá", -0.1)]])
        text, meta = engine.transcribe(np.ones(16000))
        self.assertEqual(text, "Olá")
        self.assertEqual(meta["silero_vad"], "fallback")
        self.assertFalse(engine._model.transcribe.call_args.kwargs["vad_filter"])

    def test_downsampling_rejects_high_frequency_alias(self):
        engine = VoiceEngine({"max_gain": 1})
        for rate in (44100, 48000):
            t = np.arange(rate) / rate
            low, _ = engine._prepare_audio(0.1 * np.sin(2 * np.pi * 1000 * t), rate)
            high, _ = engine._prepare_audio(0.1 * np.sin(2 * np.pi * 12000 * t), rate)
            self.assertEqual(low.size, 16000)
            self.assertGreater(engine._rms(low[100:-100]), 0.06)
            self.assertLess(engine._rms(high[100:-100]), 0.001)

    def test_short_audio_keeps_length(self):
        engine = VoiceEngine({})
        audio, _ = engine._prepare_audio(np.array([0.1, -0.1, 0.1]), 48000)
        self.assertEqual(audio.size, 1)

    def test_long_sentence_preserves_half_second_pause(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config/default.json").read_text(encoding="utf-8"))["voice"]
        detector = AdaptiveEndpointDetector(block_seconds=0.03,
            short_end_silence_seconds=config["v2_short_end_silence_seconds"],
            long_end_silence_seconds=config["v2_long_end_silence_seconds"],
            long_phrase_after_seconds=config["v2_long_phrase_after_seconds"])
        for _ in range(40):
            detector.push(hot=True, quiet=False)
        for _ in range(17):
            detector.push(hot=False, quiet=True)
        self.assertFalse(detector.ended)
        for _ in range(5):
            detector.push(hot=False, quiet=True)
        self.assertTrue(detector.ended)

    def test_unpunctuated_reply_starts_with_bounded_chunk(self):
        engine = VoiceEngine({"tts_chunk_max_chars": 150})
        text = " ".join(["uma resposta longa sem pontuação"] * 20)
        chunks = engine._split_tts_chunks(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 150 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)


if __name__ == "__main__":
    unittest.main()
