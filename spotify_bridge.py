from __future__ import annotations

import json
import os
import queue
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config" / "default.json"
TOKEN_FILE = BASE / "config" / "spotify_bridge_token.txt"
LOG_DIR = BASE / "logs"
LOG_FILE = LOG_DIR / "spotify_bridge.log"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766

_commands: queue.Queue = queue.Queue()
_waiters: dict[str, dict] = {}
_waiters_lock = threading.Lock()
_last_seen = {"extension": 0.0, "last_status": None}
_server_thread: threading.Thread | None = None
_server = None


def _cfg():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data.get("spotify_bridge", {}) or {}


def _host_port():
    cfg = _cfg()
    return str(cfg.get("host") or DEFAULT_HOST), int(cfg.get("port") or DEFAULT_PORT)


def _log(event: str, **data):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.time(), "event": event, **data}
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _installed_extension_path() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "spicetify" / "Extensions" / "vSpotifyBridge.js"


def _token_from_installed_extension() -> str | None:
    path = _installed_extension_path()
    if not path or not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'const\s+TOKEN\s*=\s*["\']([^"\']+)["\']', text)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def ensure_token() -> str:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    # Se o protótipo já instalou a extensão, reutiliza o token para evitar
    # incompatibilidade enquanto o usuário migra para o V integrado.
    tok = _token_from_installed_extension() or secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(tok, encoding="utf-8")
    return tok


def _authorized(handler) -> bool:
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(handler.path).query)
    return q.get("token", [""])[0] == ensure_token()


class _Handler(BaseHTTPRequestHandler):
    server_version = "VSpotifyBridge/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body_json(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        if path == "/health":
            age = None if not _last_seen["extension"] else round(time.time() - _last_seen["extension"], 2)
            self._json(200, {
                "ok": True,
                "bridge": "online",
                "extension_seen": bool(_last_seen["extension"]),
                "extension_age_s": age,
                "last_status": _last_seen["last_status"],
            })
            return
        if not _authorized(self):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        if path == "/next":
            _last_seen["extension"] = time.time()
            try:
                cmd = _commands.get(timeout=0.25)
            except queue.Empty:
                self.send_response(204)
                self._cors()
                self.end_headers()
                return
            self._json(200, cmd)
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        if not _authorized(self):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            body = self._body_json()
        except Exception as exc:
            self._json(400, {"ok": False, "error": f"invalid_json: {exc}"})
            return
        if path == "/command":
            action = str(body.get("action", "")).strip()
            args = body.get("args") or {}
            allowed = {"status", "play_uri", "next", "previous", "pause", "play", "toggle", "volume", "shuffle"}
            if action not in allowed:
                self._json(400, {"ok": False, "error": "unsupported_action"})
                return
            cid = secrets.token_hex(8)
            evt = threading.Event()
            slot = {"event": evt, "result": None}
            with _waiters_lock:
                _waiters[cid] = slot
            cmd = {"id": cid, "action": action, "args": args}
            _commands.put(cmd)
            _log("command", **cmd)
            timeout = float(body.get("timeout", _cfg().get("command_timeout", 7.0)) or 7.0)
            if not evt.wait(timeout=timeout):
                with _waiters_lock:
                    _waiters.pop(cid, None)
                self._json(504, {"ok": False, "error": "extension_timeout", "id": cid})
                return
            result = slot["result"] or {"ok": False, "error": "empty_result"}
            self._json(200, result)
            return
        if path == "/result":
            cid = str(body.get("id", ""))
            _last_seen["extension"] = time.time()
            if body.get("status"):
                _last_seen["last_status"] = body.get("status")
            with _waiters_lock:
                slot = _waiters.pop(cid, None)
            if slot:
                slot["result"] = body
                slot["event"].set()
            _log("result", **body)
            self._json(200, {"ok": True})
            return
        if path == "/heartbeat":
            _last_seen["extension"] = time.time()
            if body.get("status"):
                _last_seen["last_status"] = body.get("status")
            self._json(200, {"ok": True})
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt, *args):
        return


def _url(path: str) -> str:
    host, port = _host_port()
    return f"http://{host}:{port}{path}"


def _request(path: str, method="GET", obj=None, timeout=2.5, token=False):
    if token:
        sep = "&" if "?" in path else "?"
        path = f"{path}{sep}token={ensure_token()}"
    data = None if obj is None else json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(_url(path), data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return int(r.status), json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return int(e.code), body
    except Exception as exc:
        return 0, {"ok": False, "error": str(exc)}


def health():
    code, body = _request("/health", timeout=1.2)
    return code, body or {}


def start_bridge_background() -> bool:
    global _server_thread, _server
    cfg = _cfg()
    if cfg.get("enabled", True) is False:
        return False
    ensure_token()
    code, body = health()
    if code == 200 and body.get("bridge") == "online":
        return True
    if _server_thread and _server_thread.is_alive():
        return True
    host, port = _host_port()
    try:
        _server = ThreadingHTTPServer((host, port), _Handler)
    except OSError as exc:
        _log("bridge_bind_failed", error=f"{type(exc).__name__}: {exc}")
        # Pode haver uma instância antiga do protótipo usando a porta.
        code, body = health()
        return bool(code == 200 and body.get("bridge") == "online")

    def run():
        _log("bridge_start", host=host, port=port)
        try:
            _server.serve_forever(poll_interval=0.2)
        except Exception as exc:
            _log("bridge_crash", error=f"{type(exc).__name__}: {exc}")

    _server_thread = threading.Thread(target=run, name="VSpotifyBridge", daemon=True)
    _server_thread.start()
    time.sleep(0.08)
    return True


def _launch_spotify():
    try:
        import legacy_tools
        return bool(legacy_tools._launch_spotify())
    except Exception:
        try:
            if hasattr(os, "startfile"):
                os.startfile("spotify:")
                return True
        except Exception:
            pass
    return False


def wait_extension(seconds=None, launch=True):
    start_bridge_background()
    cfg = _cfg()
    seconds = float(seconds if seconds is not None else cfg.get("extension_wait_seconds", 10.0) or 10.0)
    if launch:
        _launch_spotify()
    deadline = time.time() + seconds
    last = {}
    while time.time() < deadline:
        code, body = health()
        last = body or {}
        age = last.get("extension_age_s")
        if code == 200 and last.get("extension_seen") and (age is None or float(age) < 8.0):
            return True, last
        time.sleep(0.35)
    return False, last


def command(action: str, args=None, timeout=None, launch_if_needed=False):
    start_bridge_background()
    if launch_if_needed:
        ok, _ = wait_extension(launch=True)
        if not ok:
            return False, {"ok": False, "error": "spotify_extension_offline"}
    cfg = _cfg()
    timeout = float(timeout if timeout is not None else cfg.get("command_timeout", 7.0) or 7.0)
    code, body = _request(
        "/command", "POST",
        {"action": action, "args": args or {}, "timeout": timeout},
        timeout=timeout + 1.5,
        token=True,
    )
    body = body or {}
    return bool(code == 200 and body.get("ok")), body


def control(action: str):
    mapping = {"play_pause": "toggle", "next": "next", "previous": "previous", "pause": "pause", "play": "play"}
    target = mapping.get(action, action)
    ok, body = command(target, launch_if_needed=False)
    if not ok:
        return False, str(body.get("error") or "Spotify Bridge indisponível.")
    labels = {
        "next": "Avançando para a próxima faixa.",
        "previous": "Voltando para a faixa anterior.",
        "pause": "Pausado.",
        "play": "Continuando.",
        "toggle": "Pronto.",
    }
    return True, labels.get(target, "Pronto.")


def play_query(query: str):
    q = str(query or "").strip()
    if not q:
        return False, "Não recebi o nome da música para pesquisar no Spotify."
    try:
        from spotify_api import SpotifyClient, SpotifyAPIError
        client = SpotifyClient()
        if not client.configured:
            return False, "Spotify ainda não está configurado. Rode configurar_spotify_api.bat primeiro."
        client.token(interactive=False)
        item = client.search_track(q)
    except Exception as exc:
        return False, f"Não consegui pesquisar essa música no Spotify: {exc}"
    if not item:
        return False, f"Não encontrei {q} no catálogo do Spotify."
    uri = str(item.get("uri") or "")
    name = str(item.get("name") or q)
    artists = ", ".join(str(a.get("name") or "") for a in (item.get("artists") or []) if a.get("name"))
    if not uri:
        return False, f"Encontrei {name}, mas o Spotify não retornou a URI da faixa."

    online, h = wait_extension(launch=True)
    if not online:
        return False, (
            "O Spotify Bridge não apareceu dentro do Spotify. "
            "Rode configurar_spotify_bridge.bat e reinicie o Spotify Desktop."
        )
    ok, result = command("play_uri", {"uri": uri}, timeout=8.0)
    if not ok:
        return False, f"Encontrei {name}, mas o Spotify Bridge não conseguiu iniciar a faixa: {result.get('error','erro desconhecido')}"

    # O próprio resultado da extensão traz o estado logo após playUri.
    status = result.get("status") or {}
    got_uri = status.get("uri")
    verified = bool(status.get("playing")) and (not got_uri or got_uri == uri)
    _log("play_query", query=q, uri=uri, name=name, artists=artists, verified=verified, status=status)
    who = f" de {artists}" if artists else ""
    return True, f"Tocando {name}{who} no Spotify."


def status():
    ok, body = command("status", launch_if_needed=False)
    return ok, body
