"""Resident local synthesis worker. Stdout is a JSON protocol, logs are separate."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from collections import OrderedDict

ROOT = Path(__file__).resolve().parents[1]


def valid_embedding(path):
    try:
        values = json.loads(path.read_text(encoding='utf-8'))
        return isinstance(values, list) and len(values) == 1024 and all(
            isinstance(v, (int, float)) and math.isfinite(v) for v in values)
    except (OSError, ValueError):
        return False


def validate_prompt(path, reference):
    """Do not reuse another sample's pronunciation context after replacement."""
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('format') != 'qwen3_tts_icl_prompt_v1':
        raise ValueError('Referência de pronúncia Qwen inválida')
    if data.get('_v_reference_sha256') != hashlib.sha256(reference.read_bytes()).hexdigest():
        raise ValueError('A amostra mudou; recrie a referência de pronúncia Qwen')


class AudioCache:
    """Bounded in-memory PCM cache; never leave old response files on disk."""
    def __init__(self, limit=8 * 1024 * 1024):
        self.limit = limit
        self.items = OrderedDict()
        self.size = 0

    def get(self, key):
        value = self.items.get(key)
        if value is not None:
            self.items.move_to_end(key)
        return value

    def put(self, key, audio, rate):
        if audio.nbytes > self.limit:
            return
        old = self.items.pop(key, None)
        if old is not None:
            self.size -= old[0].nbytes
        self.items[key] = (audio, rate)
        self.size += audio.nbytes
        while self.size > self.limit:
            _, (removed, _) = self.items.popitem(last=False)
            self.size -= removed.nbytes


def main():
    (ROOT / 'logs').mkdir(exist_ok=True)
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), 'w', encoding='utf-8', buffering=1)
    with (ROOT / 'logs/qwen_worker.log').open('a', encoding='utf-8') as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())
        from gpu_priority import lower_worker_gpu_priority
        gpu_priority = (lower_worker_gpu_priority() if os.environ.get('V_QWEN_GPU_BACKGROUND', '1') == '1'
                        else {'applied': False, 'status': 'disabled'})
        print('GPU scheduling:', json.dumps(gpu_priority), flush=True)
        from qwen_native import BASE, Params, init, load, extract, synthesize, synthesize_icl, free_result, free, last_error, np, sf, CPU_THREADS, DEVICE, backend
        ctx = init()
        loaded = False
        embeddings = {}
        warmed = set()
        validated = set()
        cache = AudioCache()
        try:
            for line in sys.stdin:
                try:
                    request = json.loads(line)
                    started = time.perf_counter()
                    if not loaded:
                        if not load(ctx, str(BASE / 'models').encode(), b'qwen-talker-0.6b-base-Q8_0.gguf'):
                            raise RuntimeError(last_error(ctx))
                        loaded = True
                        if DEVICE == 'cpu' and (backend() or b'').decode().lower() != 'cpu':
                            raise RuntimeError('O motor não confirmou CPU; geração cancelada para não usar GPU.')
                    reference = Path(request['reference']).resolve()
                    stat = reference.stat()
                    key = (str(reference), stat.st_size, stat.st_mtime_ns)
                    prompt = request.get('prompt')
                    if prompt:
                        path = Path(prompt)
                        if not path.is_absolute():
                            path = ROOT / path
                        pstat = path.stat()
                        key += (str(path), pstat.st_size, pstat.st_mtime_ns)
                        if key not in validated:
                            validate_prompt(path, reference)
                            validated.add(key)
                        embeddings[key] = path
                    elif key not in embeddings:
                        digest = hashlib.sha256(repr(key).encode()).hexdigest()[:20]
                        path = BASE / ('speaker_' + digest + '.json')
                        if not valid_embedding(path) and not extract(ctx, str(reference).encode(), str(path).encode()):
                            raise RuntimeError(last_error(ctx))
                        embeddings[key] = path
                    if request['action'] == 'synthesize' or key not in warmed:
                        params = Params(512, .9, 1.0, 50, CPU_THREADS, 0, 0, 1.05, 2071, None, None, 0)
                        text = request['text'] if request['action'] == 'synthesize' else 'Olá.'
                        cache_key = (key, text)
                        cached = cache.get(cache_key)
                        if cached is None:
                            generate = synthesize_icl if prompt else synthesize
                            result = generate(ctx, text.encode('utf-8'), str(embeddings[key]).encode(), params)
                            try:
                                if not result.success:
                                    raise RuntimeError(result.error_msg.decode('utf-8', errors='replace') if result.error_msg else last_error(ctx))
                                audio = np.ctypeslib.as_array(result.audio, shape=(result.audio_len,)).copy()
                                rate = result.sample_rate
                                if not audio.size or not np.isfinite(audio).all() or np.max(np.abs(audio)) < .0001:
                                    raise RuntimeError('Áudio vazio ou inválido')
                                cache.put(cache_key, audio, rate)
                            finally:
                                free_result(result)
                        else:
                            audio, rate = cached
                        if request['action'] == 'synthesize':
                            sf.write(request['output'], audio, rate, subtype='PCM_16')
                        warmed.add(key)
                    else:
                        cached = None
                    response = {'ok': True, 'generation_ms': round((time.perf_counter()-started)*1000, 1),
                                'gpu_priority': gpu_priority,
                                'compute_backend': (backend() or b'unknown').decode(), 'cpu_threads': CPU_THREADS,
                                'cache_hit': cached is not None, 'reference_mode': 'icl' if prompt else 'speaker'}
                except Exception as exc:
                    response = {'ok': False, 'error': str(exc)}
                protocol.write(json.dumps(response, ensure_ascii=False) + '\n')
                protocol.flush()
        finally:
            free(ctx)


if __name__ == '__main__':
    main()
