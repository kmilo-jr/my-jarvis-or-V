"""Groq text and JSON adapter, without remote execution of V tools."""
import base64
import json
import os
from pathlib import Path
import time
import requests

KEY_PATH = Path(__file__).resolve().parents[1] / 'config' / 'groq_key.dat'
DEFAULT_MODEL = 'openai/gpt-oss-120b'


def load_key(path=None):
    env = os.environ.get('GROQ_API_KEY', '').strip()
    if env:
        return env
    try:
        import win32crypt
        payload = json.loads(Path(path or KEY_PATH).read_text(encoding='utf-8'))
        if payload.get('scheme') != 'windows-dpapi-user':
            return ''
        return win32crypt.CryptUnprotectData(base64.b64decode(payload['data']), None, None, None, 0)[1].decode('utf-8').strip()
    except Exception:
        return ''


def save_key(key, path=None):
    import win32crypt
    key = str(key).strip()
    if not key:
        raise ValueError('Chave vazia.')
    blob = win32crypt.CryptProtectData(key.encode('utf-8'), 'V Groq', None, None, None, 0)
    path = Path(path or KEY_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps({'scheme': 'windows-dpapi-user', 'data': base64.b64encode(blob).decode('ascii')}), encoding='utf-8')
    temp.replace(path)


class GroqClient:
    def __init__(self, config):
        self.enabled = bool(config.get('groq_enabled', True))
        self.model = str(config.get('groq_model', DEFAULT_MODEL))
        self.timeout = max(1, min(30, float(config.get('groq_timeout', 12))))
        self.key = load_key()
        self.session = requests.Session()
        self.last_error = ''
        self.last_latency = {}
        self.retry_at = 0.0
        self.last_stream_text = ""

    @property
    def available(self):
        return self.enabled and bool(self.key)

    def generate(self, system, history, text, *, json_mode=False):
        started = time.perf_counter()
        self.last_latency = {'provider': 'groq:' + self.model, 'streaming': False}
        if not self.available:
            self.last_error = 'Groq: chave não configurada ou serviço desativado.'
            return None
        if time.monotonic() < self.retry_at:
            return None
        messages = [{'role': 'system', 'content': system}]
        for item in history[-10:]:
            if item.get('role') in ('user', 'assistant') and item.get('content'):
                messages.append({'role': item['role'], 'content': str(item['content'])[:1500]})
        messages.append({'role': 'user', 'content': str(text)})
        payload = {'model': self.model, 'messages': messages, 'stream': False,
                   'max_completion_tokens': 2048 if json_mode else 1200}
        if self.model.startswith('openai/gpt-oss-'):
            payload['reasoning_effort'] = 'low'
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        try:
            with self.session.post('https://api.groq.com/openai/v1/chat/completions',
                                   headers={'Authorization': 'Bearer ' + self.key},
                                   json=payload, timeout=(3, self.timeout)) as response:
                if response.status_code >= 400:
                    labels = {401: 'chave inválida', 403: 'acesso negado', 404: 'modelo indisponível',
                              429: 'limite de uso atingido', 503: 'serviço indisponível'}
                    self.last_error = f"Groq: HTTP {response.status_code} — {labels.get(response.status_code, 'pedido recusado')}"
                    if response.status_code == 429:
                        try:
                            delay = max(1, min(3600, float(response.headers.get('retry-after', 60))))
                        except (ValueError, TypeError):
                            delay = 60
                        self.retry_at = time.monotonic() + delay
                    elif response.status_code >= 500:
                        self.retry_at = time.monotonic() + 30
                    return None
                obj = response.json()
            choice = (obj.get('choices') or [{}])[0]
            answer = (choice.get('message') or {}).get('content')
            if choice.get('finish_reason') != 'stop':
                self.last_error = 'Groq: resposta incompleta ou sem conclusão válida.'
                return None
            if not isinstance(answer, str) or not answer.strip():
                self.last_error = 'Groq: resposta sem texto.'
                return None
            self.last_error = ''
            return answer.strip()
        except Exception as exc:
            # Never log credentials, response bodies or private prompts.
            self.last_error = 'Groq: ' + type(exc).__name__
            self.retry_at = time.monotonic() + 30
            return None
        finally:
            self.last_latency['total_ms'] = round((time.perf_counter() - started) * 1000, 1)

    def generate_stream(self, system, history, text, *, chunk_callback=None):
        """Stream a text reply so voice playback can start before generation ends."""
        started = time.perf_counter()
        first_token_ms = None
        self.last_stream_text = ""
        self.last_latency = {'provider': 'groq:' + self.model, 'streaming': False}
        if not self.available:
            self.last_error = 'Groq: chave não configurada ou serviço desativado.'
            return None
        if time.monotonic() < self.retry_at:
            self.last_error = 'Groq: aguardando a próxima tentativa.'
            return None

        messages = [{'role': 'system', 'content': system}]
        for item in history[-10:]:
            if item.get('role') in ('user', 'assistant') and item.get('content'):
                messages.append({'role': item['role'], 'content': str(item['content'])[:1500]})
        messages.append({'role': 'user', 'content': str(text)})
        payload = {'model': self.model, 'messages': messages, 'stream': True,
                   'max_completion_tokens': 1200}
        if self.model.startswith('openai/gpt-oss-'):
            payload['reasoning_effort'] = 'low'

        finish_reason = ''
        response = None
        try:
            response = self.session.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + self.key},
                json=payload, stream=True, timeout=(3, self.timeout),
            )
            if response.status_code >= 400:
                labels = {401: 'chave inválida', 403: 'acesso negado', 404: 'modelo indisponível',
                          429: 'limite de uso atingido', 503: 'serviço indisponível'}
                self.last_error = f"Groq: HTTP {response.status_code} — {labels.get(response.status_code, 'pedido recusado')}"
                if response.status_code == 429:
                    try:
                        delay = max(1, min(3600, float(response.headers.get('retry-after', 60))))
                    except (ValueError, TypeError):
                        delay = 60
                    self.retry_at = time.monotonic() + delay
                elif response.status_code >= 500:
                    self.retry_at = time.monotonic() + 30
                return None

            for raw_line in response.iter_lines(chunk_size=1, decode_unicode=False):
                if not raw_line:
                    continue
                line = raw_line.decode('utf-8', errors='replace').strip() if isinstance(raw_line, bytes) else str(raw_line).strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if not data or data == '[DONE]':
                    continue
                try:
                    obj = json.loads(data)
                except (TypeError, ValueError):
                    continue
                choice = (obj.get('choices') or [{}])[0] or {}
                finish_reason = str(choice.get('finish_reason') or finish_reason)
                delta = choice.get('delta') or {}
                piece = delta.get('content', '')
                if isinstance(piece, list):
                    piece = ''.join(str(part.get('text', '')) for part in piece if isinstance(part, dict))
                if not isinstance(piece, str) or not piece:
                    continue
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - started) * 1000
                self.last_stream_text += piece
                if chunk_callback:
                    try:
                        chunk_callback(piece)
                    except Exception:
                        pass

            answer = self.last_stream_text.strip()
            if finish_reason != 'stop' or not answer:
                self.last_error = 'Groq: resposta em streaming incompleta.'
                return None
            self.last_error = ''
            return answer
        except Exception as exc:
            self.last_error = 'Groq: ' + type(exc).__name__
            self.retry_at = time.monotonic() + 30
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            self.last_latency = {
                'provider': 'groq:' + self.model,
                'first_chunk_ms': round(first_token_ms or (time.perf_counter() - started) * 1000, 1),
                'total_ms': round((time.perf_counter() - started) * 1000, 1),
                'streaming': bool(first_token_ms),
                'finish_reason': finish_reason or 'unknown',
            }
