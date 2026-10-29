from __future__ import annotations
from app_paths import ROOT

import json
import os
from pathlib import Path

from secure_store import SecureStoreError, protect_text, unprotect_text
from vlog import get_logger

log = get_logger(__name__)


def _base_dir() -> Path:
    return ROOT


def key_path(config: dict | None = None) -> Path:
    config = config or {}
    raw = str(config.get("tts_eleven_key_file", "config/elevenlabs_key.dat") or "config/elevenlabs_key.dat")
    p = Path(raw)
    return p if p.is_absolute() else (_base_dir() / p)


def save_key(api_key: str, path: Path | None = None) -> dict:
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("API Key vazia.")
    path = Path(path or key_path())
    path.parent.mkdir(parents=True, exist_ok=True)

    # Sem fallback em texto puro: se o DPAPI falhar, a chave NAO e gravada e o
    # arquivo anterior (se existir) permanece intacto.
    try:
        encoded = protect_text(key, "V ElevenLabs API Key")
    except SecureStoreError as exc:
        log.warning(
            "nao foi possivel proteger a API key da ElevenLabs com DPAPI: %s",
            type(exc).__name__,
        )
        raise RuntimeError(
            "Nao foi possivel salvar a API key da ElevenLabs com seguranca: o DPAPI "
            "do Windows nao esta disponivel. A chave NAO foi gravada em texto puro. "
            "Instale/reinstale o pywin32 no .venv e tente novamente."
        ) from exc

    payload = {
        "version": 1,
        "protected": True,
        "scheme": "windows-dpapi-user",
        "data": encoded,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return {"path": str(path), "protected": True, "scheme": payload["scheme"]}


def load_key(config: dict | None = None, path: Path | None = None) -> str:
    # Compatibilidade: save_key(chave, path) e load_key(path) leem bem, mas o
    # primeiro argumento de load_key e o config. Aceitar caminho posicional evita
    # o erro "WindowsPath has no attribute get" em testes e chamadas diretas.
    if path is None and isinstance(config, (str, Path)):
        path, config = Path(config), None
    env = str(os.environ.get("ELEVENLABS_API_KEY", "") or "").strip()
    if env:
        return env
    path = Path(path or key_path(config))
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("nao foi possivel ler a API key da ElevenLabs: %s", type(exc).__name__)
        return ""
    if not isinstance(payload, dict):
        log.warning("API key da ElevenLabs em formato inesperado; sera ignorada")
        return ""
    data = str(payload.get("data", "") or "")
    if not data:
        return ""
    if payload.get("protected"):
        try:
            return unprotect_text(data, "V ElevenLabs API Key").strip()
        except SecureStoreError as exc:
            log.warning(
                "falha ao desproteger a API key da ElevenLabs: %s",
                type(exc).__name__,
            )
            return ""
    # Formato legado em texto puro: le e sera migrado no proximo save_key.
    log.warning("API key da ElevenLabs em texto puro no disco; sera migrada na proxima gravacao")
    return data.strip()
