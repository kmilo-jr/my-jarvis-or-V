"""Bounded, read-only polling. Cursor and pending notice commit together."""
import hashlib
import threading
import time


class CaptureUnavailable(RuntimeError):
    pass


def gmail_delta(previous):
    from integrations.gmail_reader import GmailReader
    reader = GmailReader()
    with reader.connection() as (client, address, validity):
        scope = hashlib.sha256((address.casefold() + repr(validity)).encode()).hexdigest()
        if not previous or previous.get('scope') != scope:
            next_uid = client.response('UIDNEXT')[1]
            if not next_uid or not next_uid[0]: raise ValueError('UIDNEXT ausente')
            return {'scope': scope, 'uid': int(next_uid[0])-1}, None
        last = int(previous['uid'])
        status, data = client.uid('search', None, 'UID', f'{last+1}:*')
        if status != 'OK': raise ValueError('Consulta IMAP falhou')
        uids = sorted(int(x) for x in (data[0] or b'').split() if int(x) > last)
        if not uids: return previous, None
        from integrations.gmail_reader import parse_message
        raw = reader.fetch(client, str(uids[-1]), '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
        if not raw: raise ValueError('Cabeçalho indisponível')
        item = parse_message(raw)
        title = f"Gmail: {len(uids)} novo(s) e-mail(s). Mais recente: {item['sender']}. Assunto: {item['title']}"
        return {'scope': scope, 'uid': uids[-1]}, title[:240]


def messages_delta(previous):
    import mobile_bridge
    items = [x for x in mobile_bridge.recent_notifications(100)
             if str(x.get('app', '')).casefold() in ('whatsapp', 'instagram')]
    ids = [x['id'] for x in items]
    fresh = [x for x in items if x['id'] not in (previous or {}).get('ids', [])] if previous is not None else []
    if not fresh and not mobile_bridge.notification_backend_status().get('automatic'):
        raise CaptureUnavailable('Captura automática indisponível')
    if previous is None: return {'ids': ids}, None
    if not fresh: return {'ids': ids}, None
    latest = fresh[-1]
    # Content stays in the source app / existing notification history.
    return {'ids': ids}, f"{len(fresh)} nova(s) notificação(ões). {latest['app']}: {latest.get('title', '')}"[:240]


class LiveNotifications:
    def __init__(self, store, probes=None):
        self.store = store
        self.probes = probes or {'gmail': gmail_delta, 'messages': messages_delta}
        self.lock = threading.Lock()
        self.busy = set(); self.next_check = {}; self.failures = {}; self.status = {}
        self.closed = False

    def close(self):
        with self.lock: self.closed = True

    def tick(self):
        cfg = self.store.snapshot()['settings']
        if not cfg['enabled'] or cfg['paused_until'] > time.time(): return
        with self.lock:
            if self.closed: return
            for name in self.probes:
                if cfg.get(name) and name not in self.busy and time.monotonic() >= self.next_check.get(name, 0):
                    self.busy.add(name)
                    threading.Thread(target=self._run, args=(name,), daemon=True, name='V-Notify-'+name).start()

    def _run(self, name):
        delay = 30 if name == 'gmail' else 5
        try:
            previous = self.store.snapshot().get('notification_cursors', {}).get(name)
            cursor, title = self.probes[name](previous)
            with self.lock:
                if not self.closed:
                    self.store.commit_notification(name, previous, cursor, title)
                    self.failures[name] = 0
                    self.status[name] = 'Última consulta concluída às ' + time.strftime('%H:%M:%S')
        except Exception as exc:
            with self.lock:
                self.failures[name] = self.failures.get(name, 0) + 1
                delay = min(300, delay * 2 ** min(4, self.failures[name]))
                reason = 'Captura automática de mensagens indisponível' if isinstance(exc, CaptureUnavailable) else f'Falha ({type(exc).__name__})'
                self.status[name] = f'{reason}; nova tentativa em {delay} s. Confira Conexões.'
        finally:
            with self.lock:
                self.next_check[name] = time.monotonic() + delay
                self.busy.discard(name)
