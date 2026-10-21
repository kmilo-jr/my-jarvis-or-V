import json
import time
import unittest
from unittest.mock import Mock, patch
from voice.qwen_backend import QwenBackend
from brain.service import BrainService


class GpuBudgetTests(unittest.TestCase):
    def test_invalid_idle_setting_uses_safe_default(self):
        for value in ('invalid', None, float('nan'), float('inf')):
            backend = QwenBackend({'tts_qwen_idle_seconds': value})
            self.assertEqual(backend._idle_seconds(),120)

    def test_closed_backend_does_not_wait_for_busy_lock(self):
        backend = QwenBackend(); backend.lock.acquire(); backend.closed = True
        try:
            with self.assertRaisesRegex(RuntimeError, 'encerrado'):
                backend.prepare('unused.wav')
        finally:
            backend.lock.release()
    def test_idle_release_does_not_close_backend_or_interrupt_busy_generation(self):
        backend = QwenBackend({'tts_qwen_idle_seconds': 1})
        backend._last_activity = time.monotonic()-5
        with patch.object(backend, '_stop') as stop:
            backend.lock.acquire()
            backend._release_idle(); stop.assert_not_called()
            backend.lock.release()
            backend._release_idle(); stop.assert_called_once()
        self.assertFalse(backend.closed)

    def test_stale_timer_does_not_stop_recent_work(self):
        backend = QwenBackend({'tts_qwen_idle_seconds': 120})
        with patch.object(backend, '_stop') as stop:
            backend._release_idle(); stop.assert_not_called()

    def test_timer_rearmed_and_cancelled_on_close(self):
        backend = QwenBackend({'tts_qwen_idle_seconds': 120})
        backend.process = Mock()
        with patch('voice.qwen_backend.threading.Timer') as timer, patch.object(backend, '_stop'):
            backend._schedule_idle_release(); backend._schedule_idle_release()
            self.assertEqual(timer.call_count,2)
            timer.return_value.cancel.assert_called_once()
            backend.close()
            self.assertEqual(timer.return_value.cancel.call_count,2)

    def test_cpu_ollama_payload_has_no_gpu_and_unloads_after_reply(self):
        brain = BrainService({'ollama_cpu_only': True, 'keep_alive': 0, 'groq_enabled': False})
        response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"message":{"content":"ok"}}'
        with patch('urllib.request.urlopen', return_value=response) as request:
            self.assertEqual(brain._request_chat([]), 'ok')
        payload=json.loads(request.call_args.args[0].data)
        self.assertEqual(payload['options']['num_gpu'],0)
        self.assertEqual(payload['options']['num_thread'],2)
        self.assertEqual(payload['keep_alive'],0)
