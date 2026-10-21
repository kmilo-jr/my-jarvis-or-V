"""Sample local health without blocking the UI; notify only sustained conditions."""
import os
import time


class SystemWatch:
    def __init__(self, store):
        self.store = store
        self.last_sample = None
        self.since = {}
        self.last_alert = {}
        self.event_ids = {}

    def poll(self, now=None):
        now = time.time() if now is None else now
        if self.last_sample is not None and now - self.last_sample < 15:
            return
        if not self.store.snapshot()['settings']['system']:
            self.since.clear()
            return
        import psutil
        drive = os.environ.get('SystemDrive', 'C:') + os.sep
        battery = psutil.sensors_battery()
        readings = {'cpu': psutil.cpu_percent(interval=None), 'ram': psutil.virtual_memory().percent,
                    'disk_free': 100 - psutil.disk_usage(drive).percent,
                    'battery': battery.percent if battery and not battery.power_plugged else None}
        self.observe(readings, now)

    def observe(self, readings, now):
        if self.last_sample is None or now - self.last_sample > 60:
            self.since.clear()
        self.last_sample = now
        conditions = {
            'cpu': (readings.get('cpu', 0) >= 95, 120, 'A CPU ficou acima de 95% por cerca de dois minutos. Confira os programas em execução.'),
            'ram': (readings.get('ram', 0) >= 90, 120, 'A memória RAM ficou acima de 90% por cerca de dois minutos. Confira os programas em execução.'),
            'disk': (readings.get('disk_free', 100) <= 5, 30, 'O disco do Windows está com 5% ou menos de espaço livre. Revise os arquivos quando puder.'),
            'battery': (readings.get('battery') is not None and readings['battery'] <= 15, 15, 'A bateria está em 15% ou menos, fora da tomada. Conecte o carregador quando puder.'),
        }
        snapshot = self.store.snapshot()
        pending_by_title = {e['title']: e['id'] for e in snapshot['events'] if e['kind'] == 'system' and e['state'] == 'pending'}
        for key, (active, duration, title) in conditions.items():
            previous = [e['created'] for e in snapshot['events'] if e['kind'] == 'system' and e['title'] == title]
            if previous:
                self.last_alert[key] = max(self.last_alert.get(key, -float('inf')), max(previous))
            if title in pending_by_title:
                self.event_ids[key] = pending_by_title[title]
            if not active:
                self.since.pop(key, None)
                event_id = self.event_ids.pop(key, None)
                if event_id:
                    self.store.cancel_pending(event_id)
                continue
            self.since.setdefault(key, now)
            if now - self.since[key] < duration or now - self.last_alert.get(key, -float('inf')) < 1800:
                continue
            # A pending event already represents this condition, including after restart.
            if title in pending_by_title:
                continue
            event = self.store.add(title, now, kind='system', now=now)
            if event:
                self.event_ids[key] = event['id']
                self.last_alert[key] = now
