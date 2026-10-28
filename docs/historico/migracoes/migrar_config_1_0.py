from pathlib import Path
import json, shutil

BASE=Path(__file__).resolve().parent
PARENT=BASE.parent
candidates=[
    'V_PROTOTYPE_1_0_2_FISH_DIAGNOSTIC',
    'V_PROTOTYPE_1_0_1_FISH_KEY_GUI_HOTFIX',
    'V_PROTOTYPE_1_0_1_FISH_JARVIS_VOICE',
    'V_PROTOTYPE_1_0_BRAIN_CORE_ALPHA',
]
src=None
for name in candidates:
    p=PARENT/name
    if p.exists():
        src=p; break
if not src:
    print('Nenhuma versao 1.0 anterior encontrada ao lado desta pasta.')
    raise SystemExit(1)

newp=BASE/'config'/'default.json'
oldp=src/'config'/'default.json'
new=json.loads(newp.read_text(encoding='utf-8'))
old=json.loads(oldp.read_text(encoding='utf-8'))
# preserva configuracoes funcionais, mas NAO importa Fish Audio.
for section in ('brain','spotify_api','memory','personality'):
    if section in old:
        new[section]=old[section]
oldv=old.get('voice',{})
newv=new.setdefault('voice',{})
for key in ('model','device','compute_type','language','initial_prompt','continuous_voice_default','wake_words','post_tts_cooldown','cpu_threads'):
    if key in oldv:
        newv[key]=oldv[key]
# Edge-TTS volta a ser o unico TTS online principal.
for key,default in (
    ('tts_edge_voice','pt-BR-AntonioNeural'),
    ('tts_edge_rate','+15%'),
    ('tts_edge_pitch','-32Hz'),
    ('tts_edge_volume','+0%'),
):
    newv[key]=oldv.get(key,newv.get(key,default))
newv['tts_profile']='edge_tts_728'
newv['tts_playback']='win32_mci'
new['assistant']['version']='PROTOTYPE 1.0.3 EDGE-TTS 7.2.8'
newp.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# preserva memoria/historico locais se existirem.
for rel in ('data/memory.json','data/conversation_history.json','config/spotify_token.json'):
    a=src/rel; b=BASE/rel
    if a.exists():
        b.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(a,b)
print('Migracao concluida de:',src.name)
print('Fish Audio nao foi importado.')
print('Edge-TTS 7.2.8 restaurado como voz principal.')
