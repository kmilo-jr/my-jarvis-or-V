from __future__ import annotations
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import json, os, sys, tempfile
from pathlib import Path
import requests

BASE=_ROOT
sys.path.insert(0,str(BASE))
from voice.eleven_auth import load_key
from voice.engine import VoiceEngine

cfg=json.loads((BASE/'config/default.json').read_text(encoding='utf-8'))
v=cfg['voice']
key=load_key(v)
voice_id=str(v.get('tts_eleven_voice_id',''))
print('=== V 1.3 — TESTE DA VOZ PERSONALIZADA ===')
print('Voice ID:',voice_id)
print('API Key configurada:', 'SIM' if key else 'NAO')
print('Modelo:',v.get('tts_eleven_model'))
if not key:
    print('\nFALHOU: rode configurar_voz_v.bat primeiro.')
    input('\nPressione Enter para sair...')
    raise SystemExit(1)

# Confirma que a voz está acessível à conta sem revelar credenciais.
try:
    r=requests.get(f'https://api.elevenlabs.io/v1/voices/{voice_id}',headers={'xi-api-key':key},timeout=(4,12))
    print('Consulta da voz -> HTTP',r.status_code)
    if r.status_code==200:
        try:
            data=r.json(); print('Nome da voz:',data.get('name','(sem nome)'))
        except Exception: pass
    else:
        try: print('Mensagem:',str(r.json())[:500])
        except Exception: print('Mensagem:',r.text[:500])
except Exception as exc:
    print('Consulta da voz falhou:',type(exc).__name__,exc)

engine=VoiceEngine(v)
text='Boa tarde, senhor. Sistemas online. A nova voz do V está pronta.'
print('\nGerando teste de áudio...')
ok=engine._speak_elevenlabs(text)
print('RESULTADO:', 'OK' if ok else 'FALHOU')
if not ok:
    print('Se a voz foi criada mas ainda não está disponível por API, confira o plano e as permissões da ElevenLabs.')
input('\nPressione Enter para sair...')
raise SystemExit(0 if ok else 2)
