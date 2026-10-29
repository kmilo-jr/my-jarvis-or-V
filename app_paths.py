"""Fonte unica da raiz do projeto, consciente de executavel empacotado.

Dentro do codigo-fonte (rodando de um clone), a raiz e a pasta do projeto.
Dentro de um executavel criado pelo PyInstaller, `__file__` aponta para dentro
de `_internal`, entao a raiz precisa ser a pasta do `.exe` (onde ficam config/,
data/, logs/, assets/ e os modelos opcionais).

Regra: nenhum modulo deve montar caminhos com `Path(__file__)`; importe daqui.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _detectar_raiz() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = _detectar_raiz()


def em_executavel() -> bool:
    return bool(getattr(sys, "frozen", False))


def caminho(*partes: str) -> Path:
    """Monta um caminho relativo a raiz do projeto/executavel."""
    return ROOT.joinpath(*partes)
