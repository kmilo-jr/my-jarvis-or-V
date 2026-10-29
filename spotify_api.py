from __future__ import annotations
from app_paths import ROOT

import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import unicodedata
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from secure_store import SecureStoreError, protect_json, unprotect_json
from vlog import get_logger

BASE = ROOT
CONFIG_PATH = BASE / "config" / "default.json"
TOKEN_PATH = BASE / "config" / "spotify_token.json"
API = "https://api.spotify.com/v1"
ACCOUNTS = "https://accounts.spotify.com"

log = get_logger(__name__)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def split_track_artist(query: str):
    q = str(query or "").strip()
    m = re.match(r"^(.+?)\s+(?:do|da|de)\s+(.+)$", q, flags=re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return q, ""


def load_spotify_config():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data.get("spotify_api", {}) or {}


def save_client_id(client_id: str):
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    data.setdefault("spotify_api", {})["client_id"] = str(client_id or "").strip()
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class SpotifyAPIError(RuntimeError):
    pass


# Formato atual de config/spotify_token.json:
#   {"version": 2, "protect": "dpapi", "scheme": "windows-dpapi-user",
#    "data": "<token JSON completo, protegido com DPAPI e em base64>"}
# Arquivos antigos guardavam access_token/refresh_token direto no topo do
# JSON, em texto puro. Eles continuam sendo lidos e, na proxima gravacao,
# passam a ser gravados protegidos (migracao transparente).
_TOKEN_VERSION = 2
_TOKEN_PROTECT = "dpapi"
_TOKEN_SCHEME = "windows-dpapi-user"


def _read_token():
    try:
        raw = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        log.warning("nao foi possivel ler o token do Spotify: %s", type(exc).__name__)
        return {}
    if not isinstance(raw, dict):
        log.warning("token do Spotify em formato inesperado; sera ignorado")
        return {}
    scheme = str(raw.get("protect") or "plain").strip().lower()
    if scheme != _TOKEN_PROTECT:
        # Formato legado em texto puro: apenas le. A migracao acontece no
        # proximo _write_token bem-sucedido.
        return raw
    encoded = str(raw.get("data") or "").strip()
    if not encoded:
        log.warning("token do Spotify marcado como DPAPI sem blob; sera ignorado")
        return {}
    try:
        token = unprotect_json(encoded, "V Spotify OAuth")
    except SecureStoreError as exc:
        log.warning("falha ao desproteger o token do Spotify: %s", type(exc).__name__)
        raise SpotifyAPIError(
            "Nao foi possivel ler o token do Spotify protegido pelo Windows (DPAPI). "
            "O arquivo pode ser de outro usuario/PC. Rode configurar_spotify_api.bat "
            "e autorize o Spotify novamente."
        ) from exc
    if not isinstance(token, dict):
        log.warning("token do Spotify descriptografado em formato inesperado; sera ignorado")
        return {}
    return token


def _write_token(token):
    """Grava o token OAuth cifrado com DPAPI. Nunca grava segredo em claro.

    Se o DPAPI falhar, levanta SpotifyAPIError de forma explicita e deixa o
    arquivo anterior intacto (gravacao atomica via temporario + replace).
    """
    payload_token = dict(token or {})
    try:
        protected = protect_json(payload_token, "V Spotify OAuth")
    except SecureStoreError as exc:
        log.warning(
            "nao foi possivel proteger o token do Spotify com DPAPI: %s",
            type(exc).__name__,
        )
        raise SpotifyAPIError(
            "Nao foi possivel salvar o token do Spotify com seguranca: o DPAPI do "
            "Windows nao esta disponivel. Nada foi gravado e o token anterior foi "
            "mantido. Instale/reinstale o pywin32 no .venv e tente novamente."
        ) from exc
    payload = {
        "version": _TOKEN_VERSION,
        "protect": _TOKEN_PROTECT,
        "scheme": _TOKEN_SCHEME,
        "data": protected,
    }
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_PATH.with_suffix(TOKEN_PATH.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(TOKEN_PATH)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _response_json(response, *, context="Spotify", allow_empty=False):
    """Converte uma resposta HTTP em JSON sem deixar JSONDecodeError escapar.

    Alguns endpoints de playback do Spotify respondem 204 No Content por
    design. Além disso, respostas intermediárias/proxies podem chegar sem
    corpo ou com HTML/texto. O V deve tratar isso como estado HTTP, não como
    erro interno de JSON.
    """
    status = int(getattr(response, "status_code", 0) or 0)
    raw = getattr(response, "content", b"") or b""
    text = (getattr(response, "text", "") or "").strip()
    content_type = str((getattr(response, "headers", {}) or {}).get("Content-Type", "")).lower()

    if status == 204 or not raw or not text:
        if allow_empty:
            return None
        raise SpotifyAPIError(f"{context}: resposta vazia do Spotify (HTTP {status or '?'})")

    try:
        return response.json()
    except Exception as exc:
        snippet = text[:220].replace("\n", " ")
        detail = f"; Content-Type={content_type}" if content_type else ""
        raise SpotifyAPIError(
            f"{context}: resposta nao-JSON do Spotify (HTTP {status or '?'}{detail}): {snippet or 'sem corpo'}"
        ) from exc


class _OAuthCallback(BaseHTTPRequestHandler):
    result = {}
    expected_state = ""

    def log_message(self, *_args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        code = (qs.get("code") or [""])[0]
        state = (qs.get("state") or [""])[0]
        error = (qs.get("error") or [""])[0]
        if state != self.expected_state:
            self.__class__.result = {"error": "state_mismatch"}
            body = "Falha de seguranca no login do Spotify. Pode fechar esta aba."
        elif error:
            self.__class__.result = {"error": error}
            body = f"Spotify recusou a autorizacao: {error}. Pode fechar esta aba."
        else:
            self.__class__.result = {"code": code}
            body = "Spotify conectado ao V. Pode fechar esta aba e voltar ao V."
        raw = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class SpotifyClient:
    def __init__(self):
        self.cfg = load_spotify_config()
        self.client_id = str(self.cfg.get("client_id", "")).strip()
        self.redirect_uri = str(self.cfg.get("redirect_uri", "http://127.0.0.1:8765/callback"))
        self.scopes = list(self.cfg.get("scopes") or [
            "user-read-playback-state", "user-modify-playback-state", "user-read-currently-playing"
        ])
        self.timeout = float(self.cfg.get("request_timeout", 12))
        self.verify_timeout = float(self.cfg.get("verify_timeout", 4.0))
        self._token_lock = threading.Lock()

    @property
    def configured(self):
        return bool(self.client_id)

    def _pkce_pair(self):
        verifier = secrets.token_urlsafe(64)[:96]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        return verifier, challenge

    def authorize_interactive(self, timeout=180):
        if not self.client_id:
            raise SpotifyAPIError("Spotify API sem Client ID. Rode configurar_spotify_api.bat primeiro.")
        parsed = urlparse(self.redirect_uri)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
            raise SpotifyAPIError("Use redirect URI loopback http://127.0.0.1:PORT/callback no modo local.")
        port = parsed.port or 8765
        verifier, challenge = self._pkce_pair()
        state = secrets.token_urlsafe(24)
        _OAuthCallback.result = {}
        _OAuthCallback.expected_state = state
        server = HTTPServer(("127.0.0.1", port), _OAuthCallback)
        server.timeout = 1.0
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
            "show_dialog": "true",
        }
        webbrowser.open(f"{ACCOUNTS}/authorize?{urlencode(params)}")
        deadline = time.time() + timeout
        while time.time() < deadline and not _OAuthCallback.result:
            server.handle_request()
        server.server_close()
        result = dict(_OAuthCallback.result)
        if not result:
            raise SpotifyAPIError("Tempo de autorizacao do Spotify expirou.")
        if result.get("error"):
            raise SpotifyAPIError(f"Autorizacao do Spotify falhou: {result['error']}")
        code = result.get("code")
        r = requests.post(
            f"{ACCOUNTS}/api/token",
            data={
                "client_id": self.client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
            },
            timeout=self.timeout,
        )
        if r.status_code >= 300:
            raise SpotifyAPIError(f"Falha ao trocar codigo por token: HTTP {r.status_code} {r.text[:240]}")
        token = _response_json(r, context="Autorizacao do Spotify", allow_empty=False) or {}
        if not token.get("access_token"):
            raise SpotifyAPIError("Autorizacao do Spotify nao retornou access_token.")
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600)) - 45
        _write_token(token)
        return token

    def _refresh(self, token):
        refresh = token.get("refresh_token")
        if not refresh:
            return self.authorize_interactive()
        r = requests.post(
            f"{ACCOUNTS}/api/token",
            data={
                "client_id": self.client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh,
            },
            timeout=self.timeout,
        )
        if r.status_code >= 300:
            return self.authorize_interactive()
        new = _response_json(r, context="Renovacao do token Spotify", allow_empty=False) or {}
        if not new.get("access_token"):
            raise SpotifyAPIError("Renovacao do token Spotify nao retornou access_token. Rode configurar_spotify_api.bat novamente.")
        if "refresh_token" not in new:
            new["refresh_token"] = refresh
        new["expires_at"] = time.time() + int(new.get("expires_in", 3600)) - 45
        _write_token(new)
        return new

    def token(self, interactive=False):
        with self._token_lock:
            token = _read_token()
            if token.get("access_token") and float(token.get("expires_at", 0)) > time.time():
                return token["access_token"]
            if token.get("refresh_token"):
                return self._refresh(token)["access_token"]
            if interactive:
                return self.authorize_interactive()["access_token"]
            raise SpotifyAPIError("Spotify ainda nao foi autorizado. Rode configurar_spotify_api.bat.")

    def _request(self, method, path, *, params=None, json_body=None, retry=True):
        access = self.token(interactive=False)
        headers = {"Authorization": f"Bearer {access}"}
        r = requests.request(method, API + path, headers=headers, params=params, json=json_body, timeout=self.timeout)
        if r.status_code == 401 and retry:
            tok = _read_token()
            if tok:
                self._refresh(tok)
            return self._request(method, path, params=params, json_body=json_body, retry=False)
        if r.status_code == 429 and retry:
            wait = min(10, max(1, int(r.headers.get("Retry-After", "1") or 1)))
            time.sleep(wait)
            return self._request(method, path, params=params, json_body=json_body, retry=False)
        if r.status_code >= 300:
            detail = ""
            try:
                payload = _response_json(r, context="Spotify API", allow_empty=True) or {}
                err = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(err, dict):
                    detail = str(err.get("message") or "")
                elif err:
                    detail = str(err)
            except SpotifyAPIError:
                detail = (r.text or "")[:240]
            raise SpotifyAPIError(f"Spotify API HTTP {r.status_code}: {detail or 'erro sem detalhe'}")
        return _response_json(r, context=f"Spotify API {method.upper()} {path}", allow_empty=True)

    def me(self):
        return self._request("GET", "/me")

    def devices(self):
        data = self._request("GET", "/me/player/devices") or {}
        return data.get("devices") or []

    @staticmethod
    def _device_usable(device):
        return bool(device) and not device.get("is_restricted") and bool(device.get("id"))

    def _rank_device(self, device):
        """Prioriza o Spotify Desktop do PC em vez de qualquer device ativo.

        Antes, um celular/TV ativo podia vencer simplesmente por estar ativo. Para o V,
        um device tipo Computer e, se possível, com nome semelhante ao COMPUTERNAME do
        Windows é preferível. Device restrito ou sem id nunca é controlável pela API.
        """
        if not self._device_usable(device):
            return -10_000
        dtype = _norm(device.get("type"))
        name = _norm(device.get("name"))
        computer_name = _norm(os.environ.get("COMPUTERNAME", ""))
        score = 0
        if dtype == "computer":
            score += 1000
        elif dtype in ("smartphone", "tablet"):
            score += 200
        if computer_name and (computer_name in name or name in computer_name):
            score += 500
        if device.get("is_active"):
            score += 120
        if device.get("supports_volume"):
            score += 10
        return score

    def _best_device(self, prefer_computer=True):
        devices = [d for d in self.devices() if self._device_usable(d)]
        if not devices:
            return None
        if prefer_computer:
            computers = [d for d in devices if _norm(d.get("type")) == "computer"]
            if computers:
                return max(computers, key=self._rank_device)
        return max(devices, key=self._rank_device)

    def playback_state(self):
        return self._request("GET", "/me/player")

    def _active_device_id(self):
        try:
            state = self.playback_state() or {}
            dev = state.get("device") or {}
            if dev.get("is_active") and dev.get("id"):
                return dev.get("id")
        except SpotifyAPIError:
            pass
        try:
            active = next((d for d in self.devices() if d.get("is_active") and self._device_usable(d)), None)
            return active.get("id") if active else None
        except SpotifyAPIError:
            return None

    def wait_for_device(self, launch_callback=None, seconds=12.0, prefer_computer=True):
        # Se o Desktop ja estiver visivel ao Spotify Connect, use-o mesmo que outro
        # device (celular/TV) esteja ativo.
        device = self._best_device(prefer_computer=prefer_computer)
        if device and (not prefer_computer or _norm(device.get("type")) == "computer"):
            return device
        if launch_callback:
            try:
                launch_callback()
            except Exception:
                pass
        deadline = time.time() + seconds
        last = device
        while time.time() < deadline:
            time.sleep(0.75)
            try:
                current = self._best_device(prefer_computer=prefer_computer)
            except SpotifyAPIError:
                current = None
            if current:
                last = current
                if not prefer_computer or _norm(current.get("type")) == "computer":
                    return current
        return last

    def transfer_playback(self, device_id, play=True):
        if not device_id:
            raise SpotifyAPIError("O Spotify retornou um dispositivo sem ID controlavel.")
        self._request(
            "PUT",
            "/me/player",
            json_body={"device_ids": [device_id], "play": bool(play)},
        )
        return True

    def wait_until_device_active(self, device_id, seconds=6.0):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self._active_device_id() == device_id:
                return True
            time.sleep(0.35)
        return False

    def search_track(self, query):
        track, artist = split_track_artist(query)
        if not track:
            raise SpotifyAPIError("Nome da musica vazio.")
        q = f'track:"{track}"'
        if artist:
            q += f' artist:"{artist}"'
        data = self._request("GET", "/search", params={"q": q, "type": "track", "limit": 10}) or {}
        items = ((data.get("tracks") or {}).get("items") or [])
        if not items and artist:
            data = self._request("GET", "/search", params={"q": f"{track} {artist}", "type": "track", "limit": 10}) or {}
            items = ((data.get("tracks") or {}).get("items") or [])
        if not items:
            return None
        wt, wa = _norm(track), _norm(artist)
        scored = []
        for item in items:
            name = _norm(item.get("name"))
            artists = [_norm(a.get("name")) for a in (item.get("artists") or [])]
            score = 0
            if name == wt: score += 100
            elif wt and wt in name: score += 55
            if wa:
                if wa in artists: score += 100
                elif any(wa in a or a in wa for a in artists if a): score += 55
            score += min(20, int(item.get("popularity") or 0) // 5)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def currently_playing(self):
        return self._request("GET", "/me/player/currently-playing")

    def _verify_track_on_device(self, track_id, device_id=None, seconds=None):
        seconds = self.verify_timeout if seconds is None else float(seconds)
        deadline = time.time() + seconds
        last = {}
        while time.time() < deadline:
            time.sleep(0.4)
            try:
                state = self.playback_state() or {}
            except SpotifyAPIError:
                state = {}
            last = state
            cur = (state.get("item") or {})
            dev = state.get("device") or {}
            same_track = bool(cur.get("id") and cur.get("id") == track_id)
            same_device = (not device_id) or (dev.get("id") == device_id)
            if same_track and same_device:
                return True, state
        return False, last

    def _device_label(self, device):
        if not device:
            return "dispositivo desconhecido"
        name = str(device.get("name") or "Spotify").strip()
        dtype = str(device.get("type") or "").strip()
        return f"{name} ({dtype})" if dtype else name

    def queue_state(self):
        return self._request("GET", "/me/player/queue") or {}

    @staticmethod
    def _queue_items(snapshot):
        return list((snapshot or {}).get("queue") or [])

    def _wait_target_in_queue(self, track_id, seconds=None):
        """Espera o item realmente aparecer na fila e devolve sua posição.

        O Spotify avisa que a ordem entre endpoints de Player não é garantida.
        Portanto o V NÃO chama Next imediatamente após Add to Queue: primeiro
        confirma via GET /me/player/queue que o alvo entrou na fila e descobre
        quantos avanços são necessários.
        """
        seconds = float(
            self.cfg.get("queue_sync_timeout", 6.0) if seconds is None else seconds
        )
        deadline = time.time() + seconds
        last = {}
        while time.time() < deadline:
            try:
                snap = self.queue_state() or {}
            except SpotifyAPIError:
                snap = {}
            last = snap
            for idx, qitem in enumerate(self._queue_items(snap)):
                if (qitem or {}).get("id") == track_id:
                    return idx, snap
            time.sleep(0.35)
        return None, last

    def add_to_queue(self, uri, device_id=None):
        params = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        self._request("POST", "/me/player/queue", params=params)
        return True

    def skip_next(self, device_id=None):
        params = {"device_id": device_id} if device_id else None
        self._request("POST", "/me/player/next", params=params)
        return True

    @staticmethod
    def _is_web_player_device(device):
        if not device:
            return False
        text = _norm(f"{device.get('name', '')} {device.get('type', '')}")
        hints = (
            "web player", "webplayer", "chrome", "firefox", "edge",
            "browser", "navegador", "opera", "brave",
        )
        return any(h in text for h in hints)

    def _wait_for_web_player(self, before_ids=None, seconds=16.0):
        before_ids = set(before_ids or [])
        deadline = time.time() + float(seconds)
        best = None
        while time.time() < deadline:
            try:
                devices = [d for d in self.devices() if self._device_usable(d)]
            except SpotifyAPIError:
                devices = []
            for d in devices:
                if self._is_web_player_device(d):
                    if d.get("is_active"):
                        return d
                    best = d
            # Se um novo Computer apareceu depois de abrir open.spotify.com, ele e um
            # forte candidato a ser o Web Player, mesmo que o nome varie por idioma.
            newcomers = [
                d for d in devices
                if d.get("id") not in before_ids and _norm(d.get("type")) == "computer"
            ]
            if newcomers:
                active = next((d for d in newcomers if d.get("is_active")), None)
                return active or newcomers[0]
            time.sleep(0.6)
        return best

    def _verify_track(self, track_id, seconds=None):
        seconds = self.verify_timeout if seconds is None else float(seconds)
        deadline = time.time() + seconds
        last = {}
        while time.time() < deadline:
            time.sleep(0.35)
            try:
                state = self.playback_state() or {}
            except SpotifyAPIError:
                state = {}
            last = state
            item = state.get("item") or {}
            if item.get("id") == track_id:
                return True, state
        return False, last

    def _play_via_queue_walk(self, item, state):
        """Toca a faixa via Queue + Windows SMTC direcionado ao Spotify.

        A API do Spotify continua responsavel por identificar/enfileirar a faixa.
        O salto e enviado diretamente a sessao de midia do Spotify publicada no
        Windows.Media.Control (GSMTC/SMTC). Assim o V nao depende de /next e nem de
        uma tecla multimidia global que pode ser capturada por outro aplicativo.
        """
        uri = item.get("uri")
        track_id = item.get("id")
        if not uri or not track_id:
            return False, state or {}, "track_sem_uri", {"reason": "track_sem_uri"}

        self.add_to_queue(uri, device_id=None)
        index, queue_snapshot = self._wait_target_in_queue(track_id)
        if index is None:
            return False, state or {}, "queue_target_not_visible", {
                "reason": "target_not_visible",
                "queue_ids": [x.get("id") for x in self._queue_items(queue_snapshot)[:25]],
            }

        hops_needed = int(index) + 1
        max_hops = int(self.cfg.get("max_queue_hops", 20) or 20)
        if hops_needed > max_hops:
            return False, state or {}, "queue_target_too_far", {
                "reason": "too_many_hops",
                "index": index,
                "hops_needed": hops_needed,
                "max_hops": max_hops,
            }

        trace = {
            "target_index": index,
            "hops_needed": hops_needed,
            "next_transport": "windows_smtc_spotify_session",
            "steps": [],
        }
        last = state or {}
        initially_paused = not bool((state or {}).get("is_playing"))

        try:
            from windows_media_session import spotify_skip_next
        except Exception:
            spotify_skip_next = None
        try:
            from legacy_tools import _press_media_key
        except Exception:
            _press_media_key = None

        for step in range(hops_needed):
            before_id = ((last.get("item") or {}).get("id"))
            smtc = {"ok": False, "reason": "not_available"}
            sent = False
            transport = "windows_smtc_spotify_session"

            if spotify_skip_next is not None:
                try:
                    smtc = spotify_skip_next(resume_if_paused=initially_paused)
                    sent = bool(smtc.get("skip_ok") or smtc.get("ok"))
                except Exception as exc:
                    smtc = {"ok": False, "reason": "exception", "error": f"{type(exc).__name__}: {exc}"}

            # Compatibilidade: se o Windows nao publicar uma sessao SMTC do Spotify,
            # tenta a antiga tecla global. /me/player/next fica como ultimo recurso.
            key_sent = False
            if not sent and _press_media_key is not None:
                transport = "windows_media_key_fallback"
                try:
                    key_sent = bool(_press_media_key("next"))
                except Exception:
                    key_sent = False
                sent = key_sent

            if not sent:
                transport = "spotify_api_next_last_resort"
                self.skip_next(device_id=None)
                sent = True

            deadline = time.time() + 3.2
            changed = False
            samples = []
            while time.time() < deadline:
                time.sleep(0.24)
                try:
                    cur_state = self.playback_state() or {}
                except SpotifyAPIError:
                    cur_state = {}
                if cur_state:
                    last = cur_state
                cur_id = ((cur_state.get("item") or {}).get("id"))
                samples.append({
                    "current_id": cur_id,
                    "is_playing": cur_state.get("is_playing"),
                })
                if cur_id == track_id:
                    trace["steps"].append({
                        "step": step + 1,
                        "before_id": before_id,
                        "current_id": cur_id,
                        "transport": transport,
                        "smtc": smtc,
                        "key_sent": key_sent,
                        "result": "target_reached",
                    })
                    return True, cur_state, "queue_windows_smtc_next", trace
                if cur_id and cur_id != before_id:
                    changed = True
                    trace["steps"].append({
                        "step": step + 1,
                        "before_id": before_id,
                        "current_id": cur_id,
                        "transport": transport,
                        "smtc": smtc,
                        "key_sent": key_sent,
                        "result": "advanced",
                    })
                    break

            if not changed and ((last.get("item") or {}).get("id")) != track_id:
                trace["steps"].append({
                    "step": step + 1,
                    "before_id": before_id,
                    "current_id": ((last.get("item") or {}).get("id")),
                    "transport": transport,
                    "smtc": smtc,
                    "key_sent": key_sent,
                    "result": "no_change_confirmed",
                    "samples": samples[-5:],
                })
                # Tenta UMA nova solicitacao SMTC com uma sessao recapturada. Isso e
                # diferente de reenviar a mesma tecla global: o manager localiza de
                # novo a sessao real do Spotify antes de chamar TrySkipNextAsync.
                if spotify_skip_next is not None:
                    retry = spotify_skip_next(resume_if_paused=initially_paused)
                    if retry.get("skip_ok") or retry.get("ok"):
                        ok, after = self._verify_track(track_id, seconds=2.8)
                        trace["steps"].append({
                            "step": step + 1,
                            "transport": "windows_smtc_spotify_session_retry",
                            "smtc": retry,
                            "result": "target_reached" if ok else "retry_sent",
                        })
                        if ok:
                            return True, after, "queue_windows_smtc_next", trace

        ok, after = self._verify_track(track_id, seconds=max(3.0, self.verify_timeout))
        return ok, after or last, "queue_windows_smtc_next", trace

    def _play_via_web_player(self, item):
        """Fallback para o Web Player, que nao apresenta o bug atual do Desktop."""
        uri = item.get("uri")
        track_id = item.get("id")
        try:
            before = self.devices()
        except SpotifyAPIError:
            before = []
        before_ids = {d.get("id") for d in before if d.get("id")}

        url = ((item.get("external_urls") or {}).get("spotify") or "https://open.spotify.com/")
        try:
            webbrowser.open(url)
        except Exception:
            webbrowser.open("https://open.spotify.com/")

        web = self._wait_for_web_player(
            before_ids=before_ids,
            seconds=float(self.cfg.get("web_player_wait_timeout", 16.0)),
        )
        if not web or not web.get("id"):
            return False, {}, None, "web_player_nao_apareceu"

        web_id = web.get("id")
        # No Web Player a chamada /play continua sendo o caminho mais direto.
        # Primeiro tentamos diretamente no device; se estiver inativo, ativamos sem
        # forcar play da faixa anterior e tentamos novamente apos confirmacao.
        try:
            self._request(
                "PUT", "/me/player/play",
                params={"device_id": web_id},
                json_body={"uris": [uri], "position_ms": 0},
            )
        except SpotifyAPIError as exc:
            if "HTTP 404" not in str(exc):
                raise
            self.transfer_playback(web_id, play=False)
            self.wait_until_device_active(web_id, seconds=5.0)
            self._request(
                "PUT", "/me/player/play",
                params={"device_id": web_id},
                json_body={"uris": [uri], "position_ms": 0},
            )

        ok, state = self._verify_track_on_device(track_id, device_id=web_id, seconds=max(5.0, self.verify_timeout))
        return ok, state, web, "web_player"

    def _write_playback_log(self, payload):
        try:
            log_dir = BASE / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            safe = dict(payload or {})
            (log_dir / "spotify_api_last.json").write_text(
                json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def play_track(self, query, launch_callback=None):
        item = self.search_track(query)
        if not item:
            return False, f"Nao encontrei {query} no catalogo do Spotify."

        artists = ", ".join(a.get("name", "") for a in item.get("artists") or [])
        track_id = item.get("id")
        uri = item.get("uri")

        try:
            state = self.playback_state() or {}
        except SpotifyAPIError:
            state = {}
        current = state.get("item") or {}
        active = state.get("device") or {}

        if current.get("id") == track_id and state.get("is_playing"):
            return True, f"{item.get('name')} de {artists} ja esta tocando no Spotify."

        # 0.7.4 é DESKTOP-ONLY: nunca abre Web Player automaticamente.
        # Se o Desktop ainda não apareceu no Connect, abre o app e espera.
        if not (active and self._device_usable(active)):
            desktop = self.wait_for_device(
                launch_callback=launch_callback,
                seconds=float(self.cfg.get("device_wait_timeout", 12.0)),
                prefer_computer=True,
            )
            try:
                state = self.playback_state() or {}
            except SpotifyAPIError:
                state = {}
            active = state.get("device") or desktop or {}
            current = state.get("item") or {}

        attempts = []

        # O caminho seguro hoje exige uma sessão já tocando no Desktop.
        # Não usamos /play com URI porque esse é justamente o endpoint com o
        # problema observado. Com playback ativo, Queue + vários Next funciona
        # sem mouse, sem Web Player e sem /play.
        if active and self._device_usable(active):
            try:
                ok, after, route, trace = self._play_via_queue_walk(item, state)
                attempts.append({
                    "route": route,
                    "ok": ok,
                    "device": active.get("name"),
                    "trace": trace,
                })
                self._write_playback_log({
                    "query": query,
                    "track": item.get("name"),
                    "artist": artists,
                    "uri": uri,
                    "route": route,
                    "desktop_only": True,
                    "attempts": attempts,
                })
                if ok:
                    return True, (
                        f"Tocando {item.get('name')} de {artists} no Spotify Desktop "
                        f"em {self._device_label((after or {}).get('device') or active)}."
                    )
            except SpotifyAPIError as exc:
                attempts.append({"route": "queue_walk", "ok": False, "error": str(exc)})

        self._write_playback_log({
            "query": query,
            "track": item.get("name"),
            "artist": artists,
            "uri": uri,
            "desktop_only": True,
            "state_is_playing": state.get("is_playing"),
            "active_device": {
                "id": active.get("id"),
                "name": active.get("name"),
                "type": active.get("type"),
            } if active else None,
            "attempts": attempts,
        })

        return False, (
            f"Encontrei {item.get('name')} de {artists}, mas nao consegui concluir a troca "
            "no Spotify Desktop. O V nao abriu o navegador. "
            "Diagnostico salvo em logs\\spotify_api_last.json."
        )

    def pause(self):
        device = self._best_device()
        params = {"device_id": device.get("id")} if device else None
        self._request("PUT", "/me/player/pause", params=params)
        return True

    def next(self):
        device = self._best_device()
        params = {"device_id": device.get("id")} if device else None
        self._request("POST", "/me/player/next", params=params)
        return True

    def previous(self):
        device = self._best_device()
        params = {"device_id": device.get("id")} if device else None
        self._request("POST", "/me/player/previous", params=params)
        return True


def api_configured():
    return SpotifyClient().configured


def play_track_api(query, launch_callback=None):
    client = SpotifyClient()
    if not client.configured:
        return False, "Spotify API ainda nao configurada. Rode configurar_spotify_api.bat, cole o Client ID e autorize o V no navegador."
    try:
        client.token(interactive=False)
    except SpotifyAPIError as exc:
        return False, str(exc)
    try:
        return client.play_track(query, launch_callback=launch_callback)
    except SpotifyAPIError as exc:
        return False, f"Spotify API: {exc}"
