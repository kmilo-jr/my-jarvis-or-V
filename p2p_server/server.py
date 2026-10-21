from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass, field

from aiohttp import WSMsgType, web


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


REMOTE_HTML = r'''<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#05070b"><title>V P2P Remote</title>
<style>
:root{--bg:#05070b;--panel:#0b0e14;--line:#222936;--text:#eef2f7;--muted:#8e99aa;--red:#ff4e4e}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 50% 16%,#171019 0,#07090d 36%,#040609 75%);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;min-height:100vh}.wrap{max-width:650px;margin:auto;padding:18px 16px 32px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.brand{font-size:21px;letter-spacing:.2em;font-weight:700}.status{font-size:11px;color:var(--muted)}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--red);box-shadow:0 0 14px var(--red);margin-right:7px}.card{background:linear-gradient(180deg,rgba(18,22,30,.94),rgba(9,12,17,.94));border:1px solid var(--line);border-radius:18px;padding:16px;margin-bottom:12px}.hero{text-align:center;padding:22px}.face{width:92px;height:92px;margin:2px auto 12px;position:relative;filter:drop-shadow(0 0 15px rgba(255,55,55,.25))}.face:before,.face:after{content:"";position:absolute;background:var(--red);box-shadow:0 0 12px rgba(255,50,50,.6);clip-path:polygon(0 0,100% 42%,92% 100%,12% 58%)}.face:before{width:40px;height:17px;left:3px;top:20px;transform:rotate(17deg)}.face:after{width:40px;height:17px;right:3px;top:20px;transform:scaleX(-1) rotate(17deg)}.jaw{position:absolute;left:14px;right:14px;bottom:7px;height:45px;background:var(--red);clip-path:polygon(0 0,32% 36%,42% 67%,58% 67%,68% 36%,100% 0,78% 100%,22% 100%)}.state{font-size:19px;letter-spacing:.14em}.sub,.mini{color:var(--muted);font-size:11px;line-height:1.45}.badge{display:inline-block;padding:5px 8px;border-radius:999px;background:#151922;border:1px solid #262d39;color:#b7c0cc;font-size:10px;margin:3px}.section{font-size:11px;letter-spacing:.18em;color:#aeb7c5;margin-bottom:10px}.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.btn{border:1px solid #2a313d;background:#0c1016;color:#e8edf4;border-radius:14px;padding:13px 10px;font-size:13px;font-weight:650;min-height:48px}.btn:active{transform:scale(.985)}.btn.red{border-color:#5a242a;background:linear-gradient(180deg,#341217,#1b0d10)}.wide{grid-column:1/-1}.field{width:100%;border:1px solid #2a313d;background:#080b10;color:#fff;border-radius:13px;padding:13px;outline:none}.cmdrow{display:flex;gap:8px}.cmd{flex:1}.send{width:56px}.hidden{display:none}.pair{max-width:430px;margin:12vh auto 0}.pin{text-align:center;font-size:24px;letter-spacing:.35em}.error{color:#ff9292;font-size:12px;min-height:18px;margin-top:8px}.row{display:flex;justify-content:center;gap:6px;flex-wrap:wrap}.ok{color:#9be0a5}.warn{color:#ffc48b}
</style></head><body><div class="wrap">
<div id="pair" class="card pair"><div class="top"><div class="brand">V P2P</div><div class="status"><span class="dot"></span><span id="net">CONECTANDO</span></div></div><p class="sub">Digite o PIN que aparece no V no computador.</p><input id="pin" class="field pin" inputmode="numeric" maxlength="6" placeholder="000000"><button class="btn red wide" style="width:100%;margin-top:10px" onclick="pairNow()">PAREAR</button><div id="err" class="error"></div><div class="mini">A conexão tenta WebRTC direto. Se a rede bloquear o P2P, os comandos passam pelo relay automaticamente.</div></div>
<div id="remote" class="hidden"><div class="top"><div class="brand">V REMOTE</div><div class="status"><span class="dot"></span><span id="online">ONLINE</span></div></div>
<div class="card hero"><div class="face"><div class="jaw"></div></div><div id="vstate" class="state">READY</div><div class="row"><span id="mode" class="badge">CONEXÃO —</span><span id="latency" class="badge">PING —</span><span id="voice" class="badge">VOICE —</span></div></div>
<div class="card"><div class="section">STATUS DO PC</div><div class="row"><span id="cpu" class="badge">CPU —</span><span id="ram" class="badge">RAM —</span><span id="disk" class="badge">DISCO —</span></div></div>
<div class="card"><div class="section">COMANDO</div><div class="cmdrow"><input id="command" class="field cmd" placeholder="Fale com o V..." onkeydown="if(event.key==='Enter')sendCommand()"><button class="btn send" onclick="sendCommand()">➤</button></div></div>
<div class="card"><div class="section">MÍDIA</div><div class="grid"><button class="btn" onclick="action('media_previous')">⏮ ANTERIOR</button><button class="btn" onclick="action('media_play_pause')">⏯ PLAY / PAUSE</button><button class="btn" onclick="action('media_next')">⏭ PRÓXIMA</button><button class="btn" onclick="action('volume_mute')">🔇 MUDO</button></div></div>
<div class="card"><div class="section">CONTROLE DO PC</div><div class="grid"><button class="btn" onclick="action('volume_down')">🔉 VOLUME −</button><button class="btn" onclick="action('volume_up')">🔊 VOLUME +</button><button class="btn" onclick="action('open_spotify')">♫ SPOTIFY</button><button class="btn" onclick="action('open_youtube')">▶ YOUTUBE</button><button class="btn wide" onclick="action('open_browser')">◉ NAVEGADOR</button></div></div>
<div class="card"><div class="section">V MOBILE</div><div class="grid"><input id="alarm" type="time" class="field" value="07:00"><button class="btn" onclick="alarm()">⏰ ALARME</button><input id="rtext" class="field wide" placeholder="Lembrete"><input id="rdue" type="datetime-local" class="field wide"><button class="btn red wide" onclick="reminder()">◷ CRIAR LEMBRETE</button></div></div>
<div class="card"><div class="section">SISTEMA / V</div><div class="grid"><button class="btn" onclick="action('switch_ui')">⇄ INTERFACE</button><button class="btn" onclick="action('toggle_voice')">◉ MICROFONE</button><button class="btn" onclick="confirmAct('lock_pc','Bloquear o PC?')">▣ BLOQUEAR</button><button class="btn" onclick="confirmAct('restart_pc','Reiniciar o PC?')">↻ REINICIAR</button><button class="btn red wide" onclick="confirmAct('shutdown_pc','Desligar o PC?')">⏻ DESLIGAR</button></div></div>
<div class="mini">V P2P Remote • WebRTC direto + relay automático</div></div></div>
<script>
const hash=new URLSearchParams(location.hash.slice(1));const ROOM=hash.get('room')||'';const TOKEN=hash.get('token')||'';let ws=null,pc=null,dc=null,paired=false,relayReady=false;const pending=new Map();
function wsURL(){return (location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws'}
function setMode(t){document.getElementById('mode').textContent='CONEXÃO '+t}
function connect(){if(!ROOM||!TOKEN){document.getElementById('err').textContent='Link inválido: room/token ausentes.';return}ws=new WebSocket(wsURL());ws.onopen=()=>{document.getElementById('net').textContent='ONLINE';ws.send(JSON.stringify({type:'register',role:'client',room:ROOM,token:TOKEN}))};ws.onclose=()=>{document.getElementById('net').textContent='RECONECTANDO';setMode('OFFLINE');setTimeout(connect,2500)};ws.onmessage=async e=>{let m={};try{m=JSON.parse(e.data)}catch(_){return}if(m.type==='error'){document.getElementById('err').textContent=m.error||'Erro';return}if(m.type==='pair_ok'){paired=true;relayReady=!!m.relay;document.getElementById('pair').classList.add('hidden');document.getElementById('remote').classList.remove('hidden');setMode(m.webrtc?'NEGOCIANDO':'RELAY');return}if(m.type==='pair_error'){document.getElementById('err').textContent=m.error||'PIN incorreto';return}if(m.type==='offer'){await onOffer(m.description);return}if(m.type==='p2p_unavailable'){setMode('RELAY');return}if(m.type==='host_status'){updateStatus(m.status||{});return}if(m.type==='host_offline'){setMode('PC OFFLINE');return}if(m.type==='relay_response'){handleResponse(m.request_id,m.result||{});return}}}
function pairNow(){const pin=document.getElementById('pin').value.trim();document.getElementById('err').textContent='';if(!ws||ws.readyState!==1){document.getElementById('err').textContent='Ainda conectando ao servidor.';return}ws.send(JSON.stringify({type:'pair_request',pin}))}
function waitIce(pc){if(pc.iceGatheringState==='complete')return Promise.resolve();return new Promise(resolve=>{const f=()=>{if(pc.iceGatheringState==='complete'){pc.removeEventListener('icegatheringstatechange',f);resolve()}};pc.addEventListener('icegatheringstatechange',f);setTimeout(resolve,8000)})}
async function onOffer(desc){try{if(pc)pc.close();pc=new RTCPeerConnection({iceServers:[{urls:['stun:stun.l.google.com:19302']}]});pc.ondatachannel=e=>{dc=e.channel;dc.onopen=()=>{setMode('P2P DIRETO');};dc.onclose=()=>{if(relayReady)setMode('RELAY')};dc.onmessage=e=>{let m={};try{m=JSON.parse(e.data)}catch(_){return}if(m.type==='status')updateStatus(m.status||{});if(m.type==='response')handleResponse(m.request_id,m.result||{})}};pc.onconnectionstatechange=()=>{if(['failed','disconnected','closed'].includes(pc.connectionState)&&relayReady)setMode('RELAY')};await pc.setRemoteDescription(desc);const ans=await pc.createAnswer();await pc.setLocalDescription(ans);await waitIce(pc);ws.send(JSON.stringify({type:'answer',description:{type:pc.localDescription.type,sdp:pc.localDescription.sdp}}))}catch(e){setMode('RELAY')}}
let req=0;function sendPayload(payload){if(!paired)return;const request_id=String(++req);payload.request_id=request_id;pending.set(request_id,performance.now());if(dc&&dc.readyState==='open'){dc.send(JSON.stringify(payload));return}if(ws&&ws.readyState===1&&relayReady){ws.send(JSON.stringify({type:'relay_request',request_id,payload}));setMode('RELAY')}}
function sendCommand(){const i=document.getElementById('command'),t=i.value.trim();if(!t)return;sendPayload({kind:'command',text:t});i.value=''}function action(name){sendPayload({kind:'action',name})}function confirmAct(n,t){if(confirm(t))action(n)}function alarm(){sendPayload({kind:'mobile_create',subtype:'alarm',time:document.getElementById('alarm').value,label:'Alarme do V'})}function reminder(){const title=document.getElementById('rtext').value.trim(),due=document.getElementById('rdue').value;if(!title||!due){alert('Preencha o lembrete e a data.');return}sendPayload({kind:'mobile_create',subtype:'reminder',title,due})}
function updateStatus(s){document.getElementById('vstate').textContent=s.state||'READY';document.getElementById('voice').textContent='VOICE '+(s.voice_enabled?'ON':'OFF');document.getElementById('cpu').textContent='CPU '+(s.cpu_percent??'—')+'%';document.getElementById('ram').textContent='RAM '+(s.ram_percent??'—')+'%';document.getElementById('disk').textContent='DISCO '+(s.disk_percent??'—')+'%';document.getElementById('online').textContent=s.busy?'OCUPADO':'ONLINE'}function handleResponse(id,r){if(pending.has(String(id))){const ms=Math.round(performance.now()-pending.get(String(id)));pending.delete(String(id));document.getElementById('latency').textContent='PING '+ms+' ms'}if(r&&r.error)console.warn(r.error)}
setInterval(()=>{if(paired)sendPayload({kind:'ping'})},5000);connect();
</script></body></html>'''


@dataclass
class Room:
    token_hash: str
    host: web.WebSocketResponse | None = None
    clients: dict[str, web.WebSocketResponse] = field(default_factory=dict)
    host_capabilities: dict = field(default_factory=dict)


ROOMS: dict[str, Room] = {}


async def index(_request: web.Request):
    return web.Response(text=REMOTE_HTML, content_type="text/html")


async def health(_request: web.Request):
    return web.json_response({"ok": True, "rooms": len(ROOMS)})


async def safe_send(ws: web.WebSocketResponse | None, obj: dict):
    if ws is not None and not ws.closed:
        try:
            await ws.send_str(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            pass


async def websocket_handler(request: web.Request):
    ws = web.WebSocketResponse(heartbeat=25, max_msg_size=1_000_000)
    await ws.prepare(request)
    role = room_name = client_id = ""
    room: Room | None = None
    try:
        first = await ws.receive(timeout=15)
        if first.type != WSMsgType.TEXT:
            await safe_send(ws, {"type": "error", "error": "registro ausente"})
            return ws
        try:
            reg = json.loads(first.data)
        except Exception:
            reg = {}
        if reg.get("type") != "register":
            await safe_send(ws, {"type": "error", "error": "registro inválido"})
            return ws
        role = str(reg.get("role", ""))
        room_name = str(reg.get("room", ""))[:80]
        token = str(reg.get("token", ""))
        if role not in {"host", "client"} or not room_name or len(token) < 20:
            await safe_send(ws, {"type": "error", "error": "credenciais inválidas"})
            return ws
        th = token_hash(token)
        if role == "host":
            room = ROOMS.get(room_name)
            if room is None:
                room = Room(token_hash=th)
                ROOMS[room_name] = room
            elif room.token_hash != th:
                await safe_send(ws, {"type": "error", "error": "token inválido"})
                return ws
            if room.host is not None and not room.host.closed:
                try:
                    await room.host.close(code=4001, message=b"new host")
                except Exception:
                    pass
            room.host = ws
            room.host_capabilities = dict(reg.get("capabilities") or {})
            await safe_send(ws, {"type": "registered", "role": "host"})
            for cid, cws in list(room.clients.items()):
                await safe_send(cws, {"type": "host_online", "capabilities": room.host_capabilities})
                await safe_send(ws, {"type": "client_joined", "client_id": cid})
        else:
            room = ROOMS.get(room_name)
            if room is None or room.token_hash != th:
                await safe_send(ws, {"type": "error", "error": "PC offline ou link inválido"})
                return ws
            client_id = secrets.token_urlsafe(8)
            room.clients[client_id] = ws
            await safe_send(ws, {"type": "registered", "role": "client", "client_id": client_id, "host_online": bool(room.host and not room.host.closed)})
            await safe_send(room.host, {"type": "client_joined", "client_id": client_id})

        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except Exception:
                continue
            kind = str(data.get("type", ""))
            if role == "client":
                if kind in {"pair_request", "answer", "relay_request"}:
                    if room.host is None or room.host.closed:
                        await safe_send(ws, {"type": "host_offline"})
                        continue
                    data["client_id"] = client_id
                    await safe_send(room.host, data)
            else:
                if kind == "host_status":
                    for cws in list(room.clients.values()):
                        await safe_send(cws, data)
                elif kind in {"pair_ok", "pair_error", "offer", "p2p_unavailable", "relay_response"}:
                    target = str(data.get("target", ""))
                    await safe_send(room.clients.get(target), data)
    except Exception:
        pass
    finally:
        if room is not None:
            if role == "client" and client_id:
                room.clients.pop(client_id, None)
                await safe_send(room.host, {"type": "client_left", "client_id": client_id})
            elif role == "host" and room.host is ws:
                room.host = None
                for cws in list(room.clients.values()):
                    await safe_send(cws, {"type": "host_offline"})
            if room.host is None and not room.clients:
                ROOMS.pop(room_name, None)
    return ws


app = web.Application(client_max_size=1_000_000)
app.router.add_get("/", index)
app.router.add_get("/health", health)
app.router.add_get("/ws", websocket_handler)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8890"))
    web.run_app(app, host="0.0.0.0", port=port)
