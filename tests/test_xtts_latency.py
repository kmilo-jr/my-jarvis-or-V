import json
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from voice.engine import VoiceEngine


class CallbackStop(Exception):
    pass


class CallbackAbort(Exception):
    pass


class AudioDevice:
    """A device clock independent of the synthesis generator."""

    def __init__(self, **kwargs):
        self.callback = kwargs['callback']
        self.finished = kwargs['finished_callback']
        self.frames = kwargs['blocksize']
        self.active = False
        self.closed = False
        self.blocks = []
        self.heard = threading.Event()
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        self.active = True

        def pump():
            try:
                while not self.stop.is_set():
                    audio = np.zeros((self.frames, 1), dtype=np.float32)
                    done = False
                    try:
                        self.callback(audio, self.frames,
                                      SimpleNamespace(outputBufferDacTime=0, currentTime=0),
                                      SimpleNamespace(output_underflow=False))
                    except CallbackStop:
                        done = True
                    except CallbackAbort:
                        break
                    self.blocks.append(audio.copy())
                    if np.any(audio):
                        self.heard.set()
                    if done:
                        break
                    self.stop.wait(.002)
            finally:
                self.active = False
                self.finished()

        self.thread = threading.Thread(target=pump, daemon=True)
        self.thread.start()

    def abort(self):
        self.stop.set()

    def close(self):
        self.closed = True
        if self.thread:
            self.thread.join(1)


class XttsLatencyTests(unittest.TestCase):
    def test_buffered_playback_starts_with_two_phrases_while_third_is_preparing(self):
        voice = VoiceEngine({})
        heard = threading.Event()
        generated = []
        with tempfile.TemporaryDirectory() as folder:
            def synthesize(text):
                if text == 'third':
                    self.assertTrue(heard.wait(2), 'Waited for the entire answer')
                generated.append(text)
                path = Path(folder) / text
                path.write_bytes(b'complete audio')
                return str(path)
            def play(path):
                self.assertGreaterEqual(len(generated), 2)
                heard.set()
                return True
            with patch.object(voice, '_play_mp3_windows', side_effect=play):
                self.assertTrue(voice._speak_chunks(['first', 'second', 'third'], synthesize, prebuffer=2))
            self.assertEqual(generated, ['first', 'second', 'third'])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_xtts_cache_reuses_audio_but_changes_with_sample_or_speed(self):
        import soundfile as sf
        voice = VoiceEngine({'tts_xtts_polish_enabled': False})
        with tempfile.TemporaryDirectory() as folder:
            prime, alt = Path(folder) / 'prime.wav', Path(folder) / 'alt.wav'
            prime.write_bytes(b'prime'); alt.write_bytes(b'alt')
            voice.config.update(tts_xtts_reference=str(prime), tts_xtts_reference_alt=str(alt))
            engine = Mock()
            engine.synthesizer = None
            def synthesize(**kwargs):
                sf.write(kwargs['file_path'], np.full(2400, .1), 24000)
            engine.tts_to_file.side_effect = synthesize
            paths = []
            with patch.object(voice, '_load_xtts', return_value=engine):
                for key, speed in [('v_prime', 1.0), ('v_prime', 1.0), ('v_alt', 1.0), ('v_alt', 1.08)]:
                    voice.config.update(tts_xtts_voice=key, tts_xtts_speed_alt=speed)
                    paths.append(voice._synthesize_xtts_file('Olá.'))
            self.assertTrue(all(paths))
            self.assertEqual(engine.tts_to_file.call_count, 3)
            for path in paths:
                Path(path).unlink()

    def test_complete_response_joins_all_phrases_before_one_playback(self):
        voice = VoiceEngine({})
        generated = []
        played = []
        with tempfile.TemporaryDirectory() as folder:
            def synthesize(text):
                generated.append(text)
                path = Path(folder) / (str(len(generated)) + '.wav')
                with wave.open(str(path), 'wb') as wav:
                    wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                    wav.writeframes(bytes([len(generated), 0]) * 2400)
                return str(path)

            def play(path):
                self.assertEqual(generated, ['Primeira frase.', 'Segunda frase.', 'Última frase.'])
                with wave.open(path, 'rb') as wav:
                    played.append(wav.readframes(wav.getnframes()))
                return True

            with patch.object(voice, '_synthesize_xtts_file', side_effect=synthesize), \
                 patch.object(voice, '_play_mp3_windows', side_effect=play):
                self.assertTrue(voice._speak_xtts('Primeira frase. Segunda frase. Última frase.'))
            self.assertEqual(played, [b'\x01\x00' * 2400 + b'\x02\x00' * 2400 + b'\x03\x00' * 2400])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_failed_later_phrase_never_plays_truncated_response(self):
        voice = VoiceEngine({})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'first.wav'
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\x01\x00' * 2400)
            with patch.object(voice, '_synthesize_xtts_file', side_effect=[str(path), None]), \
                 patch.object(voice, '_play_mp3_windows') as play:
                self.assertFalse(voice._speak_xtts('Primeira frase. Segunda frase.'))
            play.assert_not_called()
            self.assertFalse(path.exists())

    def test_long_response_preserves_text_and_sentence_boundaries(self):
        voice = VoiceEngine({})
        text = 'Primeira frase completa. ' + 'Uma explicação mais extensa sem interrupção. ' * 60
        chunks = voice._split_xtts_response(text)
        self.assertEqual(' '.join(chunks), text.strip())
        self.assertTrue(all(c.endswith('.') for c in chunks))
        with patch.object(voice, '_ensure_tts_thread'):
            voice.speak(text)
        self.assertEqual(voice._tts_queue.get_nowait()[0], text.strip())

    def test_both_cloned_voices_can_use_complete_audio_fallback(self):
        saved = json.loads((Path(__file__).resolve().parents[1] / 'config/default.json').read_text(encoding='utf-8'))['voice']
        for settings in ({}, saved):
            for profile in ('v_prime', 'v_alt'):
                with self.subTest(settings='saved' if settings else 'defaults', voice=profile):
                    voice = VoiceEngine(dict(settings, tts_xtts_voice=profile, tts_xtts_enabled=True, tts_xtts_streaming_enabled=False))
                    complete = threading.Event()
                    played = []
                    with tempfile.TemporaryDirectory() as folder:
                        path = Path(folder) / 'whole-phrase.wav'
                        content = b'beginning-middle-end-of-phrase'

                        def synthesize(text):
                            path.write_bytes(content)
                            complete.set()
                            return str(path)

                        def play(filename):
                            self.assertTrue(complete.is_set())
                            played.append(Path(filename).read_bytes())
                            return True

                        with patch.object(voice, '_speak_xtts_streaming') as streaming, \
                             patch.object(voice, '_synthesize_xtts_response', side_effect=synthesize), \
                             patch.object(voice, '_play_mp3_windows', side_effect=play):
                            self.assertTrue(voice._speak_xtts('Estou pronto para ouvir.'))
                        streaming.assert_not_called()
                        self.assertEqual(played, [content])
                        self.assertFalse(path.exists())

    def play(self, engine, chunks, factory=None, engine_name=None):
        devices = []

        def open_device(**kwargs):
            device = AudioDevice(**kwargs)
            devices.append(device)
            return device

        self.devices = devices
        metrics = {'engine': engine_name} if engine_name else {}
        sd = SimpleNamespace(OutputStream=factory or open_device,
                             CallbackStop=CallbackStop, CallbackAbort=CallbackAbort)
        with patch.dict(sys.modules, {'sounddevice': sd}):
            result = engine._play_xtts_audio(chunks, 24000, engine._active_cancel,
                                             time.perf_counter(), metrics)
        return result, metrics

    def test_qwen_requests_safer_device_buffer_without_changing_samples(self):
        settings = {}
        devices = []
        def factory(**kwargs):
            settings.update(kwargs)
            device = AudioDevice(**kwargs); devices.append(device); return device
        samples = np.full((2400, 1), .2, dtype=np.float32)
        result, metrics = self.play(VoiceEngine({}), iter([samples]), factory, 'qwen3_0.6b')
        self.assertTrue(result)
        self.assertEqual(settings['latency'], 'high')
        actual = np.concatenate(devices[0].blocks).reshape(-1)
        np.testing.assert_array_equal(actual[actual != 0], samples.reshape(-1))

    def test_many_queued_chunks_keep_sample_order_and_close_device(self):
        voice = VoiceEngine({'tts_xtts_stream_prebuffer_chunks': 2})
        chunks = [np.full((731, 1), (i + 1)/100, dtype=np.float32) for i in range(50)]
        result, metrics = self.play(voice, iter(chunks), engine_name='qwen3_0.6b')
        self.assertTrue(result)
        actual = np.concatenate(self.devices[0].blocks).reshape(-1)
        np.testing.assert_array_equal(actual[actual != 0], np.concatenate(chunks).reshape(-1))
        self.assertTrue(self.devices[0].closed)

    def test_audio_starts_before_generation_finishes_and_keeps_every_sample(self):
        voice = VoiceEngine({})
        first = np.full((1137, 1), .2, dtype=np.float32)
        second = np.full((957, 1), .4, dtype=np.float32)

        def chunks():
            yield first
            self.assertTrue(self.devices[0].heard.wait(1), 'Playback waited for full synthesis')
            yield second

        result, metrics = self.play(voice, chunks())
        self.assertTrue(result)
        actual = np.concatenate(self.devices[0].blocks).reshape(-1)
        # Ignore device-padding silence; real samples must retain their order.
        np.testing.assert_array_equal(actual[actual != 0], np.concatenate((first, second)).reshape(-1))
        self.assertLessEqual(metrics['first_audio_ms'], metrics['generation_ms'])
        self.assertTrue(self.devices[0].closed)

    def test_stream_reserves_three_blocks_before_starting(self):
        voice = VoiceEngine({'tts_xtts_stream_prebuffer_chunks': 3})
        def chunks():
            yield np.full((960, 1), .1, dtype=np.float32)
            self.assertFalse(self.devices[0].active)
            yield np.full((960, 1), .2, dtype=np.float32)
            self.assertFalse(self.devices[0].active)
            yield np.full((960, 1), .3, dtype=np.float32)
            self.assertTrue(self.devices[0].heard.wait(1))
        result, metrics = self.play(voice, chunks())
        self.assertTrue(result)
        actual = np.concatenate(self.devices[0].blocks).reshape(-1)
        expected = np.concatenate([np.full(960, x, dtype=np.float32) for x in (.1, .2, .3)])
        np.testing.assert_array_equal(actual[actual != 0], expected)

    def test_short_stream_plays_even_when_smaller_than_reserve(self):
        voice = VoiceEngine({'tts_xtts_stream_prebuffer_chunks': 3})
        result, _ = self.play(voice, iter([np.full((960, 1), .1, dtype=np.float32)]))
        self.assertTrue(result)
        self.assertTrue(self.devices[0].closed)

    def test_cancel_discards_queued_audio_and_closes_generator(self):
        voice = VoiceEngine({})
        closed = threading.Event()

        def chunks():
            try:
                yield np.full((960, 1), .2, dtype=np.float32)
                self.assertTrue(self.devices[0].heard.wait(1))
                voice.stop_speaking()
                yield np.full((960, 1), .4, dtype=np.float32)
            finally:
                closed.set()

        result, _ = self.play(voice, chunks())
        self.assertTrue(result)  # cancellation never replays via fallback
        actual = np.concatenate(self.devices[0].blocks)
        self.assertFalse(np.any(actual == .4))
        self.assertTrue(closed.is_set())
        self.assertTrue(self.devices[0].closed)

    def test_device_failure_allows_file_fallback(self):
        voice = VoiceEngine({})
        chunks = (np.ones((960, 1), dtype=np.float32) for _ in range(1))
        result, _ = self.play(voice, chunks, Mock(side_effect=RuntimeError('device unavailable')))
        self.assertIsNone(result)

    def test_generation_failure_after_audio_does_not_replay_sentence(self):
        voice = VoiceEngine({})

        def chunks():
            yield np.full((960, 1), .2, dtype=np.float32)
            self.assertTrue(self.devices[0].heard.wait(1))
            raise RuntimeError('synthesis stopped')

        result, _ = self.play(voice, chunks())
        self.assertTrue(result)
        self.assertEqual(voice.last_tts_error, 'RuntimeError: synthesis stopped')
        actual = np.concatenate(self.devices[0].blocks).reshape(-1)
        self.assertEqual(np.count_nonzero(actual), 960, 'Ready audio was cut by the next generation failure')

    def test_speech_waits_for_reference_instead_of_using_another_voice(self):
        voice = VoiceEngine({'tts_profile': 'xtts_local'})
        voice._xtts_warmup_active.set()
        result = []
        with patch.object(voice, '_speak_chunks', return_value=True) as speak:
            worker = threading.Thread(target=lambda: result.append(voice._speak_xtts('Olá.')))
            worker.start()
            try:
                worker.join(.1)
                self.assertTrue(worker.is_alive())
                speak.assert_not_called()
            finally:
                voice._xtts_warmup_active.clear()
                worker.join(2)
            self.assertEqual(result, [True])
            speak.assert_called_once()

    def test_waiting_for_reference_can_be_cancelled_without_fallback(self):
        voice = VoiceEngine({'tts_profile': 'xtts_local'})
        voice._xtts_warmup_active.set()
        result = []
        with patch.object(voice, '_speak_chunks') as speak:
            worker = threading.Thread(target=lambda: result.append(voice._speak_xtts('Olá.')))
            worker.start()
            voice.stop_speaking()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result, [True])
            speak.assert_not_called()

    def test_warmup_flag_is_set_before_worker_and_duplicate_start_is_ignored(self):
        voice = VoiceEngine({'tts_profile': 'xtts_local'})
        with patch('voice.engine.threading.Thread') as thread:
            self.assertTrue(voice.warmup_tts())
            self.assertTrue(voice._xtts_warmup_active.is_set())
            self.assertTrue(voice.warmup_tts())
        thread.assert_called_once()

    def test_reference_is_cached_and_recomputed_after_sample_changes(self):
        voice = VoiceEngine({})
        model = Mock()
        engine = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / 'sample.wav'
            reference.write_bytes(b'first')
            first = voice._get_xtts_voice(engine, reference)
            self.assertIs(voice._get_xtts_voice(engine, reference), first)
            model.clone_voice.assert_called_once()
            reference.write_bytes(b'new reference sample')
            voice._get_xtts_voice(engine, reference)
            self.assertEqual(model.clone_voice.call_count, 2)

    def test_switching_samples_uses_separate_speaker_embeddings(self):
        voice = VoiceEngine({})
        first, second = {'speaker_embedding': object()}, {'speaker_embedding': object()}
        model = Mock()
        model.clone_voice.side_effect = [first, second]
        engine = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        with tempfile.TemporaryDirectory() as folder:
            prime, alt = Path(folder) / 'prime.wav', Path(folder) / 'alt.wav'
            prime.write_bytes(b'prime')
            alt.write_bytes(b'alt')
            voice.config.update(tts_xtts_reference=str(prime), tts_xtts_reference_alt=str(alt))
            for key, expected in [('v_prime', first), ('v_alt', second), ('v_prime', first)]:
                voice.config['tts_xtts_voice'] = key
                self.assertIs(voice._get_xtts_voice(engine, voice._resolve_xtts_reference()), expected)
            self.assertEqual(model.clone_voice.call_count, 2)
            self.assertEqual(model.clone_voice.call_args_list[1].args[0], [str(alt)])

    def test_polish_preserves_quiet_final_sound(self):
        import soundfile as sf
        voice = VoiceEngine({'tts_xtts_highpass_hz': 0, 'tts_xtts_trim_pad_ms': 38})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'quiet-ending.wav'
            # A soft 200 ms final phoneme after the loud body must survive.
            audio = np.concatenate([np.full(2400, .5), np.full(4800, .004), np.zeros(4800)])
            sf.write(path, audio, 24000, subtype='PCM_16')
            voice._polish_xtts_file(str(path))
            result, rate = sf.read(path)
            self.assertGreaterEqual(len(result), 7200)
            self.assertGreater(np.abs(result[7000]), .001)

    def test_long_reply_keeps_streaming_with_selected_voice_speed(self):
        voice = VoiceEngine({'tts_xtts_voice': 'v_alt', 'tts_xtts_speed_alt': 1.08,
                             'tts_xtts_polish_enabled': False})
        model = Mock()

        def synthesize(*args, **kwargs):
            yield np.full(480, .2, dtype=np.float32)

        model.inference_stream.side_effect = synthesize
        engine = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model, output_sample_rate=24000))
        identity = {'gpt_conditioning_latents': object(), 'speaker_embedding': object()}
        received = []

        def play(chunks, *args):
            received.extend(chunks)
            return True

        text = ('Uma frase completa para explicar o andamento da tarefa. ' * 12).strip()
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / 'sample.wav'
            reference.write_bytes(b'sample')
            with patch.object(voice, '_resolve_xtts_reference', return_value=reference), \
                 patch.object(voice, '_load_xtts', return_value=engine), \
                 patch.object(voice, '_get_xtts_voice', return_value=identity), \
                 patch.object(voice, '_play_xtts_audio', side_effect=play):
                self.assertTrue(voice._speak_xtts_streaming(text))
        self.assertGreater(len(received), 1)
        self.assertEqual(' '.join(call.args[0] for call in model.inference_stream.call_args_list), text)
        for call in model.inference_stream.call_args_list:
            self.assertEqual(call.kwargs['speed'], 1.08)
            self.assertFalse(call.kwargs['enable_text_splitting'])
            self.assertIs(call.args[2], identity['gpt_conditioning_latents'])


if __name__ == '__main__':
    unittest.main()
