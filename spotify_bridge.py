"""Bridge HTTP local (127.0.0.1) entre o V e a extensao Spicetify do Spotify.

Seguranca:
- O token do bridge fica em ``config/spotify_bridge_token.dat`` protegido com
  DPAPI (secure_store). O antigo ``.txt`` em texto puro e lido apenas para
  migracao e removido assim que a gravacao protegida funciona. Sem DPAPI o
  token NAO e gravado em claro (vale apenas para a execucao atual).
- A extensao instalada (``%APPDATA%\\spicetify\\Extensions\\vSpotifyBridge.js``)
  NECESSARIAMENTE contem o token em texto: o Spicetify nao tem um cofre de
  segredos acessivel ao JS. Por isso o configurador restringe as permissoes
  do arquivo e deve ser rodado de novo para ROTACIONAR o token se o JS vazar.
- Token de requisicao vem no header ``X-Bridge-Token`` (query so no handshake
  /health e /heartbeat, por compatibilidade com extensao antiga). CORS e
  restrito as origens da extensao/Spotify.
"""

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
from urllib.parse import parse_qs, urlparse

from secure_store import SecureStoreError, protect_text, unprotect_text
from vlog import get_logger

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config" / "default.json"
# Token protegido por DPAPI (formato atual). O .txt legado e so para migracao.
TOKEN_FILE = BASE / "config" / "spotify_bridge_token.dat"
LEGACY_TOKEN_FILE = BASE / "config" / "spotify_bridge_token.txt"
TOKEN_PROTECT = "dpapi"
TOKEN_SCHEME = "windows-dpapi-user"
LOG_DIR = BASE / "logs"
LOG_FILE = LOG_DIR / "spotify_bridge.log"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766

# Token do bridge: sempre por header. A query string so e aceita no handshake
# (/health e /heartbeat), porque era assim que a extensao antiga se anunciava;
# nunca em /next, /command ou /result (evita token em log/historico/Referer).
TOKEN_HEADER = "X-Bridge-Token"
CLIENT_HEADER = "X-Bridge-Client"
HANDSHAKE_PATHS = frozenset({"/health", "/heartbeat"})

# Origens permitidas no CORS: a extensao (chrome-extension://) e a origem do
# proprio Spotify Desktop, onde a extensao Spicetify executa o fetch.
ORIGIN_PREFIXES = ("chrome-extension://", "moz-extension://", "safari-web-extension://")
SPOTIFY_ORIGIN_SUFFIXES = ("spotify.com",)

# Tempo maximo que um comando entregue a um cliente fica "em andamento".
COMMAND_LEASE_SECONDS = 10.0

_commands: queue.Queue = queue.Queue()
_waiters: dict[str, dict] = {}
_waiters_lock = threading.Lock()
_last_seen = {"extension": 0.0, "last_status": None, "legacy_query": 0.0}
_server_thread: threading.Thread | None = None
_server = None
_inflight: dict | None = None
_inflight_lock = threading.Lock()

log = get_logger(__name__)


def _log(event: str, **data):
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.time(), "event": event, **data}
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _cfg():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data.get("spotify_bridge", {}) or {}


def _host_port():
    cfg = _cfg()
    return str(cfg.get("host") or DEFAULT_HOST), int(cfg.get("port") or DEFAULT_PORT)


def _allowed_origin(origin: str) -> str:
    origin = str(origin or "").strip().rstrip("/")
    if not origin:
        return ""
    low = origin.lower()
    if any(low.startswith(prefix) for prefix in ORIGIN_PREFIXES):
        return origin
    if low.startswith("https://"):
        try:
            host = (urlparse(low).hostname or "").strip()
        except ValueError:
            host = ""
        if host and any(host == s or host.endswith("." + s) for s in SPOTIFY_ORIGIN_SUFFIXES):
            return origin
    return ""


def _client_key(handler) -> str:
    """Identidade best-effort do cliente HTTP (extensao/aba/processo)."""
    for header in (CLIENT_HEADER, "Origin"):
        value = str(handler.headers.get(header) or "").strip()
        if value:
            return value[:200]
    return "local"


def _inflight_snapshot() -> dict | None:
    global _inflight
    with _inflight_lock:
        current = _inflight
        if current and float(current.get("deadline", 0)) <= time.time():
            _inflight = None
            current = None
        return dict(current) if current else None


def _claim_inflight(cmd: dict, client: str) -> None:
    global _inflight
    with _inflight_lock:
        _inflight = {
            "id": str(cmd.get("id", "")),
            "client": client,
            "action": str(cmd.get("action", "")),
            "deadline": time.time() + COMMAND_LEASE_SECONDS,
        }


def _release_inflight(command_id: str | None = None) -> None:
    global _inflight
    with _inflight_lock:
        if _inflight and (command_id is None or _inflight.get("id") == command_id):
            _inflight = None


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


def _read_secure_token() -> str | None:
    """Le o token do bridge protegido por DPAPI (formato atual do .dat)."""
    try:
        if not TOKEN_FILE.exists():
            return None
        payload = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("bridge: nao foi possivel ler o token protegido: %s", type(exc).__name__)
        return None
    if not isinstance(payload, dict):
        log.warning("bridge: token protegido em formato inesperado; sera ignorado")
        return None
    if str(payload.get("protect") or "").strip().lower() != TOKEN_PROTECT:
        token = str(payload.get("token") or "").strip()
        if token:
            log.warning("bridge: token em formato legado dentro do .dat; sera migrado")
            return token
        return None
    try:
        token = unprotect_text(str(payload.get("data") or ""), "V Spotify Bridge Token").strip()
    except SecureStoreError as exc:
        log.warning("bridge: falha ao desproteger o token do bridge: %s", type(exc).__name__)
        return None
    return token or None


def _read_legacy_token() -> str | None:
    """Le o token legado em texto puro (config/spotify_bridge_token.txt)."""
    try:
        if not LEGACY_TOKEN_FILE.exists():
            return None
        token = LEGACY_TOKEN_FILE.read_text(encoding="utf-8").strip()
        return token or None
    except Exception as exc:
        log.warning("bridge: falha ao ler o token legado .txt: %s", type(exc).__name__)
        return None


def _write_secure_token(token: str) -> None:
    """Grava o token protegido por DPAPI de forma atomica (levanta SecureStoreError)."""
    data = protect_text(token, "V Spotify Bridge Token")
    payload = {
        "version": 1,
        "protect": TOKEN_PROTECT,
        "scheme": TOKEN_SCHEME,
        "data": data,
    }
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_FILE.with_suffix(TOKEN_FILE.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(TOKEN_FILE)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def _remove_legacy_token() -> None:
    """Remove o .txt legado depois de migrar o token para DPAPI."""
    try:
        if LEGACY_TOKEN_FILE.exists():
            LEGACY_TOKEN_FILE.unlink()
            log.info("bridge: token legado em texto puro removido apos migrar para DPAPI")
            _log("legacy_token_migrated")
    except OSError as exc:
        log.warning("bridge: nao foi possivel remover o token legado .txt: %s", type(exc).__name__)


def _persist_token(token: str) -> bool:
    """Tenta gravar o token protegido; nunca grava em texto puro."""
    try:
        _write_secure_token(token)
        return True
    except SecureStoreError as exc:
        log.warning(
            "bridge: nao foi possivel proteger o token do bridge com DPAPI: %s",
            type(exc).__name__,
        )
        return False
    except Exception as exc:  # disco cheio/sem permissao: nao pode gravar em claro
        log.warning("bridge: falha ao gravar token protegido: %s", type(exc).__name__)
        return False


def save_token(token: str) -> str:
    """Salva/rotaciona o token do bridge com DPAPI (usado pelo configurador).

    Levanta RuntimeError com mensagem clara se o DPAPI nao estiver disponivel:
    o token NUNCA e gravado em texto puro.
    """
    token = str(token or "").strip()
    if not token:
        raise ValueError("Token do bridge vazio.")
    try:
        _write_secure_token(token)
    except SecureStoreError as exc:
        log.warning("bridge: falha ao salvar token do bridge com DPAPI: %s", type(exc).__name__)
        raise RuntimeError(
            "Nao foi possivel salvar o token do Spotify Bridge com seguranca: o DPAPI "
            "do Windows nao esta disponivel. O token NAO foi gravado em texto puro. "
            "Instale/reinstale o pywin32 no .venv e tente novamente."
        ) from exc
    _remove_legacy_token()
    return token


def ensure_token() -> str:
    """Devolve o token do bridge, migrando formatos antigos quando possivel.

    Ordem: .dat protegido -> .txt legado (migra) -> token da extensao ja
    instalada (compat de upgrade) -> token novo. Se o DPAPI falhar, o token
    vale apenas para esta execucao (nunca e gravado em claro).
    """
    token = _read_secure_token()
    if token:
        if LEGACY_TOKEN_FILE.exists():
            # .dat novo ja existe: limpa a copia em texto puro.
            _remove_legacy_token()
        return token
    legacy = _read_legacy_token()
    if legacy:
        if _persist_token(legacy):
            _remove_legacy_token()
        else:
            log.warning(
                "bridge: token legado .txt mantido (DPAPI indisponivel); migre depois "
                "com configurar_spotify_bridge.bat"
            )
        return legacy
    # Se o protótipo já instalou a extensão, reutiliza o token para evitar
    # incompatibilidade enquanto o usuário migra para o V integrado.
    installed = _token_from_installed_extension()
    if installed:
        _persist_token(installed)
        return installed
    token = secrets.token_urlsafe(32)
    if not _persist_token(token):
        log.warning(
            "bridge: token efemero nesta execucao (nao gravado). Rode "
            "configurar_spotify_bridge.bat para instalar a extensao com um token persistente."
        )
    return token


def _token_from_request(handler) -> str:
    """Token por header (preferido); query apenas nos paths de handshake."""
    header_token = str(handler.headers.get(TOKEN_HEADER) or "").strip()
    if header_token:
        return header_token
    parsed = urlparse(handler.path)
    if parsed.path not in HANDSHAKE_PATHS:
        return ""
    query = parse_qs(parsed.query)
    return str((query.get("token") or [""])[0]).strip()


def _legacy_query_recent(seconds: float = 120.0) -> bool:
    seen = float(_last_seen.get("legacy_query") or 0)
    return bool(seen) and (time.time() - seen) <= seconds


def _authorized(handler) -> bool:
    supplied = _token_from_request(handler)
    expected = ensure_token()
    if not supplied or not expected:
        return False
    try:
        ok = secrets.compare_digest(supplied, expected)
    except Exception:
        return False
    if ok and not str(handler.headers.get(TOKEN_HEADER) or "").strip():
        # Autenticou via query string: extensao antiga (protocolo legado).
        _last_seen["legacy_query"] = time.time()
        _log("legacy_query_auth", path=urlparse(handler.path).path)
    return ok


class _Handler(BaseHTTPRequestHandler):
    server_version = "VSpotifyBridge/1.1"

    def _cors(self):
        # Reflete apenas a origem da extensao (ou do Spotify Desktop, onde a
        # extensao roda). Nunca "*": pagina local nenhuma le a resposta.
        origin = _allowed_origin(self.headers.get("Origin"))
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header(
            "Access-Control-Allow-Headers",
            f"Content-Type, {TOKEN_HEADER}, {CLIENT_HEADER}",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _no_content(self, code=204):
        self.send_response(code)
        self._cors()
        self.end_headers()

    def _body_json(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _poll_command(self):
        """Entrega um comando pendente a UM cliente, sem permitir roubo.

        Enquanto um comando entregue nao retorna em /result (ou enquanto a
        lease nao expira), qualquer novo poll — de outro cliente ou nao —
        recebe 409 em vez de retirar/sobrescrever o comando em andamento.
        """
        client = _client_key(self)
        inflight = _inflight_snapshot()
        if inflight:
            same_client = inflight.get("client") == client
            log.warning(
                "bridge: poll recusado; comando %s em andamento (mesmo_cliente=%s)",
                inflight.get("id"),
                same_client,
            )
            _log(
                "poll_refused",
                reason="command_in_progress",
                client=client,
                command_id=inflight.get("id"),
                same_client=same_client,
            )
            self._json(409, {
                "ok": False,
                "error": "command_in_progress",
                "id": inflight.get("id"),
            })
            return
        _last_seen["extension"] = time.time()
        try:
            cmd = _commands.get(timeout=0.25)
        except queue.Empty:
            self._no_content()
            return
        _claim_inflight(cmd, client)
        self._json(200, cmd)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            age = None if not _last_seen["extension"] else round(time.time() - _last_seen["extension"], 2)
            self._json(200, {
                "ok": True,
                "bridge": "online",
                "extension_seen": bool(_last_seen["extension"]),
                "extension_age_s": age,
                "last_status": _last_seen["last_status"],
                "legacy_query_token": _legacy_query_recent(),
                "token_storage": "dpapi" if TOKEN_FILE.exists() else "ephemeral",
                "token_notice": (
                    "O token do bridge tambem fica embutido no JS da extensao "
                    "(%APPDATA%\\spicetify\\Extensions\\vSpotifyBridge.js). "
                    "Se esse arquivo vazar, rode configurar_spotify_bridge.bat "
                    "para gerar um token novo."
                ),
            })
            return
        if not _authorized(self):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        if path in ("/next", "/previous"):
            self._poll_command()
            return
        self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if not _authorized(self):
            self._json(403, {"ok": False, "error": "forbidden"})
            return
        try:
            body = self._body_json()
        except Exception:
            self._json(400, {"ok": False, "error": "invalid_json"})
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
            _release_inflight(cid)
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
    data = None if obj is None else json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(_url(path), data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        # Token sempre por header; nunca na query string (evita vazar em log,
        # historico de proxy ou cabecalho Referer).
        req.add_header(TOKEN_HEADER, ensure_token())
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
    if code == 504 and _legacy_query_recent():
        # Extensao antiga autenticando por query string: o servidor recusa o
        # token fora do handshake, entao o comando nunca e executado. Falhe
        # alto e claro em vez de esperar em silencio.
        log.warning("bridge: extensao antiga (token na query); pedido nao executado")
        body = {
            "ok": False,
            "error": "Extensão Spotify desatualizada: rode configurar_spotify_bridge.bat "
                     "e reinicie o Spotify Desktop.",
        }
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
