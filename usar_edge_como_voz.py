import json
from pathlib import Path
p=Path(__file__).resolve().parent/'config'/'default.json'
cfg=json.loads(p.read_text(encoding='utf-8'))
cfg.setdefault('voice',{})['tts_profile']='edge_tts_728'
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
print('OK: Edge-TTS 7.2.8 definido como voz principal do V.')
