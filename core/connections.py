"""Read-only connection probes. Results never include credentials or message bodies."""
from dataclasses import dataclass, asdict
from datetime import datetime
import imaplib
import requests
from contextlib import closing


@dataclass
class ConnectionResult:
    name: str
    configured: bool
    state: str
    checked_at: str
    detail: str
    next_action: str


NAMES = ('Gmail', 'Spotify', 'Mensagens', 'IA · Gemini', 'IA · Groq', 'IA · Ollama', 'Remoto')
ACTIONS = {
    'Gmail': 'Abra Configurar Gmail; confira endereço, senha de app e acesso à internet.',
    'Spotify': 'Abra o Spotify no PC e confira a extensão Spicetify Bridge ou configure a API Spotify.',
    'Mensagens': 'Ative notificações do WhatsApp/Instagram no Windows e envie uma mensagem de teste pelo seu celular.',
    'IA · Gemini': 'Confira a chave e o modelo em configurar_gemini.bat; verifique a cota da conta.',
    'IA · Groq': 'Confira a chave, o modelo e a cota do Groq nas configurações da IA.',
    'IA · Ollama': 'Inicie o Ollama e instale o modelo configurado no V.',
    'Remoto': 'Abra o V pelo inicializador Dual e confira o painel de pareamento remoto.',
}


def configured(name, brain=None, remote=None):
    if name == 'Gmail':
        from integrations.gmail_reader import load_account
        return bool(load_account())
    if name == 'Spotify':
        from spotify_bridge import _cfg
        from spotify_api import load_spotify_config
        return bool(_cfg().get('enabled', True) or load_spotify_config().get('client_id'))
    if name == 'Mensagens':
        from windows_notification_reader import WindowsPhoneNotificationReader
        return WindowsPhoneNotificationReader().available
    if name == 'Remoto':
        return bool(remote and remote.get('server'))
    if brain is None:
        return False
    return bool({'IA · Gemini': brain._gemini_allowed,
                 'IA · Groq': brain._groq_allowed,
                 'IA · Ollama': brain._ollama_allowed}[name]())


def http_json(url, **kwargs):
    with requests.get(url, timeout=(3, 6), **kwargs) as response:
        response.raise_for_status()
        return response.json()


def probe(name, brain=None, remote=None):
    ready = False
    next_action = 'Use a função no V para validar o fluxo completo; teste novamente se houver falha.'
    try:
        ready = configured(name, brain, remote)
        if not ready:
            return ConnectionResult(name, False, 'Não configurado', datetime.now().astimezone().isoformat(timespec='seconds'),
                                    'Configuração ausente ou serviço desativado.', ACTIONS[name])
        if name == 'Gmail':
            from integrations.gmail_reader import GmailReader
            with GmailReader().connection() as (client, _, __):
                if client.noop()[0] != 'OK':
                    raise RuntimeError('imap_noop')
            detail = 'Login e caixa de entrada confirmados, somente leitura. Nenhum e-mail lido.'
        elif name == 'Spotify':
            from spotify_bridge import health
            code, data = health()
            age = data.get('extension_age_s')
            if code == 200 and data.get('extension_seen') and isinstance(age, (int, float)) and 0 <= age < 15:
                detail = 'Bridge respondeu e a extensão enviou sinal há menos de 15 segundos. Reprodução não alterada.'
            else:
                from spotify_api import SpotifyClient
                client = SpotifyClient()
                client.timeout = 6
                devices = client.devices()
                detail = f'API autenticada; {len(devices)} dispositivo(s) disponível(is). Reprodução não testada.'
                if not devices:
                    next_action = 'Abra o Spotify no PC, aguarde aparecer como dispositivo e teste novamente.'
        elif name == 'Mensagens':
            from windows_notification_reader import WindowsPhoneNotificationReader
            reader = WindowsPhoneNotificationReader()
            with closing(reader._connect()) as connection:
                connection.execute('SELECT COUNT(*) FROM Notification').fetchone()
            detail = 'Leitor local do Windows acessível. Isto não confirma login nem recebimento novo no WhatsApp/Instagram.'
        elif name == 'IA · Gemini':
            http_json(f'{brain.gemini_base_url}/models/{brain.gemini_model}', headers={'x-goog-api-key': brain.gemini_key})
            detail = 'API autenticada e modelo acessível. Geração e cota de geração não testadas.'
        elif name == 'IA · Groq':
            data = http_json('https://api.groq.com/openai/v1/models', headers={'Authorization': 'Bearer ' + brain.groq.key})
            if brain.groq.model not in {item.get('id') for item in data.get('data', [])}:
                raise LookupError('model_missing')
            detail = 'API autenticada e modelo acessível. Geração e cota de geração não testadas.'
        elif name == 'IA · Ollama':
            data = http_json(brain.base_url + '/api/tags')
            models = {x.get('name') for x in data.get('models', [])}
            if brain.model not in models and brain.model + ':latest' not in models:
                raise LookupError('model_missing')
            detail = 'Servidor respondeu e modelo instalado. Modelo não carregado na GPU pelo teste.'
        else:
            from urllib.parse import urlparse
            port = urlparse(remote.get('url', '')).port
            if not port:
                raise LookupError('remote_endpoint_missing')
            data = http_json(f'http://127.0.0.1:{port}/api/meta')
            if data.get('access_mode') != 'local':
                raise ValueError('invalid_remote_response')
            detail = 'Servidor remoto local respondeu. O pareamento do celular é testado no próprio celular, na mesma rede.'
        return ConnectionResult(name, True, 'Conectado', datetime.now().astimezone().isoformat(timespec='seconds'), detail, ACTIONS[name] if name == 'Mensagens' else next_action)
    except Exception as exc:
        # Never render raw exceptions: URLs/bodies may contain API keys or tokens.
        if isinstance(exc, requests.HTTPError):
            code = exc.response.status_code if exc.response is not None else 0
            message = f'HTTP {code}: ' + {401: 'credencial recusada.', 403: 'acesso negado.', 404: 'modelo ou endereço não encontrado.', 429: 'limite de uso atingido.'}.get(code, 'serviço recusou o teste.')
        elif isinstance(exc, (requests.Timeout, TimeoutError)):
            message = 'Tempo limite excedido; serviço não respondeu.'
        elif isinstance(exc, imaplib.IMAP4.error):
            message = 'Gmail recusou a autenticação ou a consulta IMAP.'
        elif isinstance(exc, LookupError):
            message = 'Modelo ou endereço do serviço não disponível na configuração atual.'
        else:
            message = f'Falha de conexão ou resposta inválida ({type(exc).__name__}).'
        return ConnectionResult(name, ready, 'Indisponível', datetime.now().astimezone().isoformat(timespec='seconds'), message, ACTIONS[name])
