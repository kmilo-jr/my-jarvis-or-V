from pathlib import Path
import json, shutil, re, os

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'V_PROTOTYPE_1_5_SPOTIFY_BRIDGE'
if not OLD.exists():
    print('Nao encontrei V_PROTOTYPE_1_5_SPOTIFY_BRIDGE ao lado desta pasta.')
    raise SystemExit(1)

newp=HERE/'config'/'default.json'
newcfg=json.loads(newp.read_text(encoding='utf-8'))
oldp=OLD/'config'/'default.json'
if oldp.exists():
    oldcfg=json.loads(oldp.read_text(encoding='utf-8'))
    for sec in ('brain','voice','spotify_api','memory','personality','ui','spotify_bridge'):
        if sec in oldcfg and isinstance(oldcfg[sec],dict):
            # Valores novos continuam existindo; preferências antigas substituem
            # apenas chaves que já existiam no build anterior.
            base=dict(newcfg.get(sec,{}))
            base.update(oldcfg[sec])
            newcfg[sec]=base

newcfg.setdefault('assistant',{})['version']='PROTOTYPE 1.6 NEURAL INTERFACE'
newcfg.setdefault('app',{})['version']='PROTOTYPE 1.6 NEURAL INTERFACE'
ui=newcfg.setdefault('ui',{})
ui.setdefault('processing_sound_enabled', True)
ui.setdefault('processing_sound_delay_ms', 260)
ui.setdefault('processing_sound_volume', 0.16)
ui.setdefault('processing_sound_file', 'assets/sounds/v_processing.wav')
ui.setdefault('processing_sound_loop', True)
newp.write_text(json.dumps(newcfg,ensure_ascii=False,indent=2),encoding='utf-8')

for name in ('gemini_key.dat','elevenlabs_key.dat','spotify_token.json','spotify_bridge_token.txt'):
    src=OLD/'config'/name; dst=HERE/'config'/name
    if src.exists():
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
for name in ('memory.json','conversation_history.json'):
    src=OLD/'data'/name; dst=HERE/'data'/name
    if src.exists():
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)

# Se a extensão Spicetify já estiver instalada, preserva o token dela.
try:
    ext=Path(os.environ['APPDATA'])/'spicetify'/'Extensions'/'vSpotifyBridge.js'
    if ext.exists():
        m=re.search(r'const\s+TOKEN\s*=\s*["\']([^"\']+)["\']',ext.read_text(encoding='utf-8',errors='ignore'))
        if m:
            (HERE/'config'/'spotify_bridge_token.txt').write_text(m.group(1),encoding='utf-8')
except Exception:
    pass

print('Migracao 1.5 -> 1.6 concluida.')
print('Gemini, ElevenLabs, memoria e Spotify Bridge foram preservados.')
