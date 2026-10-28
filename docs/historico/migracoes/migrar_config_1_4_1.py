from pathlib import Path
import json, shutil, re, os
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'V_PROTOTYPE_1_4_1_STREAM_ROUTING_HOTFIX'
if not OLD.exists():
    print('Nao encontrei V_PROTOTYPE_1_4_1_STREAM_ROUTING_HOTFIX ao lado desta pasta.')
    raise SystemExit(1)
newp=HERE/'config'/'default.json'
newcfg=json.loads(newp.read_text(encoding='utf-8'))
oldp=OLD/'config'/'default.json'
if oldp.exists():
    oldcfg=json.loads(oldp.read_text(encoding='utf-8'))
    for sec in ('brain','voice','spotify_api','memory','personality','ui'):
        if sec in oldcfg and isinstance(oldcfg[sec],dict):
            base=dict(newcfg.get(sec,{ })); base.update(oldcfg[sec]); newcfg[sec]=base
newcfg.setdefault('assistant',{})['version']='PROTOTYPE 1.5 SPOTIFY BRIDGE'
newcfg.setdefault('app',{})['version']='PROTOTYPE 1.5 SPOTIFY BRIDGE'
newp.write_text(json.dumps(newcfg,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('gemini_key.dat','elevenlabs_key.dat','spotify_token.json'):
    src=OLD/'config'/name; dst=HERE/'config'/name
    if src.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
for name in ('memory.json','conversation_history.json'):
    src=OLD/'data'/name; dst=HERE/'data'/name
    if src.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
# Reutiliza o token da extensão Spicetify já instalada pelo protótipo, se houver.
try:
    ext=Path(os.environ['APPDATA'])/'spicetify'/'Extensions'/'vSpotifyBridge.js'
    if ext.exists():
        m=re.search(r'const\s+TOKEN\s*=\s*["\']([^"\']+)["\']',ext.read_text(encoding='utf-8',errors='ignore'))
        if m: (HERE/'config'/'spotify_bridge_token.txt').write_text(m.group(1),encoding='utf-8')
except Exception: pass
print('Migracao 1.4.1 -> 1.5 concluida.')
print('Agora rode configurar_spotify_bridge.bat uma vez para atualizar a extensao.')
