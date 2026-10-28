
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
"""Compare warm first-audio generation locally, without playing or selecting voices."""
import json
import threading
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from voice.engine import VoiceEngine
from voice.qwen_backend import QwenBackend
from voice.qwen_audio import shorten_phrase_silence


def main():
    root = _ROOT
    config = json.loads((root/'config/default.json').read_text(encoding='utf-8'))['voice']
    reference = root/config['tts_qwen_reference']
    text = ('Primeiro, vou separar os compromissos importantes, conferir as tarefas '
            'que ficaram pendentes e apresentar um resumo claro, sem repetir informações desnecessárias.')
    engine = VoiceEngine(config)
    backend = QwenBackend(config)
    out = root/'logs'/('qwen_inicio_'+time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir(parents=True)
    report = {'text': text, 'method': 'warm generation to first playable phrase; no speaker device or brain latency', 'cases': []}
    print(str(out), flush=True)
    try:
        start = time.perf_counter()
        backend.prepare(reference)
        report['prepare_seconds'] = round(time.perf_counter()-start, 3)
        print('Prepared:', report['prepare_seconds'], flush=True)
        for label, chunks in [('antes', engine._split_xtts_response(text)), ('inicio_rapido', engine._split_qwen_response(text))]:
            arrays = []
            entry = {'id': label, 'chunks': []}
            for chunk in chunks:
                start = time.perf_counter()
                path = backend.synthesize(chunk, reference, threading.Event())
                try:
                    audio, rate = sf.read(path, dtype='float32')
                finally:
                    Path(path).unlink(missing_ok=True)
                audio = shorten_phrase_silence(audio, rate)
                elapsed = time.perf_counter()-start
                arrays.append(audio)
                entry['chunks'].append({'text': chunk, 'generation_seconds': round(elapsed,3), 'audio_seconds': len(audio)/rate, 'cache_hit': backend.last_metrics.get('cache_hit')})
                print(label, entry['chunks'][-1], flush=True)
            entry['first_audio_seconds'] = entry['chunks'][0]['generation_seconds']
            # Estimate underrun with this serial producer and reserve=1.
            ready = 0.; end = 0.; gap = 0.
            for i, chunk in enumerate(entry['chunks']):
                ready += chunk['generation_seconds']
                if i: gap += max(0., ready-end)
                end = max(ready, end)+chunk['audio_seconds']
            entry['estimated_generation_gap_seconds'] = round(gap,3)
            sf.write(out/f'{label}.wav', np.concatenate(arrays), rate, subtype='PCM_16')
            report['cases'].append(entry)
    finally:
        backend.close()
    (out/'resultado.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
