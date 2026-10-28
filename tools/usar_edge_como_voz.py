
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import json
from pathlib import Path
p=_ROOT/'config'/'default.json'
cfg=json.loads(p.read_text(encoding='utf-8'))
cfg.setdefault('voice',{})['tts_profile']='edge_tts_728'
p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
print('OK: Edge-TTS 7.2.8 definido como voz principal do V.')
