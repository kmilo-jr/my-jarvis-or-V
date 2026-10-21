from pathlib import Path
import json, shutil
BASE=Path(__file__).resolve().parent
candidates=[
    'V_PROTOTYPE_1_0_3_EDGE_TTS_728',
    'V_PROTOTYPE_1_0_2_FISH_DIAGNOSTIC',
    'V_PROTOTYPE_1_0_1_FISH_KEY_GUI_HOTFIX',
    'V_PROTOTYPE_1_0_1_FISH_JARVIS_VOICE',
    'V_PROTOTYPE_1_0_BRAIN_CORE_ALPHA',
]
old=None
for name in candidates:
    p=BASE.parent/name/'config'/'default.json'
    if p.exists(): old=p; break
if not old:
    print('Nenhuma instalacao anterior encontrada ao lado desta pasta.')
    raise SystemExit(1)
newp=BASE/'config'/'default.json'
oldcfg=json.loads(old.read_text(encoding='utf-8'))
newcfg=json.loads(newp.read_text(encoding='utf-8'))
for section in ('brain','spotify_api','memory','personality'):
    if isinstance(oldcfg.get(section),dict):
        newcfg[section].update(oldcfg[section])
# Preserva reconhecimento de voz e preferencia Edge, mas mantém Piper como principal.
ov=oldcfg.get('voice',{})
nv=newcfg.get('voice',{})
for k,v in ov.items():
    if k.startswith('tts_edge_') or k in {'model','device','compute_type','language','record_seconds','beam_size','initial_prompt','continuous_voice_default','wake_words','cpu_threads'}:
        nv[k]=v
nv['tts_profile']='piper_faber'
nv['tts_piper_voice']='pt_BR-faber-medium'
nv['tts_piper_model']='models/piper/pt_BR-faber-medium.onnx'
newcfg['voice']=nv
newp.write_text(json.dumps(newcfg,ensure_ascii=False,indent=2),encoding='utf-8')
# tokens seguros
for fname in ('spotify_token.json',):
    src=old.parent/fname; dst=newp.parent/fname
    if src.exists() and not dst.exists(): shutil.copy2(src,dst)
# memoria/historico
for fname in ('memory.json','conversation_history.json'):
    src=old.parent.parent/'data'/fname; dst=BASE/'data'/fname
    if src.exists():
        dst.parent.mkdir(exist_ok=True); shutil.copy2(src,dst)
print('Migracao concluida de:', old.parent.parent.name)
print('Piper/Faber foi mantido como voz principal; Edge continua como fallback.')
