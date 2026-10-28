"""Gera ``config/default.example.json`` a partir de ``config/default.json``.

Motivo: o ``default.json`` real concentra credenciais (client id do Spotify,
id de voz privado, caminhos de usuario) e nao pode ser versionado como
exemplo. Este script deriva o exemplo anonimizando apenas os valores
sensiveis, mantendo TODAS as chaves estruturais para que o arquivo continue
servindo de modelo.

Regras de anonimizacao (somente valores, nunca chaves):
- chaves que parecem segredo (key/token/secret/password/credential/client_id/
  voice_id/private_key/access_key) tem o valor trocado por ``<nome_da_chave>``;
  chaves terminadas em ``_file``/``_files`` sao preservadas, pois guardam o
  caminho de um arquivo de segredo, nao o segredo em si;
- ``mac`` e tratado como identificador privado;
- URLs de hosts que nao sao loopback nem bases publicas conhecidas (ex.: um
  webhook pessoal colado em algum ``*_url``) sao trocadas por ``<nome_da_chave>``;
- caminhos de usuario (``C:\\Users\\fulano`` e variantes) sao trocados por
  ``\\Users\\<usuario>``;
- enderecos de e-mail sao trocados por ``<email@exemplo.com>``.

Uso:
    python tools/gerar_config_exemplo.py           # grava config/default.example.json
    python tools/gerar_config_exemplo.py --check   # valida sem gravar nada

O ``--check`` confirma que o exemplo tem exatamente a mesma arvore de chaves
do original e que nenhum valor sensivel vazou. A saida e 0 quando esta tudo
certo e 1 quando ha problema.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE / "config"
SOURCE_PADRAO = CONFIG_DIR / "default.json"
TARGET_PADRAO = CONFIG_DIR / "default.example.json"

# Trechos de nome de chave que indicam valor secreto ou identificador privado.
PARTES_SECRETAS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passwd",
    "pwd",
    "credential",
    "client_id",
    "voice_id",
    "private_key",
    "access_key",
)
# Chaves exatas que guardam identificador privado (e nao sao cobertas acima).
CHAVES_SECRETAS = {"mac"}

_USUARIO_NO_CAMINHO = re.compile(r"(?i)\b([a-z]):[\\/]+users[\\/]+[^\\/\"'\s]+")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"^(?P<esquema>https?)://(?P<host>[^/:\s]+)", re.I)
# Hosts de servico publico cuja URL base nao identifica ninguem.
HOSTS_PUBLICOS = {"generativelanguage.googleapis.com"}
HOSTS_LOCAIS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def url_pessoal(chave: str, valor: str) -> bool:
    """Diz se uma URL guardada sob esta chave deveria ser anonimizada."""
    if "url" not in chave.lower():
        return False
    achado = _URL.match(valor.strip())
    if not achado:
        return False
    host = achado.group("host").lower()
    return host not in HOSTS_PUBLICOS and host not in HOSTS_LOCAIS


def chave_secreta(chave: str) -> bool:
    """Diz se o valor desta chave deve ser anonimizado."""
    nome = chave.lower()
    if nome in CHAVES_SECRETAS:
        return True
    # Caminhos de arquivos de segredo (config/gemini_key.dat) nao sao segredos.
    if nome.endswith("_file") or nome.endswith("_files"):
        return False
    return any(parte in nome for parte in PARTES_SECRETAS)


def limpar(valor, chave: str, alterados: list[str]):
    """Devolve o valor anonimizado; registra em ``alterados`` o que mudou."""
    if isinstance(valor, dict):
        return {k: limpar(v, k, alterados) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpar(v, chave, alterados) for v in valor]
    if not isinstance(valor, str):
        return valor

    if chave_secreta(chave) and valor.strip():
        alterados.append(chave)
        return f"<{chave.lower()}>"

    if url_pessoal(chave, valor):
        alterados.append(chave)
        return f"<{chave.lower()}>"

    limpo = _USUARIO_NO_CAMINHO.sub(r"\1:\\Users\\<usuario>", valor)
    limpo = _EMAIL.sub("<email@exemplo.com>", limpo)
    if limpo != valor:
        alterados.append(chave)
    return limpo


def arvore(objeto, prefixo: str = ""):
    """Lista os caminhos de todas as chaves (para comparar estruturas)."""
    caminhos = []
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            caminho = f"{prefixo}.{chave}" if prefixo else chave
            caminhos.append(caminho)
            caminhos.extend(arvore(valor, caminho))
    elif isinstance(objeto, list):
        for indice, item in enumerate(objeto):
            caminhos.extend(arvore(item, f"{prefixo}[{indice}]"))
    return caminhos


def folhas(objeto, prefixo: str = ""):
    """Lista pares (caminho, chave, valor) das folhas do dicionario."""
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            caminho = f"{prefixo}.{chave}" if prefixo else chave
            yield from folhas(valor, caminho)
    elif isinstance(objeto, list):
        for indice, item in enumerate(objeto):
            yield from folhas(item, f"{prefixo}[{indice}]")
    else:
        chave = prefixo.rsplit(".", 1)[-1].split("[", 1)[0]
        yield prefixo, chave, objeto


def montar_exemplo(original: dict, alterados: list[str]) -> dict:
    return limpar(original, "", alterados)


def checar(original: dict, exemplo: dict) -> list[str]:
    """Confere estrutura e ausencia de vazamentos; devolve a lista de erros."""
    problemas: list[str] = []
    if arvore(original) != arvore(exemplo):
        problemas.append("a arvore de chaves do exemplo difere da do default.json")

    corpo = json.dumps(exemplo, ensure_ascii=False)
    for caminho, chave, valor in folhas(original):
        if not (isinstance(valor, str) and valor.strip()):
            continue
        if chave_secreta(chave) or url_pessoal(chave, valor):
            if valor in corpo:
                problemas.append(f"valor sensivel de {caminho} ainda aparece no exemplo")
    if _USUARIO_NO_CAMINHO.search(corpo):
        problemas.append("o exemplo ainda contem caminho de usuario")
    if _EMAIL.search(corpo):
        problemas.append("o exemplo ainda contem endereco de e-mail")
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera/valida config/default.example.json sem segredos.")
    parser.add_argument("--check", action="store_true", help="apenas valida; nao grava o exemplo")
    parser.add_argument("--source", default=str(SOURCE_PADRAO), help="config default a ler")
    parser.add_argument("--target", default=str(TARGET_PADRAO), help="arquivo de exemplo a gravar")
    args = parser.parse_args(argv)

    origem = Path(args.source)
    destino = Path(args.target)
    if not origem.is_file():
        print(f"erro: nao encontrei {origem}", file=sys.stderr)
        return 1
    try:
        original = json.loads(origem.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"erro: falha ao ler {origem}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(original, dict):
        print("erro: o default.json deveria ser um objeto JSON", file=sys.stderr)
        return 1

    alterados: list[str] = []
    exemplo = montar_exemplo(original, alterados)
    problemas = checar(original, exemplo)

    if problemas:
        print("FALHOU: o exemplo nao passou na validacao:", file=sys.stderr)
        for problema in problemas:
            print(f"  - {problema}", file=sys.stderr)
        return 1

    if args.check:
        unicos = sorted(set(alterados))
        print(f"check OK: {len(arvore(original))} chaves, {len(unicos)} valores anonimizados")
        if unicos:
            print("anonimizados: " + ", ".join(unicos))
        print(f"exemplo valido (nao gravado): {destino}")
        return 0

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(exemplo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    unicos = sorted(set(alterados))
    print(f"gerado: {destino}")
    print(f"chaves preservadas: {len(arvore(original))}; valores anonimizados: {len(unicos)}")
    if unicos:
        print("anonimizados: " + ", ".join(unicos))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
