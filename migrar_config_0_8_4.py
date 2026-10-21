from __future__ import annotations
import json, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
CANDIDATES = [
    PARENT / 'V_PROTOTYPE_0_8_4_INTENT_FIREWALL',
    PARENT / 'V_PROTOTYPE_0_8_3_SPOTIFY_HYBRID_NEXT',
    PARENT / 'V_PROTOTYPE_0_8_2_VERIFIED_CONVERSATION',
]
source = next((p for p in CANDIDATES if p.exists()), None)
if not source:
    print('Nao encontrei V 0.8.4/0.8.3/0.8.2 ao lado desta pasta.')
    print('Voce pode configurar IA e Spotify normalmente.')
    raise SystemExit(1)

new_cfg_path = HERE / 'config' / 'default.json'
old_cfg_path = source / 'config' / 'default.json'
try:
    new_cfg = json.loads(new_cfg_path.read_text(encoding='utf-8'))
    old_cfg = json.loads(old_cfg_path.read_text(encoding='utf-8'))
    # Migra segredos/preferencias, mas preserva campos novos do 0.9.
    for section in ('spotify_api', 'voice'):
        if isinstance(old_cfg.get(section), dict):
            merged = dict(new_cfg.get(section) or {})
            merged.update(old_cfg[section])
            new_cfg[section] = merged
    if isinstance(old_cfg.get('brain'), dict):
        merged = dict(new_cfg.get('brain') or {})
        merged.update(old_cfg['brain'])
        merged['temperature'] = min(float(merged.get('temperature', 0.12)), 0.12)
        new_cfg['brain'] = merged
    new_cfg.setdefault('assistant', {})['version'] = 'PROTOTYPE 0.9'
    new_cfg_path.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=2), encoding='utf-8')
except Exception as exc:
    print('Nao consegui migrar default.json:', exc)

for name in ('spotify_token.json',):
    old = source / 'config' / name
    new = HERE / 'config' / name
    if old.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old, new)
        print(name, 'migrado.')

print('Configuracoes migradas de:', source.name)
print('Pronto. Abra iniciar_v_prototype.bat.')
