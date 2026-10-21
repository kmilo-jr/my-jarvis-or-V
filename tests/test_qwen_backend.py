import io
import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voice.qwen_backend import QwenBackend
from voice.engine import VoiceEngine
from voice.preferences import save_preferences
from voice.qwen_worker import valid_embedding, validate_prompt, AudioCache


class QwenTests(unittest.TestCase):
    def test_cpu_selection_and_thread_budget_reach_isolated_worker(self):
        backend = QwenBackend({'tts_qwen_device': 'cpu', 'tts_qwen_cpu_threads': 6})
        process = Mock()
        process.stdout = io.StringIO('')
        with patch('voice.qwen_backend.subprocess.Popen', return_value=process) as launch, \
             patch('voice.qwen_backend.threading.Thread'):
            backend._start()
        env = launch.call_args.kwargs['env']
        self.assertEqual(env['V_QWEN_DEVICE'], 'cpu')
        for key in ('V_QWEN_CPU_THREADS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
            self.assertEqual(env[key], '6')

    def test_worker_priority_yields_cpu_without_changing_main_process(self):
        import subprocess
        for enabled in (True, False):
            backend = QwenBackend({'tts_qwen_background_priority': enabled})
            process = Mock()
            process.stdout = io.StringIO('')
            with patch('voice.qwen_backend.subprocess.Popen', return_value=process) as launch, \
                 patch('voice.qwen_backend.threading.Thread'):
                backend._start()
            flags = launch.call_args.kwargs['creationflags']
            priority = getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
            self.assertEqual(bool(flags & priority), bool(enabled and priority))
            self.assertEqual(launch.call_args.kwargs['env']['V_QWEN_CPU_THREADS'], '2')

    def test_game_idle_policy_restores_preference_and_never_interrupts_generation(self):
        backend = QwenBackend({'tts_qwen_idle_seconds': 120})
        backend.game_mode = True
        self.assertEqual(backend._idle_seconds(), 15)
        with patch.object(backend, '_schedule_idle_release') as schedule:
            backend.lock.acquire()
            backend.refresh_idle_policy()
            schedule.assert_not_called()
            backend.lock.release()
            backend.refresh_idle_policy()
            schedule.assert_called_once()
        backend.game_mode = False
        self.assertEqual(backend._idle_seconds(), 120)

    def test_configured_qwen_reserve_reaches_audio_player(self):
        voice = VoiceEngine({'tts_qwen_prebuffer_phrases': 2})
        with patch.object(voice, '_get_qwen', return_value=Mock()), patch.object(voice, '_play_xtts_audio', return_value=True) as player:
            self.assertTrue(voice._speak_qwen('Uma frase. Outra frase.'))
        self.assertEqual(player.call_args.kwargs['reserve'], 2)

    def test_prompt_rejects_another_reference(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / 'reference.wav'
            prompt = Path(folder) / 'prompt.json'
            reference.write_bytes(b'original sample')
            prompt.write_text(json.dumps({'format': 'qwen3_tts_icl_prompt_v1',
                '_v_reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest()}))
            validate_prompt(prompt, reference)
            reference.write_bytes(b'replaced sample')
            with self.assertRaisesRegex(ValueError, 'amostra mudou'):
                validate_prompt(prompt, reference)

    def test_audio_cache_limits_memory_and_separates_reference(self):
        import numpy as np
        cache = AudioCache(limit=16)
        a = np.ones(2, dtype=np.float32)
        cache.put(('sample1', 'text'), a, 24000)
        cache.put(('sample2', 'text'), a * 2, 24000)
        self.assertEqual(cache.get(('sample1', 'text'))[0][0], 1)
        cache.put(('sample3', 'text'), a * 3, 24000)
        self.assertIsNone(cache.get(('sample2', 'text')))
        self.assertEqual(cache.size, 16)
        cache.put('too large', np.zeros(100), 24000)
        self.assertEqual(cache.size, 16)

    def test_qwen_keeps_one_player_for_all_phrases_and_removes_files(self):
        import numpy as np
        import soundfile as sf
        voice = VoiceEngine({'tts_profile': 'qwen_local'})
        backend = Mock()
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / ('part' + str(i) + '.wav') for i in range(2)]
            for path in paths:
                sf.write(path, np.ones(480, dtype=np.float32) * .1, 24000)
            backend.synthesize.side_effect = [str(p) for p in paths]
            def play(chunks, rate, cancel, started, metrics, reserve):
                self.assertEqual(rate, 24000)
                self.assertEqual(reserve, 1)
                self.assertEqual([a.shape for a in chunks], [(480, 1), (480, 1)])
                return True
            with patch.object(voice, '_get_qwen', return_value=backend), \
                 patch.object(voice, '_play_xtts_audio', side_effect=play) as player, \
                 patch.object(voice, '_play_mp3_windows') as old_player:
                self.assertTrue(voice._speak_qwen('Primeira frase. Segunda frase.'))
            player.assert_called_once()
            old_player.assert_not_called()
            self.assertTrue(all(not p.exists() for p in paths))

    def test_embedding_cache_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'embedding.json'
            self.assertFalse(valid_embedding(path))
            for values in ([0.1] * 1024, [0.1], [float('nan')] * 1024):
                path.write_text(json.dumps(values), encoding='utf-8')
                self.assertEqual(valid_embedding(path), len(values) == 1024 and values[0] == 0.1)

    def test_cancel_before_generation_does_not_start_worker(self):
        backend = QwenBackend()
        cancel = threading.Event()
        cancel.set()
        with patch.object(backend, '_start') as start:
            self.assertIsNone(backend.synthesize('Olá.', Path('sample.wav'), cancel))
        start.assert_not_called()

    def test_worker_failure_is_reported_and_stopped(self):
        backend = QwenBackend()
        backend.process = Mock(stdin=io.StringIO())
        backend.responses = queue.Queue()
        backend.responses.put({'ok': False, 'error': 'native failed'})
        with patch.object(backend, '_start'), patch.object(backend, '_stop') as stop:
            with self.assertRaisesRegex(RuntimeError, 'native failed'):
                backend.prepare('sample.wav')
        stop.assert_called_once()

    def test_cancel_during_generation_stops_native_worker(self):
        backend = QwenBackend()
        cancel = threading.Event()
        backend.process = Mock(stdin=io.StringIO())
        backend.responses = Mock()
        def poll(**kwargs):
            cancel.set()
            raise queue.Empty
        backend.responses.get.side_effect = poll
        with patch.object(backend, '_start'), patch.object(backend, '_stop') as stop:
            self.assertIsNone(backend._request({'reference': 'sample.wav'}, cancel))
        stop.assert_called_once()

    def test_preferences_keep_approved_qwen_voice(self):
        voice = VoiceEngine({'tts_profile': 'qwen_local', 'tts_xtts_voice': 'v_alt'})
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.json'
            config.write_text(json.dumps({'voice': voice.config}), encoding='utf-8')
            with patch.object(voice, 'warmup_tts') as warmup:
                save_preferences(voice, 100, False, False, config, xtts_voice='qwen_alt')
            warmup.assert_called_once()
            self.assertEqual(voice.config['tts_profile'], 'qwen_local')
            self.assertFalse(voice.config['tts_xtts_enabled'])
            self.assertEqual(voice.config['tts_xtts_voice'], 'v_alt')

    def test_native_failure_never_silently_uses_another_voice(self):
        voice = VoiceEngine({'tts_profile': 'qwen_local'})
        voice._tts_queue.put(('Olá.', voice._speech_generation))
        voice._tts_queue.put(None)
        with patch.object(voice, '_speak_qwen', return_value=False), \
             patch.object(voice, '_save_tts_diagnostic'), \
             patch.object(voice, '_speak_edge_tts') as edge, \
             patch.object(voice, '_speak_piper') as piper, \
             patch('win32com.client.Dispatch') as sapi:
            voice._tts_loop()
        edge.assert_not_called()
        piper.assert_not_called()
        sapi.assert_not_called()
        self.assertIn('V Alt', voice.last_tts_error)


if __name__ == '__main__':
    unittest.main()
