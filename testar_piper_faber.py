from pathlib import Path
import sys, tempfile, os, wave
BASE=Path(__file__).resolve().parent
MODEL=BASE/'models'/'piper'/'pt_BR-faber-medium.onnx'
print('=== TESTE PIPER / FABER ===')
print('Modelo:', MODEL)
if not MODEL.exists():
    print('FALHOU: modelo nao instalado. Rode instalar_piper_faber.bat.')
    raise SystemExit(2)
try:
    from piper import PiperVoice, SynthesisConfig
except Exception as e:
    print('FALHOU ao importar Piper:', e)
    raise SystemExit(3)
try:
    v=PiperVoice.load(str(MODEL), use_cuda=False)
    fd,path=tempfile.mkstemp(prefix='v_faber_test_',suffix='.wav'); os.close(fd)
    syn=SynthesisConfig(length_scale=0.92, noise_scale=0.667, noise_w_scale=0.8, volume=1.0, normalize_audio=True)
    with wave.open(path,'wb') as wf:
        v.synthesize_wav('Boa tarde. Sistemas online. V está pronto para operar.', wf, syn_config=syn)
    if os.name=='nt':
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
    print('OK: Piper/Faber sintetizou a frase offline.')
finally:
    try: os.remove(path)
    except Exception: pass
