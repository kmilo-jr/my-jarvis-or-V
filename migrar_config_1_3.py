from pathlib import Path
import json, shutil
HERE=Path(__file__).resolve().parent
candidates=[HERE.parent/'V_PROTOTYPE_1_3_CUSTOM_VOICE']
for old in candidates:
    if not old.exists(): continue
    for rel in ['config/gemini_key.dat','config/elevenlabs_key.dat','config/spotify_token.json','data/memory.json','data/conversation_history.json']:
        src=old/rel; dst=HERE/rel
        if src.exists(): dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    try:
        oldcfg=json.loads((old/'config/default.json').read_text(encoding='utf-8'))
        newp=HERE/'config/default.json'; newcfg=json.loads(newp.read_text(encoding='utf-8'))
        for section in ('spotify_api',):
            if section in oldcfg: newcfg[section].update(oldcfg[section])
        # preserve device/ASR calibration-friendly settings without reverting latency tuning
        for key in ('language','initial_prompt','term_replacements','wake_words','tts_eleven_voice_id'):
            if key in oldcfg.get('voice',{}): newcfg['voice'][key]=oldcfg['voice'][key]
        newp.write_text(json.dumps(newcfg,ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception: pass
    print('Migração concluída de', old.name); break
else:
    print('Pasta V 1.3 não encontrada ao lado desta versão.')
