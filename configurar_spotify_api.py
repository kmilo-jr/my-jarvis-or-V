from __future__ import annotations
import json
import sys
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
from spotify_api import SpotifyClient, save_client_id, load_spotify_config

DASHBOARD = "https://developer.spotify.com/dashboard"
REDIRECT = "http://127.0.0.1:8765/callback"

print("=" * 68)
print("V PROTOTYPE 0.7 - CONFIGURAR SPOTIFY WEB API")
print("=" * 68)
print("1) O Spotify Web API exige uma conta Spotify Premium para controlar playback.")
print("2) No Spotify Developer Dashboard, crie um app e marque Web API.")
print(f"3) Em Redirect URIs, adicione EXATAMENTE: {REDIRECT}")
print("4) Copie o Client ID. O V usa OAuth PKCE; NAO precisa do Client Secret.")
print()
try:
    open_now = input("Abrir o Spotify Developer Dashboard agora? [S/n]: ").strip().lower()
    if open_now not in {"n", "nao", "não"}:
        webbrowser.open(DASHBOARD)
except Exception:
    pass

current = str(load_spotify_config().get("client_id", "")).strip()
prompt = f"Client ID [{current}]: " if current else "Cole o Client ID: "
client_id = input(prompt).strip() or current
if not client_id:
    print("Client ID vazio. Configuracao cancelada.")
    raise SystemExit(2)
save_client_id(client_id)
print("Client ID salvo. Abrindo login/autorizacao do Spotify...")
try:
    client = SpotifyClient()
    token = client.authorize_interactive(timeout=240)
    me = client.me() or {}
    print()
    print("SPOTIFY CONECTADO COM SUCESSO")
    print("Conta:", me.get("display_name") or me.get("id") or "autorizada")
    devices = client.devices()
    if devices:
        print("Dispositivos detectados:")
        for d in devices:
            print(" -", d.get("name"), "|", d.get("type"), "| ativo=" + str(d.get("is_active")))
    else:
        print("Nenhum dispositivo ativo agora. Abra o Spotify Desktop antes do teste de musica.")
    input("\nPressione ENTER para fechar...")
except Exception as exc:
    print("\nFALHA:", exc)
    print("Confira se o Redirect URI cadastrado no Dashboard e exatamente:", REDIRECT)
    input("\nPressione ENTER para fechar...")
    raise SystemExit(1)
