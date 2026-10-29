"""Logging centralizado do V.

Motivo: o código tinha ~260 blocos ``except Exception:`` e boa parte deles
engolia o erro sem deixar rastro. Este módulo dá um logger único, com arquivo
rotativo em ``logs/v_assistant.log``, para que as correções possam registrar a
causa em vez de sumir com ela.

Uso:
    from vlog import get_logger
    log = get_logger(__name__)
    try:
        ...
    except Exception as exc:
        log.warning("falha ao carregar Piper: %s", exc)

Nunca registre tokens, chaves de API, conteúdo de e-mail ou corpo de resposta
HTTP; registre tipo da exceção e contexto curto.
"""

from __future__ import annotations
from app_paths import ROOT

import logging
import logging.handlers
import sys
from pathlib import Path

BASE = ROOT
LOG_DIR = BASE / "logs"
_ARQUIVO = "v_assistant.log"
_configurado = False


def setup_logging(level: int = logging.INFO, arquivo: str | None = None) -> logging.Logger:
    """Configura o logger raiz do V (idempotente)."""
    global _configurado
    raiz = logging.getLogger("v")
    if _configurado:
        return raiz

    raiz.setLevel(level)
    raiz.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s :: %(message)s")

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / (arquivo or _ARQUIVO),
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(fmt)
        raiz.addHandler(handler)
    except OSError as exc:  # ambiente sem permissão de escrita em logs/
        print(f"vlog: nao foi possivel abrir arquivo de log: {exc}", file=sys.stderr)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    raiz.addHandler(console)

    _configurado = True
    return raiz


def get_logger(nome: str = "v") -> logging.Logger:
    """Devolve um logger filho de ``v`` (configura na primeira chamada)."""
    setup_logging()
    if not nome or nome in {"v", "__main__"}:
        return logging.getLogger("v")
    limpo = nome.replace("\\", ".").replace("/", ".")
    if limpo.startswith("v."):
        limpo = limpo[2:]
    return logging.getLogger(f"v.{limpo}")
