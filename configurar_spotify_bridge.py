"""Instala a extensao Spicetify do Spotify Bridge do V.

Armazenamento do token (leia antes de mexer):
- O V guarda o token do bridge em ``config/spotify_bridge_token.dat`` protegido
  com DPAPI (helper ``secure_store``). O antigo ``.txt`` em texto puro e lido
  apenas para migracao e removido assim que a gravacao protegida funciona.
- O token TAMBEM precisa existir em texto dentro do JS instalado em
  ``%APPDATA%\\spicetify\\Extensions\\vSpotifyBridge.js``. Isso e uma limitacao
  aceita do protocolo: a extensao roda em JS dentro do Spotify e nao tem acesso
  ao DPAPI do usuario. Este configurador restringe o arquivo ao usuario atual.
- Se o JS da extensao vazar (backup, sincronizacao, compartilhamento), rode
  este configurador com ``--rotate`` para gerar e instalar um token NOVO — o V
  passa a exigir o token novo. Nao ha handshake alternativo sem reescrever o
  protocolo.
"""
import os
import secrets
import subprocess
import sys
from pathlib import Path

from secure_store import restrict_file_permissions
from spotify_bridge import TOKEN_FILE, ensure_token, save_token

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / 'integrations' / 'spotify_bridge' / 'extension' / 'vSpotifyBridge.template.js'

appdata = Path(os.environ['APPDATA']) / 'spicetify' / 'Extensions'
out = appdata / 'vSpotifyBridge.js'

# --rotate forca um token novo (use se o JS da extensao vazar/for copiado).
ROTACIONAR = any(arg in ('--rotate', '-r') for arg in sys.argv[1:])

# Reaproveita/migra o token existente (ou gera um novo com --rotate). Depois
# save_token garante a persistencia PROTEGIDA e falha de forma explicita se o
# DPAPI nao estiver disponivel (nada e gravado em texto puro).
try:
    if ROTACIONAR:
        token = secrets.token_urlsafe(32)
        save_token(token)
    else:
        token = ensure_token()
        save_token(token)
except Exception as exc:
    print('\nFALHA: nao foi possivel persistir o token do bridge com seguranca.')
    print('Motivo:', exc)
    raise SystemExit(3)
# Defesa em profundidade: alem do DPAPI, restringe o blob ao usuario atual.
restrict_file_permissions(TOKEN_FILE)

# Instala o JS da extensao com o token atual (unico lugar onde ele fica em
# texto) e restringe o arquivo ao usuario do Windows.
appdata.mkdir(parents=True, exist_ok=True)
text = TEMPLATE.read_text(encoding='utf-8')
if '__TOKEN__' not in text:
    print('Template da extensao sem marcador __TOKEN__; reinstale o V.')
    raise SystemExit(1)
out.write_text(text.replace('__TOKEN__', token), encoding='utf-8')
if restrict_file_permissions(out):
    print('Permissoes restritas ao usuario atual:', out)
else:
    print('AVISO: nao consegui restringir as permissoes de:', out)
    print('       O arquivo contem o token do bridge; restrinja o acesso manualmente.')

print('Extensao V instalada em:', out)
print()
print('AVISO DE SEGURANCA: o JS instalado CONTEM o token do bridge em texto')
print('(limitacao da extensao Spicetify, que nao tem acesso ao DPAPI do Windows).')
print('Se esse arquivo vazar/copiar, rode este configurador com --rotate para')
print('gerar um token novo, por exemplo:')
print('  .venv\\Scripts\\python.exe configurar_spotify_bridge.py --rotate')
print('A copia protegida do V fica em config/spotify_bridge_token.dat.')

try:
    subprocess.run(['spicetify', 'config', 'extensions', 'vSpotifyBridge.js'], check=True)
    subprocess.run(['spicetify', 'backup'], check=False)
    subprocess.run(['spicetify', 'apply'], check=True)
except FileNotFoundError:
    print('\nSpicetify nao encontrado. Rode instalar_spicetify.bat primeiro.')
    raise SystemExit(2)
except subprocess.CalledProcessError as exc:
    print('\nFalha ao aplicar a extensao:', exc)
    raise SystemExit(exc.returncode or 1)
print('\nOK. Feche COMPLETAMENTE o Spotify e abra novamente.')
print('Depois, inicie o V normalmente. O bridge roda oculto dentro do V.')
