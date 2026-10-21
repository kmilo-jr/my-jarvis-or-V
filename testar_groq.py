import json
from pathlib import Path
from brain.groq_client import GroqClient


def main():
    config = json.loads((Path(__file__).resolve().parent / 'config/default.json').read_text(encoding='utf-8'))
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
