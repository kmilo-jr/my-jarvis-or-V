"""Verifica o caminho completo do Spotify: V -> bridge -> extensao -> player.

Uso:
    python tools/verificar_spotify_e2e.py
    python tools/verificar_spotify_e2e.py --timeout 30 --no-launch
    python tools/verificar_spotify_e2e.py --json

Codigos de saida:
    0  bridge + extensao respondendo e comando real devolvendo estado
    1  extensao nao apareceu (Spotify fechado, Spicetify sem apply ou token antigo)
    2  extensao online, mas o comando nao voltou

Difere de `tools/diagnosticar_spotify_bridge.py`: aqui o teste e ponta a ponta,
com um comando de verdade e com a checagem de que o protocolo antigo (token na
query string) esta realmente bloqueado.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import spotify_bridge as bridge  # noqa: E402

BASE = "http://127.0.0.1:8766"


def _http(path: str, method: str = "GET", body: dict | None = None, token: bool = True) -> tuple[int, str]:
    dados = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=dados, method=method)
    if dados is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Bridge-Token", bridge.ensure_token())
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _protocolo_antigo_bloqueado() -> bool:
    """Token na query so vale no handshake; /next deve responder 403."""
    codigo, _ = _http(f"/next?token={bridge.ensure_token()}", token=False)
    return codigo == 403


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste ponta a ponta do Spotify Bridge do V")
    parser.add_argument("--timeout", type=float, default=20.0, help="espera pela extensao (s)")
    parser.add_argument("--no-launch", action="store_true", help="nao abre o Spotify se estiver fechado")
    parser.add_argument("--json", action="store_true", help="saida em JSON")
    args = parser.parse_args()

    relatorio: dict = {"bridge": None, "extensao": False, "comando": None, "protocolo_antigo_bloqueado": None}

    if not bridge.start_bridge_background():
        relatorio["erro"] = "nao foi possivel iniciar o bridge na porta configurada"
        print(json.dumps(relatorio, ensure_ascii=False, indent=2) if args.json else relatorio["erro"])
        return 1

    online, health = bridge.wait_extension(seconds=args.timeout, launch=not args.no_launch)
    relatorio["bridge"] = {
        "token_storage": health.get("token_storage"),
        "legacy_query_token": health.get("legacy_query_token"),
    }
    relatorio["extensao"] = bool(online)
    if not online:
        relatorio["erro"] = "extensao do Spicetify nao apareceu"
        if args.json:
            print(json.dumps(relatorio, ensure_ascii=False, indent=2))
        else:
            print("FALHA: a extensao do Spotify nao apareceu.")
            print("  - o Spotify esta aberto?")
            print("  - ja rodou configurar_spotify_bridge.bat depois de reinstalar/atualizar o Spotify?")
            print("  - se o token foi rotacionado, feche e reabra o Spotify.")
        return 1

    ok, resultado = bridge.command("status", timeout=8)
    estado = resultado.get("status") if isinstance(resultado, dict) else None
    relatorio["comando"] = {"ok": bool(ok), "status": estado, "erro": (resultado or {}).get("error")}
    relatorio["protocolo_antigo_bloqueado"] = _protocolo_antigo_bloqueado()

    if args.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    else:
        print("bridge: online | armazenamento do token:", relatorio["bridge"].get("token_storage"))
        print("extensao: online")
        if ok and estado:
            print(f"player: {estado.get('title')} — {estado.get('artist')}")
            print(f"        playing={estado.get('playing')} volume={estado.get('volume')} "
                  f"posicao={estado.get('position_ms')}/{estado.get('duration_ms')} ms")
        else:
            print("comando status: FALHOU —", relatorio["comando"].get("erro"))
        print("protocolo antigo (token na query):",
              "bloqueado" if relatorio["protocolo_antigo_bloqueado"] else "ACEITO (revisar)")

    if not ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
