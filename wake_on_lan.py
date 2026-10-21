from __future__ import annotations

import re
import socket
from dataclasses import dataclass

_MAC_RE = re.compile(r"^[0-9A-Fa-f]{12}$")


def normalize_mac(value: str) -> str:
    compact = re.sub(r"[^0-9A-Fa-f]", "", str(value or ""))
    if not _MAC_RE.fullmatch(compact):
        raise ValueError("invalid MAC address")
    return compact.upper()


def magic_packet(mac: str) -> bytes:
    raw = bytes.fromhex(normalize_mac(mac))
    return b"\xff" * 6 + raw * 16


def send_magic_packet(mac: str, broadcast: str = "255.255.255.255", port: int = 9) -> None:
    packet = magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(2.0)
        sock.sendto(packet, (str(broadcast), int(port)))


@dataclass(frozen=True)
class WakeConfig:
    enabled: bool = False
    mac: str = ""
    broadcast: str = "255.255.255.255"
    port: int = 9

    @classmethod
    def from_dict(cls, data: dict | None) -> "WakeConfig":
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", False)),
            mac=str(data.get("mac", "")).strip(),
            broadcast=str(data.get("broadcast", "255.255.255.255")).strip() or "255.255.255.255",
            port=int(data.get("port", 9)),
        )

    @property
    def configured(self) -> bool:
        if not self.enabled or not self.mac:
            return False
        try:
            normalize_mac(self.mac)
            return 1 <= int(self.port) <= 65535
        except Exception:
            return False
