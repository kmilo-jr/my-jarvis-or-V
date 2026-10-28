from __future__ import annotations

import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse


REMOTE_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#05070b">
<title>V Remote</title>
<style>
:root{--bg:#05070b;--panel:#0b0e14;--panel2:#0f131b;--line:#222936;--text:#eef2f7;--muted:#8e99aa;--red:#ff4e4e;--red2:#8b2027}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 50% 20%,#151018 0,#07090d 35%,#040609 75%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;min-height:100vh}
.wrap{max-width:650px;margin:0 auto;padding:18px 16px 32px}.top{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}.brand{font-size:22px;letter-spacing:.22em;font-weight:700}.dot{width:8px;height:8px;border-radius:50%;background:var(--red);box-shadow:0 0 14px var(--red);display:inline-block;margin-right:8px}.status{font-size:12px;color:var(--muted)}
.card{background:linear-gradient(180deg,rgba(18,22,30,.92),rgba(9,12,17,.92));border:1px solid var(--line);border-radius:18px;padding:16px;margin-bottom:12px;box-shadow:0 14px 40px rgba(0,0,0,.25)}
.hero{padding:22px 18px;text-align:center}.face{width:92px;height:92px;margin:4px auto 13px;position:relative;filter:drop-shadow(0 0 14px rgba(255,55,55,.25))}.face:before,.face:after{content:"";position:absolute;background:var(--red);box-shadow:0 0 12px rgba(255,50,50,.6);clip-path:polygon(0 0,100% 42%,92% 100%,12% 58%)}.face:before{width:40px;height:17px;left:3px;top:20px;transform:rotate(17deg)}.face:after{width:40px;height:17px;right:3px;top:20px;transform:scaleX(-1) rotate(17deg)}.jaw{position:absolute;left:14px;right:14px;bottom:7px;height:45px;background:var(--red);clip-path:polygon(0 0,32% 36%,42% 67%,58% 67%,68% 36%,100% 0,78% 100%,22% 100%);box-shadow:0 0 16px rgba(255,50,50,.45)}
.state{font-size:20px;letter-spacing:.15em;margin-top:6px}.sub{color:var(--muted);font-size:12px;margin-top:6px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}.btn{appearance:none;border:1px solid #2a313d;background:#0c1016;color:#e8edf4;border-radius:14px;padding:14px 12px;font-size:14px;font-weight:650;min-height:50px}.btn:active{transform:scale(.985);background:#131821}.btn.red{border-color:#5a242a;background:linear-gradient(180deg,#341217,#1b0d10);color:#fff}.btn.wide{grid-column:1/-1}.section{font-size:12px;letter-spacing:.18em;color:#aeb7c5;margin:0 0 10px}.cmdrow{display:flex;gap:9px}.cmd{flex:1;border:1px solid #2a313d;background:#080b10;color:#fff;border-radius:14px;padding:14px 13px;font-size:15px;outline:none}.cmd:focus{border-color:#5f3136;box-shadow:0 0 0 3px rgba(255,70,70,.06)}.send{width:58px;border-radius:14px;border:1px solid #61272e;background:#2b1014;color:#fff;font-size:20px}.mini{font-size:11px;color:#7f8998;margin-top:10px;line-height:1.45}.pair{max-width:430px;margin:10vh auto 0}.pin{width:100%;text-align:center;letter-spacing:.4em;font-size:24px;border:1px solid #303744;background:#080b10;color:#fff;padding:16px;border-radius:14px;outline:none}.error{color:#ff8080;font-size:12px;min-height:18px;margin-top:8px}.hidden{display:none}.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#151922;border:1px solid #262d39;color:#aeb7c5;font-size:11px}.row{display:flex;gap:8px;align-items:center;justify-content:center;flex-wrap:wrap}.field{width:100%;border:1px solid #2a313d;background:#080b10;color:#fff;border-radius:12px;padding:11px 12px;font-size:14px;outline:none}.field:focus{border-color:#5f3136}.mobileAction{border:1px solid #412027;background:#120b0e;border-radius:13px;padding:11px;margin-top:9px;text-align:left}.mobileAction b{display:block;font-size:13px;margin-bottom:4px}.notification{border-left:2px solid #7e2d36;padding:7px 9px;margin:7px 0;background:#0a0d12;border-radius:7px;text-align:left}.notification .app{font-size:10px;color:#ff7f86;letter-spacing:.12em}.notification .body{font-size:12px;color:#cbd3dc;margin-top:3px}.mono{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.pill{display:inline-block;background:#111824;border:1px solid #273142;color:#cdd5de;border-radius:10px;padding:8px 10px;font-size:11px}.warn{color:#ffb4b4}
</style>
</head>
<body>
<div class="wrap">
  <div id="pairView" class="pair card">
    <div class="top"><div class="brand">V REMOTE</div><div class="status"><span class="dot"></span><span id="pairMode">LOCAL</span></div></div>
    <p class="sub">Digite o PIN mostrado no computador para parear este celular.</p>
    <input id="pin" class="pin" inputmode="numeric" maxlength="6" placeholder="000000">
    <button class="btn red wide" style="width:100%;margin-top:12px" onclick="pair()">PAREAR</button>
    <div id="pairError" class="error"></div>
    <div id="pairHint" class="mini">O controle remoto desta versão funciona na mesma rede local do V.</div>
  </div>

  <div id="remoteView" class="hidden">
    <div class="top"><div class="brand">V REMOTE</div><div class="status"><span class="dot"></span><span id="onlineText">ONLINE</span></div></div>
    <div class="card hero">
      <div class="face"><div class="jaw"></div></div>
      <div id="vState" class="state">READY</div>
      <div class="row" style="margin-top:10px"><span id="uiMode" class="badge">UI —</span><span id="voiceState" class="badge">VOICE —</span></div>
    </div>

    <div class="card">
      <div class="section">STATUS DO PC</div>
      <div class="row"><span id="cpuState" class="badge">CPU —</span><span id="ramState" class="badge">RAM —</span><span id="diskState" class="badge">DISCO —</span></div>
    </div>

    <div class="card">
      <div class="section">COMANDO</div>
      <div class="cmdrow"><input id="command" class="cmd" placeholder="Fale com o V..." onkeydown="if(event.key==='Enter')sendCommand()"><button class="send" onclick="sendCommand()">➤</button></div>
    </div>

    <div class="card">
      <div class="section">MÍDIA</div>
      <div class="grid">
        <button class="btn" onclick="cmd('volte a música no Spotify')">⏮ ANTERIOR</button>
        <button class="btn" onclick="cmd('pause a música no Spotify')">⏯ PAUSAR</button>
        <button class="btn" onclick="cmd('continue a música no Spotify')">▶ CONTINUAR</button>
        <button class="btn" onclick="cmd('pule para a próxima música no Spotify')">⏭ PRÓXIMA</button>
      </div>
    </div>

    <div class="card">
      <div class="section">CONTROLE DO PC</div>
      <div class="grid">
        <button class="btn" onclick="action('volume_down')">🔉 VOLUME −</button>
        <button class="btn" onclick="action('volume_up')">🔊 VOLUME +</button>
        <button class="btn" onclick="action('volume_mute')">🔇 MUDO</button>
        <button class="btn" onclick="action('media_play_pause')">⏯ PLAY / PAUSE</button>
        <button class="btn" onclick="action('open_spotify')">♫ SPOTIFY</button>
        <button class="btn" onclick="action('open_youtube')">▶ YOUTUBE</button>
        <button class="btn wide" onclick="action('open_browser')">◉ NAVEGADOR</button>
      </div>
    </div>

    <div class="card">
      <div class="section">V MOBILE • IPHONE</div>
      <div class="grid">
        <input id="alarmTime" class="field" type="time" value="07:00">
        <button class="btn" onclick="createAlarm()">⏰ CRIAR ALARME</button>
        <input id="reminderText" class="field wide" placeholder="Texto do lembrete">
        <input id="reminderDue" class="field wide" type="datetime-local">
        <button class="btn red wide" onclick="createReminder()">◷ CRIAR LEMBRETE</button>
      </div>
      <div id="mobilePending" class="mini">Nenhuma ação pendente para o iPhone.</div>
      <div class="mini">Alarmes e lembretes usam o Atalho “V Mobile”. O iPhone pede um toque para abrir o Atalho.</div>
    </div>

    <div class="card">
      <div class="section">NOTIFICAÇÕES DO IPHONE</div>
      <div id="notificationStatus" class="mini">Aguardando ponte de notificações...</div>
      <div id="notificationList"></div>
    </div>

    <div class="card">
      <div class="section">SISTEMA / V</div>
      <div class="grid">
        <button id="wakeBtn" class="btn red wide" onclick="action('wake_pc')">⏻ LIGAR PC (WOL)</button>
        <button class="btn" onclick="action('switch_ui')">⇄ TROCAR INTERFACE</button>
        <button class="btn" onclick="action('toggle_voice')">◉ MICROFONE</button>
        <button class="btn wide" onclick="cmd('me mostre as principais notícias de hoje')">▤ NOTÍCIAS</button>
        <button class="btn" onclick="confirmAction('lock_pc','Bloquear o computador?')">▣ BLOQUEAR</button>
        <button class="btn" onclick="confirmAction('restart_pc','Reiniciar o computador?')">↻ REINICIAR</button>
        <button class="btn red wide" onclick="confirmAction('shutdown_pc','Desligar o computador?')">⏻ DESLIGAR PC</button>
      </div>
    </div>
    <div class="mini">V Remote v1.6 • controle avançado + V Mobile • mesmo Wi-Fi/LAN</div>
  </div>
</div>
<script>
let REMOTE_META={};
async function api(path, opts={}){const r=await fetch(path,{...opts,headers:{'Content-Type':'application/json',...(opts.headers||{})}});let j={};try{j=await r.json()}catch(e){}if(r.status===401){showPair();throw new Error('not paired')}if(!r.ok)throw new Error(j.error||'Falha');return j}
function showPair(){document.getElementById('pairView').classList.remove('hidden');document.getElementById('remoteView').classList.add('hidden')}
function showRemote(){document.getElementById('pairView').classList.add('hidden');document.getElementById('remoteView').classList.remove('hidden')}
async function loadMeta(){try{REMOTE_META=await api('/api/meta');const hint=document.getElementById('pairHint');if(REMOTE_META.local_url){hint.textContent='Controle remoto somente na mesma rede Wi-Fi/LAN. Abra '+REMOTE_META.local_url+' no celular.'}}catch(e){}}
async function pair(){const pin=document.getElementById('pin').value.trim();const e=document.getElementById('pairError');e.textContent='';try{await api('/api/pair',{method:'POST',body:JSON.stringify({pin})});showRemote();refresh()}catch(err){e.textContent='PIN incorreto ou limite de tentativas atingido.'}}
async function cmd(text){try{await api('/api/command',{method:'POST',body:JSON.stringify({text})})}catch(e){}}
function sendCommand(){const i=document.getElementById('command');const t=i.value.trim();if(!t)return;cmd(t);i.value=''}
async function action(name){try{await api('/api/action',{method:'POST',body:JSON.stringify({name})})}catch(e){}}
function confirmAction(name,label){if(confirm(label))action(name)}
async function createAlarm(){const time=document.getElementById('alarmTime').value;if(!time)return;try{const r=await api('/api/mobile/create',{method:'POST',body:JSON.stringify({kind:'alarm',time})});renderPending([r.action],true)}catch(e){alert('Não consegui preparar o alarme.')}}
async function createReminder(){const title=document.getElementById('reminderText').value.trim();const due=document.getElementById('reminderDue').value;if(!title||!due){alert('Informe o texto e a data/hora do lembrete.');return}try{const r=await api('/api/mobile/create',{method:'POST',body:JSON.stringify({kind:'reminder',title,due})});renderPending([r.action],true)}catch(e){alert('Não consegui preparar o lembrete.')}}
async function runMobile(id,url){try{await api('/api/mobile/ack',{method:'POST',body:JSON.stringify({id,status:'launched'})})}catch(e){}window.location.href=url;setTimeout(refreshMobile,800)}
function renderPending(actions,prepend=false){const box=document.getElementById('mobilePending');if(!actions||!actions.length){box.innerHTML='Nenhuma ação pendente para o iPhone.';return}box.innerHTML=actions.map(a=>'<div class="mobileAction"><b>'+a.title+'</b><div class="mini">'+(a.subtitle||'')+'</div><button class="btn red wide" style="margin-top:8px" onclick="runMobile(\''+a.id+'\',\''+a.shortcut_url+'\')">ABRIR NO IPHONE</button></div>').join('')}
function renderNotifications(data){const backend=(data&&data.backend)||{};const status=document.getElementById('notificationStatus');status.textContent=backend.message||'Aguardando ponte de notificações...';if(backend.error){status.innerHTML+='<br><span class="warn">'+backend.error+'</span>'}const list=document.getElementById('notificationList');const items=(data&&data.notifications)||[];list.innerHTML=items.map(n=>'<div class="notification"><div class="app">'+n.app+'</div><div><b>'+(n.title||'Sem título')+'</b></div><div class="body">'+(n.body||'')+'</div></div>').join('')}
async function refreshMobile(){try{const m=await api('/api/mobile');renderPending(m.actions||[]);renderNotifications(m)}catch(e){}}
async function refresh(){try{const s=await api('/api/status');showRemote();document.getElementById('vState').textContent=s.state||'READY';document.getElementById('uiMode').textContent='UI '+(s.mode||'—').toUpperCase();document.getElementById('voiceState').textContent='VOICE '+(s.voice_enabled?'ON':'OFF');document.getElementById('onlineText').textContent=s.busy?'OCUPADO':'ONLINE';document.getElementById('cpuState').textContent='CPU '+(s.cpu_percent??'—')+'%';document.getElementById('ramState').textContent='RAM '+(s.ram_percent??'—')+'%';document.getElementById('diskState').textContent='DISCO '+(s.disk_percent??'—')+'%';const wb=document.getElementById('wakeBtn');if(wb){wb.disabled=!s.wol_configured;wb.textContent=s.wol_configured?'⏻ ENVIAR WAKE-ON-LAN':'⏻ WOL NÃO CONFIGURADO'}await refreshMobile()}catch(e){}}
loadMeta(); refresh(); setInterval(refresh,2600);
</script>
</body>
</html>"""


def _local_ipv4() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


class VRemoteServer:
    def __init__(
        self,
        command_callback: Callable[[str], None],
        action_callback: Callable[[str], None],
        status_provider: Callable[[], dict],
        wake_callback: Callable[[], None] | None = None,
        port: int = 8765,
    ):
        self.command_callback = command_callback
        self.action_callback = action_callback
        self.status_provider = status_provider
        self.wake_callback = wake_callback
        self.port = int(port)
        self.pin = f"{secrets.randbelow(1_000_000):06d}"
        self.sessions: set[str] = set()
        self._attempts: dict[str, list[float]] = {}
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.local_ip = _local_ipv4()

    @property
    def url(self) -> str:
        return f"http://{self.local_ip}:{self.port}"

    def _is_local_client(self, host: str) -> bool:
        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except Exception:
            return False

    def _pair_allowed(self, host: str) -> bool:
        now = time.time()
        window = [t for t in self._attempts.get(host, []) if now - t < 60]
        self._attempts[host] = window
        return len(window) < 6

    def _note_pair_attempt(self, host: str):
        self._attempts.setdefault(host, []).append(time.time())

    def start(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "VRemote/1.6"

            def log_message(self, fmt, *args):
                return

            def _json(self, status: int, payload: dict, extra_headers: dict | None = None):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                if extra_headers:
                    for k, v in extra_headers.items():
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict:
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 8192)
                    if length <= 0:
                        return {}
                    return json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    return {}

            def _session(self) -> str:
                raw = self.headers.get("Cookie", "")
                if not raw:
                    return ""
                cookie = SimpleCookie()
                try:
                    cookie.load(raw)
                    return cookie.get("vremote").value if cookie.get("vremote") else ""
                except Exception:
                    return ""

            def _authorized(self) -> bool:
                token = self._session()
                return bool(token and token in parent.sessions)

            def _client_is_local(self) -> bool:
                return parent._is_local_client(self.client_address[0])

            def _access_guard(self) -> bool:
                if self._client_is_local():
                    return True
                self._json(HTTPStatus.FORBIDDEN, {"error": "local network only"})
                return False

            def do_GET(self):
                if not self._access_guard():
                    return
                path = urlparse(self.path).path
                if path == "/":
                    body = REMOTE_HTML.encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Frame-Options", "DENY")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path == "/api/meta":
                    self._json(HTTPStatus.OK, {
                        "local_url": parent.url,
                        "access_mode": "local",
                    })
                    return
                if path == "/api/status":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "pair first"})
                        return
                    try:
                        base = dict(parent.status_provider() or {})
                    except Exception:
                        base = {"state": "READY", "mode": "unknown", "voice_enabled": False, "busy": False}
                    self._json(HTTPStatus.OK, base)
                    return
                if path == "/api/mobile":
                    if not self._authorized():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "pair first"})
                        return
                    try:
                        import mobile_bridge
                        self._json(HTTPStatus.OK, {
                            "actions": mobile_bridge.pending_actions(8),
                            "notifications": mobile_bridge.recent_notifications(8),
                            "backend": mobile_bridge.notification_backend_status(),
                        })
                    except Exception as exc:
                        self._json(HTTPStatus.OK, {"actions": [], "notifications": [], "backend": {"automatic": False, "message": type(exc).__name__}})
                    return
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

            def do_POST(self):
                if not self._access_guard():
                    return
                path = urlparse(self.path).path
                data = self._read_json()
                if path == "/api/pair":
                    host = self.client_address[0]
                    if not parent._pair_allowed(host):
                        self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "too many attempts"})
                        return
                    parent._note_pair_attempt(host)
                    supplied = str(data.get("pin", ""))
                    if not hmac.compare_digest(supplied, parent.pin):
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "invalid pin"})
                        return
                    token = secrets.token_urlsafe(32)
                    parent.sessions.add(token)
                    headers = {"Set-Cookie": f"vremote={token}; HttpOnly; SameSite=Strict; Path=/"}
                    self._json(HTTPStatus.OK, {"ok": True}, headers)
                    return

                if not self._authorized():
                    self._json(HTTPStatus.UNAUTHORIZED, {"error": "pair first"})
                    return

                if path == "/api/command":
                    text = str(data.get("text", "")).strip()[:500]
                    if not text:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "empty command"})
                        return
                    try:
                        parent.command_callback(text)
                        self._json(HTTPStatus.OK, {"ok": True})
                    except Exception as exc:
                        self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__})
                    return

                if path == "/api/action":
                    name = str(data.get("name", "")).strip().lower()
                    if name not in {"switch_ui", "toggle_voice", "wake_pc", "volume_up", "volume_down", "volume_mute", "media_play_pause", "media_next", "media_previous", "open_spotify", "open_youtube", "open_browser", "lock_pc", "restart_pc", "shutdown_pc", "cancel_shutdown"}:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": "unknown action"})
                        return
                    try:
                        if name == "wake_pc":
                            if parent.wake_callback is None:
                                self._json(HTTPStatus.BAD_REQUEST, {"error": "wol not configured"})
                                return
                            parent.wake_callback()
                        else:
                            parent.action_callback(name)
                        self._json(HTTPStatus.OK, {"ok": True})
                    except Exception as exc:
                        self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__})
                    return

                if path == "/api/mobile/create":
                    try:
                        import mobile_bridge
                        kind = str(data.get("kind", "")).strip().lower()
                        if kind == "alarm":
                            action = mobile_bridge.queue_alarm(time_text=str(data.get("time", "")), label=str(data.get("label", "") or "Alarme do V"))
                        elif kind == "reminder":
                            action = mobile_bridge.queue_reminder(title=str(data.get("title", "")), due=str(data.get("due", "")))
                        else:
                            self._json(HTTPStatus.BAD_REQUEST, {"error": "unknown mobile action"}); return
                        self._json(HTTPStatus.OK, {"ok": True, "action": action})
                    except ValueError as exc:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    except Exception as exc:
                        self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__})
                    return

                if path == "/api/mobile/ack":
                    try:
                        import mobile_bridge
                        ok = mobile_bridge.ack_action(str(data.get("id", "")), str(data.get("status", "launched")))
                        self._json(HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND, {"ok": ok})
                    except Exception as exc:
                        self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__})
                    return

                if path == "/api/mobile/notification":
                    try:
                        import mobile_bridge
                        item = mobile_bridge.record_notification(str(data.get("app", "iPhone")), str(data.get("title", "")), str(data.get("body", "")), source=str(data.get("source", "relay")))
                        self._json(HTTPStatus.OK, {"ok": True, "notification": item})
                    except Exception as exc:
                        self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": type(exc).__name__})
                    return

                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="VRemoteServer", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
        self._httpd = None
        self._thread = None
        self.sessions.clear()
