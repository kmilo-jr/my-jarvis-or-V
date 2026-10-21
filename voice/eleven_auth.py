from __future__ import annotations

import base64
import json
import os
from pathlib import Path


def _base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


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
    payload: dict
    if os.name == "nt":
        try:
            import win32crypt
            protected = win32crypt.CryptProtectData(
                key.encode("utf-8"), "V ElevenLabs API Key", None, None, None, 0
            )[1]
            payload = {
                "version": 1,
                "protected": True,
                "scheme": "windows-dpapi-user",
                "data": base64.b64encode(protected).decode("ascii"),
            }
        except Exception:
            payload = {"version": 1, "protected": False, "scheme": "plain", "data": key}
    else:
        payload = {"version": 1, "protected": False, "scheme": "plain", "data": key}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return {"path": str(path), "protected": bool(payload.get("protected")), "scheme": payload.get("scheme")}


def load_key(config: dict | None = None, path: Path | None = None) -> str:
    env = str(os.environ.get("ELEVENLABS_API_KEY", "") or "").strip()
    if env:
        return env
    path = Path(path or key_path(config))
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    data = payload.get("data", "")
    if not data:
        return ""
    if payload.get("protected"):
        if os.name != "nt":
            return ""
        try:
            import win32crypt
            clear = win32crypt.CryptUnprotectData(base64.b64decode(data), None, None, None, 0)[1]
            return clear.decode("utf-8").strip()
        except Exception:
            return ""
    return str(data).strip()
