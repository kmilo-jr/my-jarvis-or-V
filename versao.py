"""Fonte única de versão do V.

Qualquer lugar que mostre versão/build deve importar daqui em vez de repetir
strings soltas (existiam 1.6, 1.8.3, 1.8 e 1.9.8 convivendo no mesmo código).
"""

from __future__ import annotations

VERSAO = "1.9.8"
NOME = "V Prototype"
TITULO = f"{NOME} {VERSAO}"
BUILD = "V198-LAN-20261028"

# Compatibilidade com chamadas antigas que montavam a string na mão.
BANNER = f"{TITULO} // BUILD {BUILD}"


def versao_completa() -> str:
    return f"{TITULO} ({BUILD})"
