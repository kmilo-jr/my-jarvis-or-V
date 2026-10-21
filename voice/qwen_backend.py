"""Own a resident Qwen worker without loading native CUDA libraries into the UI."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import math


class QwenBackend:
    def __init__(self, config=None):
        self.config = config or {}
        self.process = None
        self.responses = None
        self.lock = threading.Lock()
        self.closed = False
        self.game_mode = False
        self.last_metrics = {}
        self._idle_timer = None
        self._last_activity = time.monotonic()

    def _schedule_idle_release(self):
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._last_activity = time.monotonic()
        seconds = self._idle_seconds()
        if self.closed or self.process is None or seconds <= 0:
            return
        self._idle_timer = threading.Timer(seconds, self._release_idle)
        self._idle_timer.daemon = True
        self._idle_timer.start()

    def _idle_seconds(self):
        if self.game_mode:
            return 15
        try:
            seconds = float(self.config.get('tts_qwen_idle_seconds', 120))
            return min(3600, max(0, seconds)) if math.isfinite(seconds) else 120
        except (TypeError, ValueError):
            return 120

    def refresh_idle_policy(self):
        # The generation's finally block reschedules if it currently owns the lock.
        if self.lock.acquire(blocking=False):
            try:
                self._schedule_idle_release()
            finally:
                self.lock.release()

    def _release_idle(self):
        # Never terminate a model while synthesis owns this lock. Its finally
        # block rearms the idle timer when it finishes.
        if not self.lock.acquire(blocking=False):
            return
        try:
            seconds = self._idle_seconds()
            if not self.closed and seconds > 0 and time.monotonic() - self._last_activity >= seconds:
                self._stop()
                self.last_metrics['released_after_idle'] = True
        finally:
            self.lock.release()

    def _stop(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            process.stdin.close()

    def close(self):
        self.closed = True
        if self._idle_timer is not None:
            self._idle_timer.cancel()
        self._stop()

    def _start(self):
        if self.closed:
            raise RuntimeError('Motor de voz encerrado')
        if self.process is not None and self.process.poll() is None:
            return
        self._stop()
        root = Path(__file__).resolve().parents[1]
        responses = queue.Queue()
        threads = str(max(1, min(8, int(self.config.get('tts_qwen_cpu_threads', 2)))))
        process = subprocess.Popen(
            [sys.executable, '-u', str(root / 'voice/qwen_worker.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', cwd=str(root),
            env=dict(os.environ, PYTHONIOENCODING='utf-8', V_QWEN_CPU_THREADS=threads,
                     V_QWEN_DEVICE=str(self.config.get('tts_qwen_device', 'auto')).lower(),
                     V_QWEN_GPU_BACKGROUND='1' if self.config.get('tts_qwen_gpu_background_priority', True) else '0',
                     OMP_NUM_THREADS=threads, OPENBLAS_NUM_THREADS=threads, MKL_NUM_THREADS=threads),
            # Yield CPU time to foreground video/UI under contention. Keep the
            # main process and its real-time audio callback at normal priority.
            creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                           | (getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)
                              if self.config.get('tts_qwen_background_priority', True) else 0)),
        )
        self.process, self.responses = process, responses

        def read():
            try:
                for line in process.stdout:
                    try:
                        responses.put(json.loads(line))
                    except ValueError:
                        pass
            finally:
                process.stdout.close()
                responses.put({'ok': False, 'error': 'Motor Qwen encerrou inesperadamente; consulte logs/qwen_worker.log'})
        threading.Thread(target=read, daemon=True, name='V-Qwen-Output').start()

    def _request(self, payload, cancel=None):
        payload = dict(payload, prompt=self.config.get('tts_qwen_prompt', ''))
        while not self.lock.acquire(timeout=.05):
            if self.closed:
                raise RuntimeError('Motor de voz encerrado')
            if cancel is not None and cancel.is_set():
                return None
        try:
            if cancel is not None and cancel.is_set():
                return None
            self._start()
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
            self.process.stdin.flush()
            deadline = time.monotonic() + 120
            while True:
                if self.closed:
                    raise RuntimeError('Motor de voz encerrado')
                if cancel is not None and cancel.is_set():
                    self._stop()
                    return None
                if time.monotonic() > deadline:
                    self._stop()
                    raise TimeoutError('A geração da voz excedeu 120 segundos')
                try:
                    response = self.responses.get(timeout=.05)
                except queue.Empty:
                    continue
                if not response.get('ok'):
                    self._stop()
                    raise RuntimeError(response.get('error', 'Falha na voz Qwen'))
                self.last_metrics = dict(response, engine='qwen3_0.6b', reference=Path(payload['reference']).name)
                return response
        finally:
            try:
                self._schedule_idle_release()
            finally:
                self.lock.release()

    def prepare(self, reference):
        return self._request({'action': 'prepare', 'reference': str(reference)})

    def synthesize(self, text, reference, cancel):
        fd, path = tempfile.mkstemp(prefix='v_qwen_', suffix='.wav')
        os.close(fd)
        try:
            result = self._request({'action': 'synthesize', 'reference': str(reference),
                                    'text': text, 'output': path}, cancel)
            if result is None or cancel.is_set():
                Path(path).unlink(missing_ok=True)
                return None
            return path
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
