import json
from pathlib import Path
p=Path(__file__).resolve().parent/'config'/'default.json'
cfg=json.loads(p.read_text(encoding='utf-8'))
v=cfg.setdefault('voice',{})
v['tts_profile']='piper_faber'
v['tts_piper_voice']='pt_BR-faber-medium'
v['tts_piper_model']='models/piper/pt_BR-faber-medium.onnx'
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
print('OK: Piper/Faber definido como voz principal do V.')
