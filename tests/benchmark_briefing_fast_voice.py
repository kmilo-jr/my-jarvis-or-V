"""Prepare fixed greetings and benchmark the installed Piper voice, CPU only."""
import json, time, wave, threading
from pathlib import Path
from voice.engine import VoiceEngine
from voice.qwen_backend import QwenBackend
from voice.briefing_cache import GREETINGS, cache_path, store_audio, valid_audio
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'logs/briefing_fast_voice'; OUT.mkdir(exist_ok=True)
cfg=json.loads((ROOT/'config/default.json').read_text(encoding='utf-8'))['voice']
config=dict(cfg,tts_qwen_device='cpu',tts_qwen_idle_seconds=0)
backend=QwenBackend(config); engine=VoiceEngine(config)
report={'greetings':[]}
try:
    for text in GREETINGS:
        dest=cache_path(text,engine._resolve_qwen_reference(),config)
        start=time.perf_counter()
        if not valid_audio(dest):
            source=backend.synthesize(text,engine._resolve_qwen_reference(),threading.Event())
            try: store_audio(source,dest)
            finally: Path(source).unlink(missing_ok=True)
        report['greetings'].append({'text':text,'seconds':round(time.perf_counter()-start,3),'path':str(dest)})
        print('GREETING',report['greetings'][-1],flush=True)
finally: backend.close()
from piper import PiperVoice, SynthesisConfig
start=time.perf_counter()
voice=PiperVoice.load(str(engine._resolve_piper_model()),use_cuda=False)
report['piper_load_seconds']=round(time.perf_counter()-start,3)
text='Sua agenda de exemplo tem uma reunião às dez horas e um período de estudos à tarde.'
path=OUT/'piper_agenda.wav'
start=time.perf_counter()
with wave.open(str(path),'wb') as wav:
    voice.synthesize_wav(text,wav,syn_config=SynthesisConfig(length_scale=1.0))
report['piper_generation_seconds']=round(time.perf_counter()-start,3)
with wave.open(str(path),'rb') as wav: report['piper_audio_seconds']=round(wav.getnframes()/wav.getframerate(),3)
report['piper_rtf']=round(report['piper_generation_seconds']/report['piper_audio_seconds'],3)
(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True),flush=True)
