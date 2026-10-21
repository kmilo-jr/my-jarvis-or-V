from __future__ import annotations

"""Best-effort, read-only Windows toast reader for V Mobile.

The public UserNotificationListener API is awkward for an unpackaged Python
process.  This module instead reads the current user's Windows Push
Notification SQLite repository in read-only mode and only surfaces entries that
belong to WhatsApp/Instagram, either on the PC or via Phone Link.

It never modifies or clears Windows notifications.
"""

from pathlib import Path
from xml.etree import ElementTree as ET
import os
import re
import sqlite3


PHONE_TOKENS = ("yourphone", "phoneexperience", "phonelink", "crossdevice", "phone link", "link do telefone")
DEFAULT_ALLOWED = ("whatsapp", "instagram")


def _db_path() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    return Path(local) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db" if local else Path()


def _decode_payload(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raw = bytes(value)
    for enc in ("utf-8", "utf-16-le", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            if "<" in text or text.strip():
                return text.replace("\x00", "")
        except Exception:
            pass
    return ""


def _texts(xml_payload: str) -> list[str]:
    if not xml_payload:
        return []
    try:
        root = ET.fromstring(xml_payload)
        vals = []
        for node in root.iter():
            if str(node.tag).lower().endswith("text") and node.text:
                t = re.sub(r"\s+", " ", node.text).strip()
                if t and t not in vals:
                    vals.append(t)
        return vals
    except Exception:
        # fallback for payloads with minor malformed XML
        vals = re.findall(r"<text[^>]*>(.*?)</text>", xml_payload, flags=re.I | re.S)
        return [re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", x)).strip() for x in vals if x.strip()]


class WindowsPhoneNotificationReader:
    def __init__(self, allowed_apps=None):
        self.allowed_apps = tuple(str(x).lower() for x in (allowed_apps or DEFAULT_ALLOWED))
        self.path = _db_path()
        self.last_order: int | None = None
        self.last_error = ""

    @property
    def available(self) -> bool:
        return bool(self.path and self.path.is_file())

    def _connect(self):
        uri = self.path.as_uri() + "?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=0.8)

    def _max_order(self) -> int:
        if not self.available:
            return 0
        con = self._connect()
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(Notification)")}
            order_col = "Order" if "Order" in cols else next((x for x in ("Id", "NotificationId") if x in cols), None)
            if not order_col:
                return 0
            row = con.execute(f'SELECT MAX("{order_col}") FROM Notification').fetchone()
            return int((row or [0])[0] or 0)
        finally:
            con.close()

    def _fetch(self, limit: int = 80) -> list[dict]:
        if not self.available:
            return []
        con = self._connect()
        try:
            con.row_factory = sqlite3.Row
            ncols = {r[1] for r in con.execute("PRAGMA table_info(Notification)")}
            hcols = {r[1] for r in con.execute("PRAGMA table_info(NotificationHandler)")}
            order_col = "Order" if "Order" in ncols else next((x for x in ("Id", "NotificationId") if x in ncols), None)
            if not order_col or "HandlerId" not in ncols or "Payload" not in ncols:
                return []
            rec_col = "RecordId" if "RecordId" in hcols else next((x for x in ("Id", "HandlerId") if x in hcols), None)
            primary_col = "PrimaryId" if "PrimaryId" in hcols else None
            handler_expr = f'h."{primary_col}"' if primary_col else "''"
            join = f'LEFT JOIN NotificationHandler h ON n."HandlerId"=h."{rec_col}"' if rec_col else ""
            where = "WHERE lower(COALESCE(n.\"Type\", 'toast')) LIKE 'toast%'" if "Type" in ncols else ""
            q = f'''SELECT n."{order_col}" AS ord, n."Payload" AS payload, {handler_expr} AS primary_id\n                    FROM Notification n {join}\n                    {where}\n                    ORDER BY n."{order_col}" DESC LIMIT ?'''
            rows = con.execute(q, (max(10, min(limit, 200)),)).fetchall()
            out = []
            for row in rows:
                payload = _decode_payload(row["payload"])
                primary = str(row["primary_id"] or "")
                joined = (primary + " " + payload).lower()
                phoneish = any(t in primary.lower() for t in PHONE_TOKENS)
                matched = next((app for app in self.allowed_apps if app in joined), "")
                # Privacy default: only WhatsApp/Instagram are surfaced.
                if not matched:
                    continue
                texts = _texts(payload)
                # Remove duplicated source-app label from title/body.
                clean = [t for t in texts if t.lower() not in self.allowed_apps]
                title = clean[0] if clean else matched.title()
                body = clean[1] if len(clean) > 1 else (clean[0] if clean else "Nova notificação")
                out.append({"order": int(row["ord"]), "app": matched.title(), "title": title[:180], "body": body[:500], "handler": primary[:200], "source": "windows-phone-link" if phoneish else "windows-desktop"})
            return out
        finally:
            con.close()

    def poll_new(self) -> list[dict]:
        try:
            if self.last_order is None:
                # Snapshot the current global notification order. Existing toasts
                # are never announced, but the first new WhatsApp/Instagram toast
                # after startup will be detected correctly.
                self.last_order = self._max_order()
                self.last_error = ""
                return []
            rows = self._fetch()
            if not rows:
                self.last_error = ""
                return []
            fresh = [x for x in rows if int(x["order"]) > int(self.last_order)]
            global_max = self._max_order()
            self.last_order = max(int(self.last_order), int(global_max))
            self.last_error = ""
            return sorted(fresh, key=lambda x: int(x["order"]))
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return []
