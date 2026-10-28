from pathlib import Path
import json, shutil

HERE=Path(__file__).resolve().parent
CANDIDATES=[
    HERE.parent/'V_PROTOTYPE_1_4_INSTANT_PIPELINE',
]
old=next((p for p in CANDIDATES if p.exists()),None)
if old is None:
    print('Nao encontrei a pasta V_PROTOTYPE_1_4_INSTANT_PIPELINE ao lado desta pasta.')
    raise SystemExit(1)

# Config: preserva preferências/credenciais, mas mantém os ajustes novos de streaming.
new_cfg_path=HERE/'config'/'default.json'
new_cfg=json.loads(new_cfg_path.read_text(encoding='utf-8'))
old_cfg_path=old/'config'/'default.json'
if old_cfg_path.exists():
    old_cfg=json.loads(old_cfg_path.read_text(encoding='utf-8'))
    merged=dict(old_cfg)
    merged['version']='PROTOTYPE 1.4.1 STREAM + ROUTING HOTFIX'
    nb=dict(old_cfg.get('brain',{}))
    nb.update({
        'stream_chat': True,
        'gemini_stream_max_output_tokens': 520,
        'gemini_stream_repair_tokens': 560,
        'gemini_stream_first_sentence_only': True,
    })
    merged['brain']=nb
    # Mantém novos defaults caso alguma seção não existisse na antiga.
    for key,val in new_cfg.items():
        merged.setdefault(key,val)
    new_cfg_path.write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')

for name in ('gemini_key.dat','elevenlabs_key.dat','spotify_token.json'):
    src=old/'config'/name; dst=HERE/'config'/name
    if src.exists():
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
for name in ('memory.json','conversation_history.json'):
    src=old/'data'/name; dst=HERE/'data'/name
    if src.exists():
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
print('Migracao 1.4 -> 1.4.1 concluida.')
