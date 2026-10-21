"""Local, explicit reminders and factual completion notices. No background actions."""
from datetime import datetime
import json
import math
from pathlib import Path
import threading
import time
from uuid import uuid4


class InitiativeStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).resolve().parents[1] / "data" / "initiative.json"
        self.lock = threading.RLock()

    @staticmethod
    def defaults():
        return {"enabled": True, "voice": False, "reminders": True, "completions": True,
                "alarms": True, "appointments": True, "system": True, "gmail": True, "messages": True,
                "breaks": True, "summaries": True, "break_minutes": 50,
                "quiet_enabled": True, "quiet_start": 22, "quiet_end": 8,
                "gap_seconds": 120, "paused_until": 0.0}

    def _load(self):
        if not self.path.exists():
            return {"settings": self.defaults(), "events": [], "last_notice": 0.0, "next_break": 0.0}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("events"), list):
            raise ValueError("Arquivo de avisos inválido; os dados foram preservados.")
        data["settings"] = self._settings(data.get("settings", {}))
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Keep all pending items, and at most 100 closed items.
        pending = [e for e in data["events"] if e["state"] == "pending" or e.get('voice_state') == 'pending']
        closed = [e for e in data["events"] if e["state"] != "pending" and e.get('voice_state') != 'pending'][-100:]
        data["events"] = closed + pending
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def _settings(self, changes):
        cfg = self.defaults()
        cfg.update({k: v for k, v in changes.items() if k in cfg})
        for key in ("enabled", "voice", "reminders", "completions", "quiet_enabled", "breaks", "summaries", "alarms", "appointments", "system", "gmail", "messages"):
            if type(cfg[key]) is not bool:
                raise ValueError("Opção inválida: " + key)
        for key in ("quiet_start", "quiet_end"):
            if type(cfg[key]) is not int or not 0 <= cfg[key] <= 23:
                raise ValueError("Horário inválido.")
        if type(cfg["gap_seconds"]) is not int or not 30 <= cfg["gap_seconds"] <= 3600:
            raise ValueError("Intervalo deve ficar entre 30 e 3600 segundos.")
        if type(cfg["break_minutes"]) is not int or not 10 <= cfg["break_minutes"] <= 180:
            raise ValueError("Intervalo de pausa deve ficar entre 10 e 180 minutos.")
        if type(cfg["paused_until"]) not in (int, float) or not math.isfinite(cfg['paused_until']) or cfg["paused_until"] < 0:
            raise ValueError("Pausa inválida.")
        return cfg

    def snapshot(self):
        with self.lock:
            return self._load()

    def commit_notification(self, name, previous, cursor, title):
        if name not in ('gmail', 'messages'): raise ValueError('Categoria inválida')
        with self.lock:
            data = self._load()
            cfg = data['settings']
            if not cfg['enabled'] or not cfg[name] or cfg['paused_until'] > time.time(): return
            cursors = data.setdefault('notification_cursors', {})
            if cursors.get(name) != previous: return
            if cursor == previous and not title: return
            if title:
                # Coalesce queued arrivals during silence instead of creating an unbounded backlog.
                pending = next((e for e in data['events'] if e['kind'] == name and e['state'] == 'pending'), None)
                if pending:
                    pending['title'] = ('Novas atualizações acumuladas. ' + title)[:240]
                else:
                    data['events'].append(dict(id=uuid4().hex, title=title[:240], due=time.time(),
                                               kind=name, state='pending', created=time.time()))
            cursors[name] = cursor
            self._save(data)

    def update_settings(self, changes):
        with self.lock:
            data = self._load()
            data["settings"] = self._settings(dict(data["settings"], **changes))
            self._save(data)

    def add(self, title, due, kind="reminders", now=None):
        now = time.time() if now is None else now
        title = str(title).strip()
        if not title or len(title) > 240:
            raise ValueError("Escreva um aviso de 1 a 240 caracteres.")
        if kind not in ("reminders", "completions", "breaks", "summaries", "alarms", "appointments", "system") or type(due) not in (int, float) or not math.isfinite(due):
            raise ValueError("Tipo ou data inválidos.")
        if kind in ("reminders", "alarms", "appointments") and due <= now:
            raise ValueError("Escolha um horário futuro para o lembrete.")
        with self.lock:
            data = self._load()
            if kind not in ("reminders", "alarms", "appointments") and not data["settings"][kind]:
                return None
            event = {"id": uuid4().hex, "title": title, "due": due, "kind": kind,
                     "state": "pending", "created": now}
            data["events"].append(event)
            self._save(data)
            return event

    def change_event(self, event_id, *, due=None):
        with self.lock:
            data = self._load()
            event = next((e for e in data["events"] if e["id"] == event_id), None)
            if event is None:
                raise ValueError("Aviso não encontrado.")
            if due is None:
                event["state"] = "cancelled"
                event['voice_state'] = 'cancelled'
                if event["kind"] == "breaks" and data.get("next_break", 0):
                    data["next_break"] = time.time() + data["settings"]["break_minutes"] * 60
            else:
                if type(due) not in (int, float) or not math.isfinite(due) or due <= time.time():
                    raise ValueError("Escolha um horário futuro.")
                event.update(due=due, state="pending")
                event.update(voice_state='none', voice_attempts=0, voice_retry_at=0)
            self._save(data)

    def cancel_pending(self, event_id):
        with self.lock:
            data = self._load()
            event = next((e for e in data['events'] if e['id'] == event_id and e['state'] == 'pending'), None)
            if event is not None:
                event['state'] = 'cancelled'
                event['voice_state'] = 'cancelled'
                self._save(data)

    @staticmethod
    def quiet(cfg, now):
        if not cfg["quiet_enabled"]:
            return False
        hour = datetime.fromtimestamp(now).hour
        start, end = cfg["quiet_start"], cfg["quiet_end"]
        if start == end:
            return True  # explicitly all day
        return start <= hour < end if start < end else hour >= start or hour < end

    def next_notice(self, *, busy, now=None):
        now = time.time() if now is None else now
        with self.lock:
            data = self._load()
            cfg = data["settings"]
            if not cfg['enabled'] or now < cfg['paused_until']:
                return None
            alarms = [e for e in data['events'] if e['kind'] == 'alarms' and e['state'] == 'pending' and e['due'] <= now]
            if cfg['alarms'] and alarms:
                return dict(min(alarms, key=lambda e: e['due']), voice=cfg['voice'] and not busy, voice_requested=cfg['voice'])
            ready = [e for e in data["events"] if e["state"] == "pending" and e["due"] - (600 if e['kind'] == 'appointments' else 0) <= now and cfg[e["kind"]]]
            if not ready:
                return None
            quiet = self.quiet(cfg, now)
            delayed = busy or quiet or now - data.get("last_notice", 0) < cfg["gap_seconds"]
            if delayed:
                # Incoming account notifications are shown immediately. Their
                # voice remains subject to busy/quiet controls and can wait in
                # the voice queue after the visual event was delivered.
                live = [e for e in ready if e['kind'] in ('gmail', 'messages')] if not quiet else []
                if not live:
                    return None
                event = min(live, key=lambda e: e["due"])
                return dict(event, voice=cfg['voice'] and not busy and not quiet,
                            voice_requested=cfg['voice'])
            event = min(ready, key=lambda e: e["due"])
            return dict(event, voice=cfg["voice"], voice_requested=cfg['voice'])

    def delivered(self, event_id, now=None, *, voice_pending=False):
        with self.lock:
            data = self._load()
            event = next(e for e in data["events"] if e["id"] == event_id)
            event.update(state="delivered", delivered=time.time() if now is None else now)
            if voice_pending and event['kind'] != 'completions':
                event.update(voice_state='pending', voice_attempts=0, voice_retry_at=0)
            data["last_notice"] = event["delivered"]
            if event["kind"] == "breaks" and data.get("next_break", 0):
                data["next_break"] = event["delivered"] + data["settings"]["break_minutes"] * 60
            self._save(data)

    def next_voice_notice(self, *, busy, now=None, defer_common=False):
        now = time.time() if now is None else now
        with self.lock:
            data = self._load()
            cfg = data['settings']
            if busy or not cfg['enabled'] or not cfg['voice'] or now < cfg['paused_until']:
                return None
            ready = [e for e in data['events'] if e['state'] == 'delivered' and e.get('voice_state') == 'pending'
                     and (not defer_common or e['kind'] == 'alarms')
                     and e.get('voice_retry_at', 0) <= now and cfg[e['kind']]
                     and (e['kind'] == 'alarms' or not self.quiet(cfg, now))]
            return dict(min(ready, key=lambda e: (e['kind'] != 'alarms', e['due']))) if ready else None

    def voice_result(self, event_id, state, error='', now=None):
        now = time.time() if now is None else now
        with self.lock:
            data = self._load()
            event = next((e for e in data['events'] if e['id'] == event_id), None)
            if event is None or event.get('voice_state') != 'pending':
                return
            attempts = event.get('voice_attempts', 0) + 1
            if state == 'done':
                event.update(voice_state='spoken', voice_delivered=now, voice_error='')
            elif state == 'cancelled':
                event.update(voice_state='cancelled', voice_error='Fala interrompida.')
            else:
                event.update(voice_state='failed' if attempts >= 3 else 'pending', voice_retry_at=now + 60, voice_error=error or 'Falha na reprodução.')
            event['voice_attempts'] = attempts
            self._save(data)

    def work_session(self, active, now=None):
        now = time.time() if now is None else now
        with self.lock:
            data = self._load()
            data["next_break"] = now + data["settings"]["break_minutes"] * 60 if active else 0.0
            for event in data["events"]:
                if event["kind"] == "breaks" and event["state"] == "pending":
                    event["state"] = "cancelled"
            self._save(data)

    def schedule_break(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            data = self._load()
            due = data.get("next_break", 0)
            if (data["settings"]["breaks"] and due and now >= due
                    and not any(e["kind"] == "breaks" and e["state"] == "pending" for e in data["events"])):
                self.add("Você está no modo trabalho há um tempo. Que tal fazer uma pausa?", now, "breaks", now)

    def startup_summary(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            data = self._load()
            if not data["settings"]["summaries"]:
                return
            reminders = [e for e in data["events"] if e["kind"] == "reminders" and e["state"] == "pending"]
            overdue = sum(e["due"] <= now for e in reminders)
            today = sum(e["due"] > now and datetime.fromtimestamp(e["due"]).date() == datetime.fromtimestamp(now).date() for e in reminders)
            text = f"Seu resumo local: {overdue} lembrete(s) vencido(s) e {today} para mais tarde hoje."
            alarm_count = sum(e['kind'] == 'alarms' and e['state'] == 'pending' and datetime.fromtimestamp(e['due']).date() == datetime.fromtimestamp(now).date() for e in data['events'])
            appointment_count = sum(e['kind'] == 'appointments' and e['state'] != 'cancelled' and e['due'] > now and datetime.fromtimestamp(e['due']).date() == datetime.fromtimestamp(now).date() for e in data['events'])
            if alarm_count or appointment_count:
                text += f' Hoje: {alarm_count} alarme(s) e {appointment_count} compromisso(s) por vir.'
            if data.get("next_break", 0) and data["settings"]["breaks"]:
                text += " As sugestões de pausa do modo trabalho estão ativas."
            for event in data["events"]:
                if event["kind"] == "summaries" and event["state"] == "pending":
                    event["state"] = "cancelled"
            self._save(data)
            self.add(text, now, "summaries", now)
