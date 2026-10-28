
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import json
from pathlib import Path
from brain.groq_client import GroqClient


def main():
    config = json.loads((_ROOT / 'config/default.json').read_text(encoding='utf-8'))
    client = GroqClient(config.get('brain', {}))
    if not client.available:
        print('Groq sem chave ou desativado. Execute configurar_groq.bat.')
        return 2
    answer = client.generate('Responda brevemente em português.', [], 'Responda apenas: Groq online.')
    print(answer or client.last_error)
    print('Modelo:', client.model)
    print('Tempo em ms:', client.last_latency.get('total_ms'))
    return 0 if answer else 1


if __name__ == '__main__':
    raise SystemExit(main())
