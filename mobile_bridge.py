from __future__ import annotations

"""V Mobile bridge.

Maintains a small local action queue consumed by the V Remote page.  The page
opens an iOS Shortcut URL only after a user tap, which keeps the flow compatible
with Safari/iOS restrictions on launching custom URL schemes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from urllib.parse import quote
import json
import re
import secrets
import unicodedata

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
ACTIONS_FILE = DATA_DIR / "mobile_actions.json"
NOTIFICATIONS_FILE = DATA_DIR / "mobile_notifications.json"
BACKEND_FILE = DATA_DIR / "mobile_notification_backend.json"
_LOCK = RLock()


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", s).strip()


def _load(path: Path, key: str) -> list[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        arr = obj.get(key, []) if isinstance(obj, dict) else []
        return [x for x in arr if isinstance(x, dict)]
    except Exception:
        return []


def _save(path: Path, key: str, items: list[dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"version": 1, key: items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_clock(request: str) -> tuple[int, int] | None:
    s = _norm(request)
    # 06:30 / 6.30 / 6h30 / 6 h 30
    m = re.search(r"\b([01]?\d|2[0-3])\s*(?::|\.|h)\s*([0-5]\d)\b", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    # 6h / 18 horas / 7 hora
    m = re.search(r"\b([01]?\d|2[0-3])\s*(?:h|hora|horas)\b", s)
    if m:
        return int(m.group(1)), 0
    return None


def _parse_due(request: str) -> datetime | None:
    now = datetime.now()
    s = _norm(request)
    clock = _parse_clock(request)
    if "amanha" in s:
        base = now + timedelta(days=1)
    elif "hoje" in s:
        base = now
    else:
        dm = re.search(r"\b([0-3]?\d)[/-]([01]?\d)(?:[/-](\d{2,4}))?\b", s)
        if dm:
            day, month = int(dm.group(1)), int(dm.group(2))
            year = int(dm.group(3)) if dm.group(3) else now.year
            if year < 100:
                year += 2000
            try:
                base = now.replace(year=year, month=month, day=day)
            except ValueError:
                return None
        elif clock:
            base = now
        else:
            return None
    if clock:
        return base.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0)
    return base.replace(hour=9, minute=0, second=0, microsecond=0)


def _extract_reminder_title(request: str) -> str:
    raw = str(request or "").strip()
    # Prefer everything after "de" following a temporal expression.
    patterns = [
        r"\b(?:hoje|amanh[ãa])\b.*?\b(?:de|para)\s+(.+)$",
        r"\b(?:às|as)\s+\d{1,2}(?::\d{2}|h\d{0,2})?\s+(.+)$",
        r"\blembrete\s+(?:para|de)\s+(.+)$",
        r"\bme\s+lembre\s+(?:de\s+)?(.+)$",
        r"\blembre(?:-me)?\s+(?:de\s+)?(.+)$",
    ]
    for p in patterns:
        m = re.search(p, raw, flags=re.I)
        if m:
            title = m.group(1).strip(" .,!?:;-")
            # strip temporal tail that sometimes survives
            title = re.sub(r"\s+(?:hoje|amanh[ãa])(?:\s+(?:às|as)\s+\d.*)?$", "", title, flags=re.I).strip()
            if title:
                return title[:180]
    return raw[:180] or "Lembrete do V"


def _shortcut_payload(action: dict) -> str:
    kind = action.get("kind", "")
    if kind == "alarm":
        # Simple pipe format is intentionally easy to parse in Apple Shortcuts.
        return f"ALARM|{action.get('time','')}|{action.get('label','Alarme do V')}"
    if kind == "reminder":
        return f"REMINDER|{action.get('due','')}|{action.get('title','Lembrete do V')}"
    return f"UNKNOWN||{action.get('title','V Mobile')}"


def _configured_shortcut_name() -> str:
    try:
        cfg = json.loads((BASE / "config" / "default.json").read_text(encoding="utf-8"))
        return str((cfg.get("mobile", {}) or {}).get("shortcut_name", "V Mobile") or "V Mobile").strip()
    except Exception:
        return "V Mobile"


def shortcut_url(action: dict, shortcut_name: str = "") -> str:
    payload = _shortcut_payload(action)
    name = shortcut_name or _configured_shortcut_name()
    return f"shortcuts://run-shortcut?name={quote(name)}&input=text&text={quote(payload)}"


def _queue(action: dict) -> dict:
    with _LOCK:
        items = _load(ACTIONS_FILE, "actions")
        action = dict(action)
        action.setdefault("id", secrets.token_urlsafe(9))
        action.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        action.setdefault("status", "pending")
        action["shortcut_url"] = shortcut_url(action)
        items.append(action)
        items = items[-50:]
        _save(ACTIONS_FILE, "actions", items)
        return action


def queue_alarm(request: str = "", time_text: str = "", label: str = "") -> dict:
    clock = _parse_clock(time_text or request)
    if not clock:
        raise ValueError("Não encontrei um horário válido para o alarme.")
    hhmm = f"{clock[0]:02d}:{clock[1]:02d}"
    label = (label or "Alarme do V").strip()[:120]
    return _queue({"kind": "alarm", "time": hhmm, "label": label, "request": str(request or "")[:300]})


def queue_reminder(request: str = "", title: str = "", due: str = "") -> dict:
    if due:
        try:
            dt = datetime.fromisoformat(due)
        except Exception as exc:
            raise ValueError("Data/hora do lembrete inválida.") from exc
    else:
        dt = _parse_due(request)
    if dt is None:
        raise ValueError("Não encontrei quando criar o lembrete. Diga, por exemplo, 'amanhã às 14h'.")
    title = (title or _extract_reminder_title(request)).strip()[:180]
    return _queue({"kind": "reminder", "due": dt.isoformat(timespec="minutes"), "title": title, "request": str(request or "")[:300]})


def pending_actions(limit: int = 8) -> list[dict]:
    with _LOCK:
        items = _load(ACTIONS_FILE, "actions")
    pending = [x for x in items if x.get("status") == "pending"]
    return pending[-max(1, min(int(limit), 20)):]


def ack_action(action_id: str, status: str = "launched") -> bool:
    action_id = str(action_id or "").strip()
    if not action_id:
        return False
    with _LOCK:
        items = _load(ACTIONS_FILE, "actions")
        found = False
        for item in items:
            if str(item.get("id", "")) == action_id:
                item["status"] = status if status in {"launched", "done", "cancelled"} else "launched"
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                found = True
                break
        if found:
            _save(ACTIONS_FILE, "actions", items[-50:])
        return found


def record_notification(app: str, title: str, body: str, source: str = "relay") -> dict:
    item = {
        "id": secrets.token_urlsafe(8),
        "app": str(app or "iPhone")[:80],
        "title": str(title or "")[:180],
        "body": str(body or "")[:500],
        "source": str(source or "relay")[:40],
        "received_at": datetime.now().isoformat(timespec="seconds"),
    }
    with _LOCK:
        items = _load(NOTIFICATIONS_FILE, "notifications")
        items.append(item)
        _save(NOTIFICATIONS_FILE, "notifications", items[-100:])
    return item


def recent_notifications(limit: int = 8) -> list[dict]:
    with _LOCK:
        items = _load(NOTIFICATIONS_FILE, "notifications")
    return items[-max(1, min(int(limit), 100)):]


def set_notification_backend(automatic: bool, backend: str, message: str, error: str = "") -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    core = {
        "automatic": bool(automatic),
        "backend": str(backend or "relay"),
        "message": str(message or ""),
        "error": str(error or "")[:300],
    }
    try:
        old = json.loads(BACKEND_FILE.read_text(encoding="utf-8"))
        if isinstance(old, dict) and all(old.get(k) == v for k, v in core.items()):
            return
    except Exception:
        pass
    payload = dict(core, updated_at=datetime.now().isoformat(timespec="seconds"))
    try:
        BACKEND_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def notification_backend_status() -> dict:
    try:
        obj = json.loads(BACKEND_FILE.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {
        "automatic": False,
        "backend": "relay",
        "message": "Aguardando o leitor de notificações do Windows. Use o WhatsApp no PC com notificações ativadas; Phone Link é opcional.",
    }
