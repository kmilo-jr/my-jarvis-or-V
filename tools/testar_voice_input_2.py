from __future__ import annotations
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import difflib
import argparse
import json
import re
import time
from pathlib import Path
from voice.engine import VoiceEngine
from voice.recognition_eval import word_errors

BASE=_ROOT
PHRASES=[
    'V, abra o YouTube.',
    'V, toque uma música no Spotify.',
    'V, quais são as notícias do dia?',
    'V, abra o Firefox.',
    'V, quanto está a PETR4?',
    'V, bom dia.',
    'V, leia apenas o assunto dos meus e-mails.',
    'V, não desligue o computador.',
    'V, abaixe o volume para quinze por cento.',
    'V, me lembre de conferir as mensagens amanhã de manhã.',
]

def norm(s):
    return re.sub(r'[^a-z0-9áàâãéêíóôõúç ]+',' ',str(s).lower()).strip()

def main():
    parser = argparse.ArgumentParser(description='Teste de reconhecimento sem executar comandos; salva texto e métricas, sem gravar arquivos de áudio.')
    parser.add_argument('--device', type=int, help='Índice do microfone')
    parser.add_argument('--list-devices', action='store_true')
    parser.add_argument('--backend', choices=['auto', 'cpu', 'cuda'])
    args = parser.parse_args()
    cfg=json.loads((BASE/'config'/'default.json').read_text(encoding='utf-8'))['voice']
    if args.backend:
        cfg.update(device=args.backend, compute_type='auto')
    eng=VoiceEngine(cfg)
    devices = eng.input_devices()
    if args.list_devices:
        for device in devices: print(device)
        return
    selected = args.device
    if selected is None:
        preferred = str(cfg.get('preferred_input_device_name', '')).casefold()
        selected = next((index for index, name, _ in devices if preferred and name.split(' · ')[0].casefold() == preferred), None)
    print('Microfone:', eng.validate_input_device(selected))
    print('=== V VOICE INPUT 2.0 // TESTE REAL DE MICROFONE ===')
    print('Use o mesmo microfone que você usa com o V. Fique em silêncio durante a calibração inicial.\n')
    rows=[]
    eng.preload_model(stage_callback=lambda s: print('[',s,']'))
    eng.calibrate_ambient(selected, stage_callback=lambda s: print('[',s,']'))
    for i,expected in enumerate(PHRASES,1):
        input(f'\n{i}/{len(PHRASES)}  Fale: "{expected}"\nPressione ENTER e fale normalmente...')
        t0=time.perf_counter()
        heard,meta=eng.listen_and_transcribe(selected,stage_callback=lambda s: print('[',s,']'))
        total=(time.perf_counter()-t0)*1000
        score=difflib.SequenceMatcher(None,norm(expected),norm(heard)).ratio()*100
        errors = word_errors(expected, heard)
        print('Entendi:',heard or '(nada)')
        print(f"Erro por palavras (WER): {errors['wer_percent']}% (menor é melhor)")
        print(f'Similaridade: {score:.1f}% | fim: {meta.get("phrase_end_silence_ms","-")} ms | Whisper: {meta.get("transcription_ms","-")} ms | total: {total:.0f} ms')
        rows.append({'expected':expected,'heard':heard,'similarity':round(score,1),'total_ms':round(total,1),'meta':meta, **errors})
    avg=sum(x['similarity'] for x in rows)/len(rows)
    out=BASE/'logs'/'voice_input_2_benchmark.json'; out.parent.mkdir(exist_ok=True)
    total_wer = round(100 * sum(r['errors'] for r in rows) / max(1, sum(r['reference_words'] for r in rows)), 2)
    out.write_text(json.dumps({'average_similarity':round(avg,1),'wer_percent':total_wer,'tests':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'\nMédia: {avg:.1f}%')
    print('Relatório:',out)
    eng.shutdown()

if __name__=='__main__':
    main()
