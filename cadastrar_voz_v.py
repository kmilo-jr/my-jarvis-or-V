import argparse
from pathlib import Path

from voice.voice_clone import VoiceCloneSetupError, register_voice_from_sample


def main():
    parser = argparse.ArgumentParser(description="Cadastre uma amostra de voz autorizada no provedor configurado.")
    parser.add_argument("sample", type=Path, help="caminho para um arquivo de áudio autorizado")
    args = parser.parse_args()
    try:
        result = register_voice_from_sample(args.sample, name="V Prime", description="Amostra autorizada pelo usuário.")
    except VoiceCloneSetupError as exc:
        print(f"Não foi possível cadastrar a voz: {exc}")
        raise SystemExit(1)
    print(f"Voz cadastrada: {result['voice_id']}")
    print("Reabra o V para usar a nova voz.")


if __name__ == "__main__":
    main()
