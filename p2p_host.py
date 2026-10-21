from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

try:
    import websockets
except Exception:
    websockets = None

try:
    from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
    AIORTC_AVAILABLE = True
except Exception:
    RTCConfiguration = RTCIceServer = RTCPeerConnection = RTCSessionDescription = None
    AIORTC_AVAILABLE = False


ALLOWED_ACTIONS = {
    "switch_ui", "toggle_voice", "volume_up", "volume_down", "volume_mute",
    "media_play_pause", "media_next", "media_previous", "open_spotify",
    "open_youtube", "open_browser", "lock_pc", "restart_pc", "shutdown_pc",
    "cancel_shutdown",
}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def ensure_p2p_identity(config_path: str | Path) -> dict:
    """Generate and persist a room id / device token if missing."""
    path = Path(config_path)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    remote = cfg.setdefault("remote", {})
    p2p = remote.setdefault("p2p", {})
    changed = False
    if not str(p2p.get("room_id", "")).strip():
        p2p["room_id"] = "v-" + secrets.token_hex(6)
        changed = True
    if not str(p2p.get("device_token", "")).strip():
        p2p["device_token"] = secrets.token_urlsafe(32)
        changed = True
    p2p.setdefault("enabled", True)
    p2p.setdefault("signaling_url", "")
    p2p.setdefault("stun_servers", ["stun:stun.l.google.com:19302"])
    p2p.setdefault("turn_servers", [])
    p2p.setdefault("relay_fallback", True)
    if changed:
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(p2p)


class VP2PHost:
    """Outbound V Remote connection with WebRTC P2P + WebSocket relay fallback.

    The PC only makes an outbound WSS connection to the signaling server. Once a
    phone is paired, aiortc attempts a direct WebRTC DataChannel. If that cannot
    be established, the same signaling WebSocket relays the small control JSON.
    """

    def __init__(
        self,
        signaling_url: str,
        room_id: str,
        device_token: str,
        command_callback: Callable[[str], None],
        action_callback: Callable[[str], None],
        status_provider: Callable[[], dict],
        stun_servers: list[str] | None = None,
        turn_servers: list[dict] | None = None,
        relay_fallback: bool = True,
    ):
        self.signaling_url = str(signaling_url or "").strip()
        self.room_id = str(room_id or "").strip()
        self.device_token = str(device_token or "").strip()
        self.command_callback = command_callback
        self.action_callback = action_callback
        self.status_provider = status_provider
        self.stun_servers = list(stun_servers or ["stun:stun.l.google.com:19302"])
        self.turn_servers = list(turn_servers or [])
        self.relay_fallback = bool(relay_fallback)
        self.pin = f"{secrets.randbelow(1_000_000):06d}"
        self.connected = False
        self.last_error = ""
        self.mode = "offline"
        self._ws = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._paired: set[str] = set()
        self._pcs: dict[str, Any] = {}
        self._channels: dict[str, Any] = {}

    @property
    def aiortc_available(self) -> bool:
        return AIORTC_AVAILABLE

    @property
    def remote_url(self) -> str:
        if not self.signaling_url:
            return ""
        p = urlparse(self.signaling_url)
        scheme = "https" if p.scheme == "wss" else "http"
        base = f"{scheme}://{p.netloc}/"
        # Fragment keeps the device token out of normal HTTP access logs.
        return f"{base}#room={self.room_id}&token={self.device_token}"

    def start(self):
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="VP2PHost", daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._async_stop(), self._loop)
            except Exception:
                pass
        self.connected = False
        self.mode = "offline"

    def snapshot(self) -> dict:
        direct = sum(1 for ch in self._channels.values() if getattr(ch, "readyState", "") == "open")
        return {
            "connected": self.connected,
            "mode": "p2p" if direct else ("relay" if self.connected else "offline"),
            "direct_peers": direct,
            "paired_peers": len(self._paired),
            "aiortc_available": self.aiortc_available,
            "remote_url": self.remote_url,
            "last_error": self.last_error,
        }

    def _thread_main(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_forever())
        finally:
            try:
                loop.run_until_complete(self._async_stop())
            except Exception:
                pass
            loop.close()

    async def _async_stop(self):
        for pc in list(self._pcs.values()):
            try:
                await pc.close()
            except Exception:
                pass
        self._pcs.clear()
        self._channels.clear()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None

    async def _run_forever(self):
        if websockets is None:
            self.last_error = "Dependência 'websockets' não instalada. Execute PREPARAR_V_P2P.bat."
            return
        if not self.signaling_url:
            self.last_error = "signaling_url não configurada"
            return
        delay = 2.0
        while not self._stop.is_set():
            try:
                await self._connect_once()
                delay = 2.0
            except asyncio.CancelledError:
                return
            except Exception as exc:
                self.connected = False
                self.mode = "offline"
                self.last_error = f"{type(exc).__name__}: {exc}"
            if self._stop.is_set():
                break
            await asyncio.sleep(delay)
            delay = min(15.0, delay * 1.5)

    async def _connect_once(self):
        async with websockets.connect(
            self.signaling_url,
            ping_interval=20,
            ping_timeout=20,
            max_size=1_000_000,
        ) as ws:
            self._ws = ws
            await self._send({
                "type": "register",
                "role": "host",
                "room": self.room_id,
                "token": self.device_token,
                "capabilities": {"webrtc": AIORTC_AVAILABLE, "relay": self.relay_fallback},
            })
            self.connected = True
            self.mode = "relay"
            self.last_error = ""
            status_task = asyncio.create_task(self._status_loop())
            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    await self._handle_signal(msg)
            finally:
                status_task.cancel()
                self.connected = False
                self.mode = "offline"
                self._ws = None

    async def _send(self, obj: dict):
        if self._ws is None:
            return
        await self._ws.send(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

    async def _status_loop(self):
        while self.connected and not self._stop.is_set():
            try:
                status = dict(self.status_provider() or {})
                status["p2p"] = self.snapshot()
                await self._send({"type": "host_status", "status": status})
                raw = json.dumps({"type": "status", "status": status}, ensure_ascii=False)
                for client_id, ch in list(self._channels.items()):
                    if getattr(ch, "readyState", "") == "open":
                        try:
                            ch.send(raw)
                        except Exception:
                            pass
            except Exception:
                pass
            await asyncio.sleep(2.0)

    async def _handle_signal(self, msg: dict):
        kind = str(msg.get("type", ""))
        client_id = str(msg.get("client_id", ""))
        if kind == "registered":
            return
        if kind == "client_left":
            self._paired.discard(client_id)
            await self._close_peer(client_id)
            return
        if kind == "pair_request":
            supplied = str(msg.get("pin", ""))
            if not hmac.compare_digest(supplied, self.pin):
                await self._send({"type": "pair_error", "target": client_id, "error": "PIN incorreto"})
                return
            self._paired.add(client_id)
            await self._send({
                "type": "pair_ok",
                "target": client_id,
                "webrtc": AIORTC_AVAILABLE,
                "relay": self.relay_fallback,
            })
            if AIORTC_AVAILABLE:
                asyncio.create_task(self._start_peer(client_id))
            else:
                await self._send({"type": "p2p_unavailable", "target": client_id, "reason": "aiortc não instalado; usando relay"})
            return
        if client_id and client_id not in self._paired:
            return
        if kind == "answer" and AIORTC_AVAILABLE:
            pc = self._pcs.get(client_id)
            if pc is not None:
                desc = msg.get("description") or {}
                await pc.setRemoteDescription(RTCSessionDescription(sdp=str(desc.get("sdp", "")), type="answer"))
            return
        if kind == "relay_request" and self.relay_fallback:
            payload = msg.get("payload") or {}
            result = await self._handle_payload(payload)
            await self._send({"type": "relay_response", "target": client_id, "request_id": msg.get("request_id"), "result": result})
            return

    def _rtc_configuration(self):
        servers = []
        if self.stun_servers:
            servers.append(RTCIceServer(urls=self.stun_servers))
        for item in self.turn_servers:
            try:
                servers.append(RTCIceServer(
                    urls=item.get("urls") or item.get("url"),
                    username=item.get("username"),
                    credential=item.get("credential"),
                ))
            except Exception:
                pass
        return RTCConfiguration(iceServers=servers)

    async def _wait_ice_complete(self, pc, timeout: float = 8.0):
        end = time.monotonic() + timeout
        while pc.iceGatheringState != "complete" and time.monotonic() < end:
            await asyncio.sleep(0.05)

    async def _start_peer(self, client_id: str):
        await self._close_peer(client_id)
        pc = RTCPeerConnection(self._rtc_configuration())
        self._pcs[client_id] = pc
        channel = pc.createDataChannel("v-control", ordered=True)
        self._channels[client_id] = channel

        @channel.on("open")
        def _opened():
            self.mode = "p2p"
            try:
                channel.send(json.dumps({"type": "hello", "mode": "p2p"}))
            except Exception:
                pass

        @channel.on("close")
        def _closed():
            self._channels.pop(client_id, None)

        @channel.on("message")
        def _message(data):
            async def work():
                try:
                    payload = json.loads(data) if isinstance(data, str) else {}
                except Exception:
                    payload = {}
                request_id = payload.pop("request_id", None)
                result = await self._handle_payload(payload)
                try:
                    channel.send(json.dumps({"type": "response", "request_id": request_id, "result": result}, ensure_ascii=False))
                except Exception:
                    pass
            asyncio.create_task(work())

        @pc.on("connectionstatechange")
        async def _state_change():
            if pc.connectionState in {"failed", "closed"}:
                await self._close_peer(client_id)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await self._wait_ice_complete(pc)
        desc = pc.localDescription
        await self._send({
            "type": "offer",
            "target": client_id,
            "description": {"type": desc.type, "sdp": desc.sdp},
        })

    async def _close_peer(self, client_id: str):
        self._channels.pop(client_id, None)
        pc = self._pcs.pop(client_id, None)
        if pc is not None:
            try:
                await pc.close()
            except Exception:
                pass

    async def _handle_payload(self, payload: dict) -> dict:
        kind = str(payload.get("kind", ""))
        try:
            if kind == "command":
                text = str(payload.get("text", "")).strip()[:500]
                if not text:
                    return {"ok": False, "error": "comando vazio"}
                self.command_callback(text)
                return {"ok": True}
            if kind == "action":
                name = str(payload.get("name", "")).strip().lower()
                if name not in ALLOWED_ACTIONS:
                    return {"ok": False, "error": "ação inválida"}
                self.action_callback(name)
                return {"ok": True}
            if kind == "mobile_create":
                import mobile_bridge
                subtype = str(payload.get("subtype", ""))
                if subtype == "alarm":
                    action = mobile_bridge.queue_alarm(
                        time_text=str(payload.get("time", "")),
                        label=str(payload.get("label", "") or "Alarme do V"),
                    )
                elif subtype == "reminder":
                    action = mobile_bridge.queue_reminder(
                        title=str(payload.get("title", "")),
                        due=str(payload.get("due", "")),
                    )
                else:
                    return {"ok": False, "error": "ação mobile inválida"}
                return {"ok": True, "action": action}
            if kind == "get_status":
                return {"ok": True, "status": dict(self.status_provider() or {})}
            if kind == "ping":
                return {"ok": True, "pong": time.time()}
            return {"ok": False, "error": "payload desconhecido"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
