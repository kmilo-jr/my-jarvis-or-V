from pathlib import Path
import time

sound=Path(__file__).resolve().parent/'assets'/'sounds'/'v_processing.wav'
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
