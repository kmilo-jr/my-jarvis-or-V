from __future__ import annotations
import json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
PARENT=HERE.parent
candidates=[
    PARENT/'V_PROTOTYPE_0_9_TOOL_SYSTEM_ALPHA',
]
src=next((p for p in candidates if p.exists()),None)
if not src:
    print('Nao encontrei a pasta V_PROTOTYPE_0_9_TOOL_SYSTEM_ALPHA ao lado desta.')
    print('Voce pode configurar IA e Spotify normalmente.')
    raise SystemExit(1)
newp=HERE/'config'/'default.json'; oldp=src/'config'/'default.json'
new=json.loads(newp.read_text(encoding='utf-8'))
old=json.loads(oldp.read_text(encoding='utf-8'))
for section in ('spotify_api','brain','voice'):
    if section in old:
        base=dict(new.get(section) or {})
        base.update(old.get(section) or {})
        new[section]=base
new.setdefault('assistant',{})['version']='PROTOTYPE 0.9.1'
newp.write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('spotify_token.json',):
    f=src/'config'/name
    if f.exists(): shutil.copy2(f,HERE/'config'/name)
print('Configuracao da 0.9 migrada para a 0.9.1.')
print('Agora rode configurar_prototype.bat para instalar o controle SMTC do Windows.')
