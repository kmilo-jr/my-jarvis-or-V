
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
from pathlib import Path
import time

sound=_ROOT/'assets'/'sounds'/'v_processing.wav'
if not sound.exists():
    raise SystemExit(f'Som nao encontrado: {sound}')
try:
    import winsound
except Exception as exc:
    raise SystemExit(f'Este teste e destinado ao Windows: {exc}')
print('Tocando o som de processamento por 4 segundos...')
winsound.PlaySound(str(sound), winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_LOOP)
time.sleep(4.0)
try:
    winsound.PlaySound(None, winsound.SND_PURGE)
except Exception:
    winsound.PlaySound(None, 0)
print('Teste concluido.')
