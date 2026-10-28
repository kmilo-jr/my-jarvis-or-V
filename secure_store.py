"""Armazenamento local de segredos em repouso (Windows DPAPI).

Este modulo centraliza a criptografia de segredos gravados no disco — token
OAuth do Spotify, API key do Gemini, senha de app do Gmail — para que o
projeto use um unico caminho, em vez de cada modulo reinventar (e errar) a
chamada do pywin32.

No Windows usa ``CryptProtectData``/``CryptUnprotectData`` no escopo do
usuario: o blob so pode ser lido pelo mesmo usuario no mesmo computador.
``CRYPTPROTECT_UI_FORBIDDEN`` (0x1) impede qualquer dialogo de UI durante a
operacao, que roda em threads de fundo.

Regra de ouro: NAO existe fallback para texto puro. Se o DPAPI nao estiver
disponivel (pywin32 ausente, plataforma nao-Windows, blob corrompido), a
gravacao falha com :class:`SecureStoreError` e a leitura devolve o erro para
quem chamou decidir. Nunca grave um segredo em claro "so para funcionar".
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from vlog import get_logger

try:  # pragma: no cover - depende do ambiente Windows
    import win32crypt as win32crypt
except Exception:  # pywin32 ausente ou plataforma sem DPAPI
    win32crypt = None  # type: ignore[assignment]

log = get_logger(__name__)

# win32crypt.CRYPTPROTECT_UI_FORBIDDEN nao existe em todas as versoes do
# pywin32; o valor documentado pela Microsoft e 0x1.
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class SecureStoreError(RuntimeError):
    """DPAPI indisponivel/falhou; o segredo NAO foi gravado nem lido."""


def dpapi_available() -> bool:
    """True quando o DPAPI do usuario pode ser usado neste processo."""
    return os.name == "nt" and win32crypt is not None


def _require_dpapi() -> Any:
    if os.name != "nt":
        raise SecureStoreError(
            "DPAPI exige Windows; segredo local nao pode ser protegido nesta plataforma."
        )
    if win32crypt is None:
        raise SecureStoreError(
            "DPAPI indisponivel: instale o pywin32 no ambiente do V (.venv). "
            "O segredo NAO sera gravado em texto puro."
        )
    return win32crypt


def protect_bytes(data: bytes, description: str = "V") -> bytes:
    """Criptografa ``data`` com DPAPI e devolve o blob binario protegido."""
    module = _require_dpapi()
    try:
        return module.CryptProtectData(
            bytes(data), description, None, None, None, CRYPTPROTECT_UI_FORBIDDEN
        )
    except SecureStoreError:
        raise
    except Exception as exc:
        log.warning("DPAPI: falha ao criptografar segredo: %s", type(exc).__name__)
        raise SecureStoreError(
            "Falha ao criptografar o segredo com o DPAPI do Windows "
            f"({type(exc).__name__}). Nada foi gravado."
        ) from exc


def unprotect_bytes(blob: bytes, description: str = "V") -> bytes:
    """Descriptografa um blob DPAPI previamente protegido."""
    module = _require_dpapi()
    try:
        # CryptUnprotectData devolve (description, data).
        return module.CryptUnprotectData(
            bytes(blob), None, None, None, CRYPTPROTECT_UI_FORBIDDEN
        )[1]
    except SecureStoreError:
        raise
    except Exception as exc:
        log.warning("DPAPI: falha ao descriptografar segredo: %s", type(exc).__name__)
        raise SecureStoreError(
            "Falha ao descriptografar o segredo com o DPAPI do Windows "
            f"({type(exc).__name__}). O arquivo pode ser de outro usuario/PC ou estar corrompido."
        ) from exc


def protect_text(text: str, description: str = "V") -> str:
    """Protege um texto e devolve o blob DPAPI codificado em base64 (ASCII)."""
    return base64.b64encode(protect_bytes(str(text).encode("utf-8"), description)).decode("ascii")


def unprotect_text(encoded: str, description: str = "V") -> str:
    """Reverte :func:`protect_text`."""
    raw = str(encoded or "").strip()
    if not raw:
        raise SecureStoreError("Blob DPAPI vazio; segredo ausente ou corrompido.")
    try:
        blob = base64.b64decode(raw.encode("ascii"), validate=True)
    except Exception as exc:
        raise SecureStoreError(
            "Blob DPAPI invalido: nao e base64 valido."
        ) from exc
    return unprotect_bytes(blob, description).decode("utf-8")


def protect_json(obj: Any, description: str = "V") -> str:
    """Serializa ``obj`` em JSON e devolve o blob DPAPI em base64."""
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(protect_bytes(payload, description)).decode("ascii")


def unprotect_json(encoded: str, description: str = "V") -> Any:
    """Reverte :func:`protect_json`; levanta :class:`SecureStoreError` se falhar."""
    clear = unprotect_text(encoded, description)
    try:
        return json.loads(clear)
    except Exception as exc:
        raise SecureStoreError("Blob DPAPI descriptografado nao contem JSON valido.") from exc


def restrict_file_permissions(path) -> bool:
    """Restringe um arquivo com segredo ao usuario atual do Windows.

    Usado quando o conteudo NAO pode ser cifrado — caso do JS da extensao do
    Spotify, que precisa do token em claro para autenticar. No Windows aplica
    uma DACL via ``icacls`` (remove heranca e concede acesso total apenas ao
    usuario atual); em outras plataformas tenta ``chmod 0o600``.

    Devolve True em caso de sucesso e NUNCA levanta excecao: quem chama decide
    como avisar o usuario. Nao use isso como substituto de DPAPI.
    """
    alvo = Path(path)
    try:
        if not alvo.exists():
            return False
        if os.name == "nt":
            usuario = str(os.environ.get("USERNAME") or "").strip()
            dominio = str(os.environ.get("USERDOMAIN") or "").strip()
            if not usuario:
                return False
            identidades = [usuario]
            if dominio:
                identidades.insert(0, f"{dominio}\\{usuario}")
            for identidade in identidades:
                try:
                    resultado = subprocess.run(
                        ["icacls", str(alvo), "/inheritance:r", "/grant:r", f"{identidade}:F"],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                except Exception:
                    continue
                if resultado.returncode == 0:
                    return True
            # Falhou: tenta devolver a heranca para nao deixar o arquivo
            # inacessivel por engano (icacls pode remover a heranca antes de
            # falhar no /grant).
            try:
                subprocess.run(
                    ["icacls", str(alvo), "/inheritance:e"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except Exception:
                pass
            return False
        os.chmod(alvo, 0o600)
        return True
    except Exception as exc:
        log.warning(
            "nao foi possivel restringir permissoes de %s: %s",
            alvo.name,
            type(exc).__name__,
        )
        return False

