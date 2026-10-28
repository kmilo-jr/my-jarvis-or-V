
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
from pathlib import Path
import json, tempfile

BASE=_ROOT
cfg=json.loads((BASE/'config'/'default.json').read_text(encoding='utf-8'))
v=cfg.get('voice',{})
voice=v.get('tts_edge_voice','pt-BR-AntonioNeural')
rate=v.get('tts_edge_rate','+10%')
pitch=v.get('tts_edge_pitch','-10Hz')
volume=v.get('tts_edge_volume','+0%')

print('Testando Edge-TTS 7.2.8...')
print('Voz:',voice)
print('Rate:',rate,' Pitch:',pitch,' Volume:',volume)
try:
    import edge_tts
    from edge_playback.win32_playback import play_mp3_win32
    with tempfile.NamedTemporaryFile(suffix='.mp3',delete=False) as tmp:
        path=Path(tmp.name)
    try:
        edge_tts.Communicate(
            text='Boa tarde. Já estou por aqui. O que temos para hoje?',
            voice=voice,rate=rate,pitch=pitch,volume=volume
        ).save_sync(str(path))
        play_mp3_win32(str(path))
        print('OK: Edge-TTS e player Win32 funcionaram.')
    finally:
        path.unlink(missing_ok=True)
except Exception as e:
    print('FALHOU:',type(e).__name__,str(e))
    raise SystemExit(1)
