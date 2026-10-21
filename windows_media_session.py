from __future__ import annotations

"""Controle direto das sessoes de midia do Windows (SMTC/GSMTC).

O Spotify Desktop publica uma sessao em Windows.Media.Control. Em vez de
simular uma tecla global (que pode ser capturada por outro player) ou usar
/me/player/next, o V pede o Next diretamente para a sessao do Spotify.

O import de PyWinRT e lazy para o projeto continuar importavel em ambientes
nao-Windows e para os self-tests rodarem sem WinRT.
"""

import asyncio
import os
import threading
from typing import Any, Dict, Optional, Tuple


def _run_async(coro):
    """Executa coroutine de forma segura a partir do Core sincrono.

    Normalmente o V chama isto de um QThread sem event loop. O fallback em
    thread separado cobre o caso de algum futuro chamador ja possuir loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box = {"value": None, "error": None}

    def worker():
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # devolve ao chamador original
            box["error"] = exc

    t = threading.Thread(target=worker, name="V-SMTC", daemon=True)
    t.start(); t.join(timeout=12.0)
    if t.is_alive():
        raise TimeoutError("Windows SMTC excedeu o tempo limite")
    if box["error"] is not None:
        raise box["error"]
    return box["value"]


def _import_media_manager():
    if os.name != "nt":
        raise RuntimeError("Windows Media Session so esta disponivel no Windows")
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as MediaManager,
        )
        return MediaManager
    except Exception as exc:
        raise RuntimeError(
            "PyWinRT de Windows.Media.Control nao esta instalado. Rode configurar_prototype.bat."
        ) from exc


async def _session_media(session) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    try:
        data["source_app_user_model_id"] = str(session.source_app_user_model_id or "")
    except Exception:
        data["source_app_user_model_id"] = ""
    try:
        props = await session.try_get_media_properties_async()
        data["title"] = str(getattr(props, "title", "") or "")
        data["artist"] = str(getattr(props, "artist", "") or "")
        data["album_title"] = str(getattr(props, "album_title", "") or "")
    except Exception:
        pass
    try:
        info = session.get_playback_info()
        status = getattr(info, "playback_status", None)
        data["playback_status"] = str(status)
    except Exception:
        pass
    return data


async def _find_spotify_session() -> Tuple[Optional[Any], Dict[str, Any]]:
    MediaManager = _import_media_manager()
    manager = await MediaManager.request_async()
    sessions = list(manager.get_sessions())
    inspected = []
    spotify = None

    # Primeiro tenta a sessao atual, desde que ela seja realmente Spotify.
    try:
        current = manager.get_current_session()
    except Exception:
        current = None
    if current is not None:
        try:
            sid = str(current.source_app_user_model_id or "")
        except Exception:
            sid = ""
        if "spotify" in sid.lower():
            spotify = current

    for session in sessions:
        try:
            sid = str(session.source_app_user_model_id or "")
        except Exception:
            sid = ""
        inspected.append(sid)
        if spotify is None and "spotify" in sid.lower():
            spotify = session

    return spotify, {
        "session_count": len(sessions),
        "session_ids": inspected,
    }


async def _skip_spotify_async(resume_if_paused: bool = False) -> Dict[str, Any]:
    session, diag = await _find_spotify_session()
    if session is None:
        return {
            "ok": False,
            "skip_ok": False,
            "play_ok": False,
            "reason": "spotify_smtc_session_not_found",
            **diag,
        }

    before = await _session_media(session)
    try:
        skip_ok = bool(await session.try_skip_next_async())
    except Exception as exc:
        return {
            "ok": False,
            "skip_ok": False,
            "play_ok": False,
            "reason": "try_skip_next_exception",
            "error": f"{type(exc).__name__}: {exc}",
            "before": before,
            **diag,
        }

    play_ok = None
    if resume_if_paused:
        try:
            play_ok = bool(await session.try_play_async())
        except Exception:
            play_ok = False

    # O Spotify pode atualizar as propriedades alguns ms depois do comando.
    await asyncio.sleep(0.18)
    after = await _session_media(session)
    return {
        "ok": bool(skip_ok),
        "skip_ok": bool(skip_ok),
        "play_ok": play_ok,
        "reason": "ok" if skip_ok else "spotify_session_rejected_skip",
        "before": before,
        "after": after,
        **diag,
    }


def spotify_skip_next(resume_if_paused: bool = False) -> Dict[str, Any]:
    """Pede Next diretamente a sessao de midia do Spotify no Windows."""
    try:
        return _run_async(_skip_spotify_async(bool(resume_if_paused)))
    except Exception as exc:
        return {
            "ok": False,
            "skip_ok": False,
            "play_ok": False,
            "reason": "smtc_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        }


async def _play_spotify_async() -> Dict[str, Any]:
    session, diag = await _find_spotify_session()
    if session is None:
        return {"ok": False, "reason": "spotify_smtc_session_not_found", **diag}
    before = await _session_media(session)
    try:
        ok = bool(await session.try_play_async())
    except Exception as exc:
        return {"ok": False, "reason": "try_play_exception", "error": str(exc), "before": before, **diag}
    return {"ok": ok, "reason": "ok" if ok else "spotify_session_rejected_play", "before": before, **diag}


def spotify_play() -> Dict[str, Any]:
    try:
        return _run_async(_play_spotify_async())
    except Exception as exc:
        return {"ok": False, "reason": "smtc_unavailable", "error": f"{type(exc).__name__}: {exc}"}
