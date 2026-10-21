from pathlib import Path
import json, shutil

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
candidates = sorted(PARENT.glob('V_PROTOTYPE_0_7_3*'))
if not candidates:
    print('Nao encontrei uma pasta 0.7.3 ao lado desta. Rode configurar_spotify_api.bat.')
    input('Enter para sair...')
    raise SystemExit(1)
src = candidates[0]
oldcfg = src / 'config' / 'default.json'
newcfg = HERE / 'config' / 'default.json'
try:
    a = json.loads(oldcfg.read_text(encoding='utf-8'))
    b = json.loads(newcfg.read_text(encoding='utf-8'))
    cid = ((a.get('spotify_api') or {}).get('client_id') or '').strip()
    if cid:
        b.setdefault('spotify_api', {})['client_id'] = cid
        newcfg.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding='utf-8')
    tok = src / 'config' / 'spotify_token.json'
    if tok.exists():
        shutil.copy2(tok, HERE / 'config' / 'spotify_token.json')
    print('Configuracao Spotify migrada da 0.7.3 para a 0.7.4.')
except Exception as exc:
    print('Falha ao migrar:', exc)
input('Enter para sair...')
