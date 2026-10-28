from pathlib import Path
import json, shutil

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
candidates = []
for folder in PARENT.glob('V_PROTOTYPE_0_7_1*'):
    cfg = folder / 'config' / 'default.json'
    tok = folder / 'config' / 'spotify_token.json'
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding='utf-8'))
            client_id = str((data.get('spotify_api') or {}).get('client_id') or '').strip()
        except Exception:
            client_id = ''
        if client_id:
            candidates.append((folder.stat().st_mtime, folder, client_id, tok))

if not candidates:
    print('Nao encontrei automaticamente uma pasta V_PROTOTYPE_0_7_1 com Client ID configurado.')
    print('Use configurar_spotify_api.bat nesta versao.')
    input('\nEnter para sair...')
    raise SystemExit(1)

_, folder, client_id, tok = sorted(candidates, reverse=True)[0]
current = HERE / 'config' / 'default.json'
data = json.loads(current.read_text(encoding='utf-8'))
data.setdefault('spotify_api', {})['client_id'] = client_id
current.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
if tok.exists():
    shutil.copy2(tok, HERE / 'config' / 'spotify_token.json')
    token_msg = 'Token OAuth copiado localmente.'
else:
    token_msg = 'Token anterior nao encontrado; sera necessario autorizar novamente.'
print(f'Configuracao migrada de: {folder.name}')
print(token_msg)
print('Pronto. Agora inicie o V 0.7.2.')
input('\nEnter para sair...')
