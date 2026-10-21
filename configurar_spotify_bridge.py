import os, re, secrets, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TOKEN_FILE=ROOT/'config'/'spotify_bridge_token.txt'
TEMPLATE=ROOT/'integrations'/'spotify_bridge'/'extension'/'vSpotifyBridge.template.js'
TOKEN_FILE.parent.mkdir(parents=True,exist_ok=True)

# Reutiliza token de uma extensão existente quando possível.
token=''
appdata=Path(os.environ['APPDATA'])/'spicetify'/'Extensions'
out=appdata/'vSpotifyBridge.js'
if TOKEN_FILE.exists(): token=TOKEN_FILE.read_text(encoding='utf-8').strip()
if not token and out.exists():
    try:
        m=re.search(r'const\s+TOKEN\s*=\s*["\']([^"\']+)["\']',out.read_text(encoding='utf-8',errors='ignore'))
        if m: token=m.group(1).strip()
    except Exception: pass
if not token: token=secrets.token_urlsafe(32)
TOKEN_FILE.write_text(token,encoding='utf-8')
appdata.mkdir(parents=True,exist_ok=True)
text=TEMPLATE.read_text(encoding='utf-8').replace('__TOKEN__',token)
out.write_text(text,encoding='utf-8')
print('Extensao V instalada em:',out)

try:
    subprocess.run(['spicetify','config','extensions','vSpotifyBridge.js'],check=True)
    subprocess.run(['spicetify','backup'],check=False)
    subprocess.run(['spicetify','apply'],check=True)
except FileNotFoundError:
    print('\nSpicetify nao encontrado. Rode instalar_spicetify.bat primeiro.')
    raise SystemExit(2)
except subprocess.CalledProcessError as exc:
    print('\nFalha ao aplicar a extensao:',exc)
    raise SystemExit(exc.returncode or 1)
print('\nOK. Feche COMPLETAMENTE o Spotify e abra novamente.')
print('Depois, inicie o V normalmente. O bridge roda oculto dentro do V.')
