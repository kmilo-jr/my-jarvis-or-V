from __future__ import annotations
import subprocess, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MODEL_DIR = BASE / 'models' / 'piper'
VOICE = 'pt_BR-faber-medium'
MODEL = MODEL_DIR / f'{VOICE}.onnx'
CONFIG = MODEL_DIR / f'{VOICE}.onnx.json'

def run(cmd):
    print('>', ' '.join(map(str, cmd)))
    return subprocess.call(cmd, cwd=str(BASE))

def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print('=== V - INSTALADOR PIPER FABER OFFLINE ===')
    print('Voz:', VOICE)
    print('Destino:', MODEL_DIR)
    print()
    if run([sys.executable, '-m', 'pip', 'install', 'piper-tts==1.8.0']) != 0:
        print('\nFALHA: nao foi possivel instalar piper-tts 1.8.0.')
        return 1
    if MODEL.exists() and CONFIG.exists():
        print('\nModelo Faber ja esta instalado.')
    else:
        if run([sys.executable, '-m', 'piper.download_voices', VOICE, '--data-dir', str(MODEL_DIR)]) != 0:
            print('\nFALHA: nao foi possivel baixar o modelo Faber.')
            return 2
    if not MODEL.exists() or not CONFIG.exists():
        print('\nFALHA: download terminou, mas os arquivos do modelo nao foram encontrados.')
        return 3
    print('\nOK: Piper/Faber instalado.')
    print('Modelo:', MODEL)
    print('Agora execute testar_piper_faber.bat.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
