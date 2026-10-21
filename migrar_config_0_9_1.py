from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parent
candidates=[ROOT.parent/'V_PROTOTYPE_0_9_1_SPOTIFY_SMTC_NEXT', ROOT.parent/'V_PROTOTYPE_0_9_TOOL_SYSTEM_ALPHA']
src=next((p for p in candidates if p.exists()),None)
if not src:
    print('Nao encontrei a pasta 0.9.1 ao lado desta pasta. Nada foi alterado.')
    raise SystemExit(1)
old_cfg=src/'config'/'default.json'; new_cfg=ROOT/'config'/'default.json'
new=json.loads(new_cfg.read_text(encoding='utf-8'))
if old_cfg.exists():
    old=json.loads(old_cfg.read_text(encoding='utf-8'))
    if old.get('spotify_api',{}).get('client_id'): new['spotify_api']['client_id']=old['spotify_api']['client_id']
    for section in ('voice',):
        if isinstance(old.get(section),dict): new[section].update(old[section])
new['assistant']['version']='PROTOTYPE 1.0 BRAIN CORE ALPHA'
new_cfg.write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
for rel in [Path('config/spotify_token.json'), Path('data/memory.json'), Path('data/conversation_history.json')]:
    a=src/rel; b=ROOT/rel
    if a.exists():
        b.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(a,b)
print('Configuracoes locais migradas para o V 1.0 Brain Core Alpha.')
