"""Adjust the local robot effect without changing the TTS voice or credentials."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Efeito robótico do V (ElevenLabs e Qwen). Reinicie o V após alterar.')
    parser.add_argument('--intensidade', type=float, default=.35, help='Mistura de 0 a 1; padrão: 0.35')
    parser.add_argument('--desligar', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.intensidade <= 1:
        parser.error('A intensidade deve estar entre 0 e 1.')
    path = Path(__file__).resolve().parent / 'config/default.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data.setdefault('voice', {}).update(tts_robot_enabled=not args.desligar,
                                      tts_robot_intensity=args.intensidade)
    tmp = path.with_suffix('.robot.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    print('Efeito desligado.' if args.desligar else f'Efeito ativado: {args.intensidade:.0%}.')
    print('Reinicie o V para carregar a alteração.')


if __name__ == '__main__':
    main()
