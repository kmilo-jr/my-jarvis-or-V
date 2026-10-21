"""Measure real synthesis, then simulate playback buffering without opening speakers."""
import json, time, threading, wave, shutil
from pathlib import Path
from datetime import datetime
from voice.qwen_backend import QwenBackend
from voice.engine import VoiceEngine

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/briefing_voice_benchmark'
TEXT=('Bom dia. Vamos conferir o seu resumo. Sua agenda de exemplo tem uma reunião às dez horas e um período de estudos à tarde. '
      'Na caixa de entrada de demonstração, há duas mensagens para revisar depois do café. '
      'Estas são informações fictícias usadas apenas para medir a velocidade da voz do V.')

def simulate(rows,reserve):
    ready=[]; total=0
    for row in rows:
        total+=row['seconds']; ready.append(total)
    start=ready[min(reserve,len(rows))-1]; end=start; gaps=0
    for row,when in zip(rows,ready):
        gaps+=max(0,when-end); end=max(end,when)+row['audio_seconds']
    return {'first_playback_seconds_estimated':round(start,2),'later_gaps_seconds_estimated':round(gaps,2),'finish_seconds_estimated':round(end,2)}

def main():
    OUT.mkdir(exist_ok=True)
    cfg=json.loads((ROOT/'config/default.json').read_text(encoding='utf-8'))['voice']
    cfg=dict(cfg,tts_qwen_device='cpu',tts_qwen_idle_seconds=0)
    backend=QwenBackend(cfg); cancel=threading.Event()
    engine=VoiceEngine(cfg)
    reference=engine._resolve_qwen_reference()
    report={'timestamp':datetime.now().astimezone().isoformat(),'device':'cpu','threads':cfg.get('tts_qwen_cpu_threads'),'text':TEXT,'rows':[]}
    def save(): (OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    try:
        start=time.perf_counter(); backend.prepare(reference)
        report['cold_prepare_seconds']=round(time.perf_counter()-start,2)
        print('PREPARE',report['cold_prepare_seconds'],flush=True); save()
        chunks=engine._split_qwen_response(TEXT)
        for i,text in enumerate(chunks):
            start=time.perf_counter(); path=backend.synthesize(text,reference,cancel)
            elapsed=time.perf_counter()-start
            with wave.open(path,'rb') as audio: seconds=audio.getnframes()/audio.getframerate()
            dest=OUT/f'chunk-{i+1}.wav'; shutil.copyfile(path,dest); Path(path).unlink()
            row={'text':text,'seconds':round(elapsed,2),'audio_seconds':round(seconds,2),'rtf':round(elapsed/seconds,2),'metrics':backend.last_metrics}
            report['rows'].append(row); save(); print('CHUNK',i+1,json.dumps(row,ensure_ascii=True),flush=True)
        report['buffer_1']=simulate(report['rows'],1); report['buffer_2']=simulate(report['rows'],2)
        start=time.perf_counter(); path=backend.synthesize(chunks[0],reference,cancel)
        report['cached_first_chunk_seconds']=round(time.perf_counter()-start,3)
        Path(path).unlink(missing_ok=True)
        save(); print('DONE',json.dumps({k:v for k,v in report.items() if k not in ('rows','text')},ensure_ascii=True),flush=True)
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'; save(); raise
    finally:
        backend.close()

if __name__=='__main__': main()
