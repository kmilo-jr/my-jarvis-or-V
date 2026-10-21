from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from p2p_host import ensure_p2p_identity

BASE=Path(__file__).resolve().parent
CFG=BASE/'config'/'default.json'

def normalize(value: str) -> str:
    v=value.strip().rstrip('/')
    if not v:
        return ''
    if v.startswith('https://'):
        v='wss://'+v[len('https://'):]
    elif v.startswith('http://'):
        v='ws://'+v[len('http://'):]
    if not v.startswith(('ws://','wss://')):
        v='wss://'+v
    p=urlparse(v)
    path=p.path or ''
    if path in {'','/'}:
        path='/ws'
    return urlunparse((p.scheme,p.netloc,path,'','',''))

print('=== CONFIGURAR V P2P ===')
print('Cole a URL publica do servidor de sinalizacao.')
print('Exemplo: https://v-p2p-signal.onrender.com')
raw=input('URL: ').strip()
url=normalize(raw)
if not url:
    print('Nenhuma URL informada. Nada foi alterado.')
    raise SystemExit(1)
cfg=json.loads(CFG.read_text(encoding='utf-8'))
p2p=cfg.setdefault('remote',{}).setdefault('p2p',{})
p2p['enabled']=True
p2p['signaling_url']=url
CFG.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
p2p=ensure_p2p_identity(CFG)
print('\nConfigurado com sucesso:')
print('Signaling:',url)
print('Room:',p2p.get('room_id'))
print('Agora inicie o V pelo INICIAR_V_P2P.bat.')
