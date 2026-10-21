from __future__ import annotations
import json, shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
candidates=[
    HERE.parent/'V_PROTOTYPE_1_0_4_PIPER_FABER_OFFLINE',
    HERE.parent/'V_PROTOTYPE_1_0_3_EDGE_TTS_728',
]
old=next((p for p in candidates if p.exists()),None)
if old is None:
    print('Pasta anterior não encontrada ao lado desta. Nada foi alterado.')
    raise SystemExit(1)

new_cfg_path=HERE/'config/default.json'
old_cfg_path=old/'config/default.json'
new=json.loads(new_cfg_path.read_text(encoding='utf-8'))
if old_cfg_path.exists():
    oldcfg=json.loads(old_cfg_path.read_text(encoding='utf-8'))
    # Preserve personal/runtime settings while keeping the new Gemini brain defaults.
    for section in ('voice','spotify_api','memory','personality','ui'):
        if isinstance(oldcfg.get(section),dict):
            new.setdefault(section,{}).update(oldcfg[section])
    # Preserve Ollama settings only as fallback.
    for key in ('model','timeout','ollama_url','temperature','max_history','planner_enabled','keep_alive','naturalize_tool_results'):
        if key in oldcfg.get('brain',{}): new['brain'][key]=oldcfg['brain'][key]
    new_cfg_path.write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')

for rel in ('config/spotify_token.json','data/memory.json','data/conversation_history.json'):
    src=old/rel; dst=HERE/rel
    if src.exists():
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        print('Copiado:',rel)

# Piper model can be large; copy only if already installed so user avoids downloading again.
old_models=old/'models/piper'
new_models=HERE/'models/piper'
if old_models.exists():
    new_models.mkdir(parents=True,exist_ok=True)
    for name in ('pt_BR-faber-medium.onnx','pt_BR-faber-medium.onnx.json'):
        src=old_models/name
        if src.exists():
            shutil.copy2(src,new_models/name)
            print('Copiado:',f'models/piper/{name}')
print('Migração 1.0.4 -> 1.1 concluída.')
