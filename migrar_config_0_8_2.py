from __future__ import annotations
import json, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
CANDIDATES = [
    PARENT / 'V_PROTOTYPE_0_8_2_VERIFIED_CONVERSATION',
    PARENT / 'V_PROTOTYPE_0_8_1_CONVERSATION_FIX',
    PARENT / 'V_PROTOTYPE_0_8_AI_BRAIN_ALPHA',
]
source = next((p for p in CANDIDATES if p.exists()), None)
if not source:
    print('Nao encontrei uma pasta 0.8.2/0.8.1/0.8 ao lado desta pasta.')
    print('Se voce renomeou a pasta antiga, configure IA e Spotify normalmente.')
    raise SystemExit(1)

new_cfg_path = HERE / 'config' / 'default.json'
old_cfg_path = source / 'config' / 'default.json'
try:
    new_cfg = json.loads(new_cfg_path.read_text(encoding='utf-8'))
    old_cfg = json.loads(old_cfg_path.read_text(encoding='utf-8'))
    for key in ('spotify_api', 'brain'):
        if isinstance(old_cfg.get(key), dict):
            new_cfg[key] = old_cfg[key]
    new_cfg_path.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=2), encoding='utf-8')
except Exception as exc:
    print('Nao consegui migrar default.json:', exc)

old_token = source / 'config' / 'spotify_token.json'
new_token = HERE / 'config' / 'spotify_token.json'
if old_token.exists():
    new_token.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old_token, new_token)
    print('Token Spotify migrado.')
else:
    print('A pasta antiga nao tinha spotify_token.json.')

print('Configuracoes migradas de:', source.name)
print('Pronto. Agora abra iniciar_v_prototype.bat.')
