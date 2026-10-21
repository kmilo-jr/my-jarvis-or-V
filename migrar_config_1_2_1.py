from __future__ import annotations
import json, shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent
OLD=BASE.parent/'V_PROTOTYPE_1_2_1_GENTLEMAN_STARTUP'
if not OLD.exists():
    print('Pasta V_PROTOTYPE_1_2_1_GENTLEMAN_STARTUP nao encontrada ao lado desta pasta.')
    raise SystemExit(1)
oldp=OLD/'config/default.json'; newp=BASE/'config/default.json'
old=json.loads(oldp.read_text(encoding='utf-8')) if oldp.exists() else {}
new=json.loads(newp.read_text(encoding='utf-8'))
for section in ('spotify_api','memory','ui','brain','personality'):
    if section in old:
        if isinstance(new.get(section),dict) and isinstance(old[section],dict):
            # Personality da 1.3 é igual à 1.2.1, então pode ser preservada.
            new[section].update(old[section])
        else: new[section]=old[section]
# Preserva reconhecimento/microfone e fallbacks, mas NÃO substitui o perfil Eleven novo.
if 'voice' in old:
    blocked={'tts_profile','tts_eleven_voice_id','tts_eleven_key_file','tts_eleven_model','tts_eleven_output_format','tts_eleven_language_code','tts_eleven_timeout','tts_eleven_stability','tts_eleven_similarity_boost','tts_eleven_style','tts_eleven_speed','tts_eleven_use_speaker_boost','tts_eleven_fallback_edge'}
    for k,val in old['voice'].items():
        if k not in blocked:
            new['voice'][k]=val
newp.write_text(json.dumps(new,ensure_ascii=False,indent=2),encoding='utf-8')
for rel in ('config/gemini_key.dat','config/spotify_token.json','data/memory.json','data/conversation_history.json'):
    src=OLD/rel; dst=BASE/rel
    if src.exists():
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
print('Migracao 1.2.1 -> 1.3 concluida. Gemini, Spotify, memoria e microfone preservados.')
