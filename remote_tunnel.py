from __future__ import annotations

import re
import shutil
import subprocess
import threading
from typing import Optional


class CloudflareQuickTunnel:
    """Best-effort helper to expose V Remote outside home using cloudflared.

    Requires the `cloudflared` binary on the user's machine. The helper is optional;
    if the binary is missing, the rest of V Remote still works locally.
    """

    URL_RE = re.compile(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com")

    def __init__(self, local_url: str, binary: str = 'cloudflared'):
        self.local_url = local_url
        self.binary = binary
        self.proc: Optional[subprocess.Popen] = None
        self.public_url: str = ''
        self.last_error: str = ''
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def start(self):
        if not self.available:
            self.last_error = f'Não encontrei o executável {self.binary}. Instale o cloudflared para usar o modo fora de casa.'
            return self
        try:
            self.proc = subprocess.Popen(
                [self.binary, 'tunnel', '--url', self.local_url, '--no-autoupdate'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore',
            )
        except Exception as exc:
            self.last_error = f'{type(exc).__name__}: {exc}'
            return self

        def _reader():
            assert self.proc is not None
            try:
                for line in self.proc.stdout or []:
                    m = self.URL_RE.search(line)
                    if m:
                        self.public_url = m.group(0)
                    if 'error' in line.lower() and not self.last_error:
                        self.last_error = line.strip()
            except Exception as exc:
                if not self.last_error:
                    self.last_error = f'{type(exc).__name__}: {exc}'

        self._thread = threading.Thread(target=_reader, name='VRemoteTunnelReader', daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self.proc = None
