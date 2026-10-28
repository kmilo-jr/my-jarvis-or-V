
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import json, time
from spotify_bridge import start_bridge_background, health, wait_extension, command
print('=== V 1.5 // DIAGNOSTICO SPOTIFY BRIDGE ===')
print('Bridge start:', start_bridge_background())
code, h=health(); print('Health HTTP:',code); print(json.dumps(h,ensure_ascii=False,indent=2))
ok, h=wait_extension(seconds=8,launch=True); print('\nExtensao online:',ok); print(json.dumps(h,ensure_ascii=False,indent=2))
if ok:
    ok2, s=command('status'); print('\nStatus:',ok2); print(json.dumps(s,ensure_ascii=False,indent=2))
