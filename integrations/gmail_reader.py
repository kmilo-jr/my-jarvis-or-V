"""Gmail IMAP reader. No send, delete, or mark-as-read operations."""
import base64
from contextlib import contextmanager
from email import policy
from email.parser import BytesParser
import imaplib
import json
import os
from pathlib import Path
import re
import ssl

from secure_store import SecureStoreError, protect_bytes, unprotect_bytes
from vlog import get_logger

ACCOUNT_PATH = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'VAssistant' / 'gmail.json'

log = get_logger(__name__)


def save_account(address, password, path=ACCOUNT_PATH):
    address = address.strip(); password = password.replace(' ', '').strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', address) or not re.fullmatch(r'[a-zA-Z]{16}', password):
        raise ValueError('Informe seu e-mail e uma senha de app do Google com 16 letras.')
    payload = json.dumps({'address': address, 'password': password}).encode('utf-8')
    try:
        encrypted = protect_bytes(payload, 'V Gmail')
    except SecureStoreError as exc:
        log.warning('nao foi possivel proteger a conta do Gmail com DPAPI: %s', type(exc).__name__)
        raise RuntimeError(
            'Nao foi possivel salvar a senha do Gmail com seguranca: o DPAPI do Windows '
            'nao esta disponivel. Nada foi gravado. Instale/reinstale o pywin32 no .venv.'
        ) from exc
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(base64.b64encode(encrypted).decode('ascii'), encoding='ascii'); temp.replace(path)


def load_account(path=ACCOUNT_PATH):
    try:
        encrypted = base64.b64decode(Path(path).read_text(encoding='ascii'))
        return json.loads(unprotect_bytes(encrypted, 'V Gmail'))
    except SecureStoreError as exc:
        log.warning('nao foi possivel desproteger a conta do Gmail: %s', type(exc).__name__)
        return None
    except Exception as exc:
        log.warning('falha ao ler a conta do Gmail: %s', type(exc).__name__)
        return None


def mail_request(text):
    from core.functional_engine import normalize, strip_wake_word
    text = normalize(strip_wake_word(text)).replace('e-mails', 'emails').replace('e-mail', 'email')
    text = re.sub(r' (?:pra mim|para mim|por favor)$', '', text)
    if re.fullmatch(r'(?:leia|ler|liste|listar|mostre|ver)(?: os| meus| os meus)? emails(?: do gmail)?(?: nao lidos)?', text):
        return ('list', 'nao lidos' in text)
    match = re.fullmatch(r'(?:leia|ler|abra|abrir)(?: o)? email (?:numero )?([1-5]|um|dois|tres|quatro|cinco|primeiro|segundo|terceiro|quarto|quinto)', text)
    if match:
        numbers = {'um':1,'dois':2,'tres':3,'quatro':4,'cinco':5,'primeiro':1,'segundo':2,'terceiro':3,'quarto':4,'quinto':5}
        return ('read', numbers.get(match[1], int(match[1]) if match[1].isdigit() else 1))
    return None


def parse_message(raw):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    part = message.get_body(preferencelist=('plain', 'html'))
    text = ''
    if part is not None:
        try:
            text = part.get_content()
        except (LookupError, UnicodeError):
            text = (part.get_payload(decode=True) or b'').decode('utf-8', 'replace')
        if part.get_content_type() == 'text/html':
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, 'html.parser')
            for tag in soup(['script', 'style', 'head']): tag.decompose()
            text = soup.get_text(' ', strip=True)
    text = re.sub(r'[ \t]+', ' ', str(text)).strip()
    return {'title': str(message.get('Subject', '(sem assunto)')),
            'sender': str(message.get('From', '(remetente desconhecido)')), 'body': text}


class GmailReader:
    def __init__(self, account_loader=load_account, client_factory=imaplib.IMAP4_SSL):
        self.account_loader = account_loader; self.client_factory = client_factory
        self.snapshot = []; self.validity = None; self.address = None

    @contextmanager
    def connection(self):
        account = self.account_loader()
        if not account:
            raise ValueError('Configure o Gmail em Controles → Gmail no V Orbital.')
        client = self.client_factory('imap.gmail.com', 993, ssl_context=ssl.create_default_context(), timeout=12)
        try:
            client.login(account['address'], account['password'])
            if client.select('INBOX', readonly=True)[0] != 'OK':
                raise ValueError('Não consegui abrir a caixa de entrada.')
            validity = client.response('UIDVALIDITY')[1]
            yield client, account['address'], validity
        finally:
            try: client.logout()
            except Exception: pass

    @staticmethod
    def fetch(client, uid, fields):
        status, data = client.uid('fetch', uid, fields)
        if status != 'OK': raise ValueError('Não consegui ler a mensagem. Atualize a lista de e-mails.')
        return next((part[1] for part in data if isinstance(part, tuple)), b'')

    def list_recent(self, unread=False):
        self.snapshot = []
        with self.connection() as (client, address, validity):
            status, data = client.uid('search', None, 'UNSEEN' if unread else 'ALL')
            if status != 'OK': raise ValueError('Não consegui consultar a caixa de entrada.')
            uids = (data[0] or b'').split()[-5:][::-1]
            items = []
            for uid in uids:
                raw = self.fetch(client, uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                if not raw: continue
                items.append(parse_message(raw)); self.snapshot.append(uid)
            self.address, self.validity = address, validity
        if not items:
            return 'Não há e-mails não lidos na caixa de entrada.' if unread else 'A caixa de entrada está vazia.'
        return '\n\n'.join(f"{i+1}. De {item['sender']}. Assunto: {item['title']}." for i, item in enumerate(items)) + '\n\nDiga “V, leia o e-mail 1” para ouvir o conteúdo.'

    def read(self, number):
        if not 1 <= number <= len(self.snapshot):
            raise ValueError('Peça “V, liste meus e-mails” primeiro e escolha um número da lista.')
        with self.connection() as (client, address, validity):
            if address != self.address or validity != self.validity:
                self.snapshot = []
                raise ValueError('A caixa de entrada mudou. Peça para listar os e-mails novamente.')
            raw = self.fetch(client, self.snapshot[number-1], '(BODY.PEEK[]<0.262144>)')
        if not raw: raise ValueError('Essa mensagem não está mais disponível. Atualize a lista.')
        item = parse_message(raw)
        body = item['body'] or 'Esta mensagem não contém texto legível. Consulte os anexos no Gmail.'
        if len(body) > 6000 or len(raw) >= 262144:
            body = body[:6000] + '\n\nLeitura parcial. Abra o Gmail para ver a mensagem completa.'
        return f"De {item['sender']}. Assunto: {item['title']}.\n\n{body}"

    def morning_messages(self, count=3):
        """Fetch only headers for the configured number of newest unread messages."""
        count = max(0, min(10, int(count)))
        if count == 0: return []
        items = []
        with self.connection() as (client, address, validity):
            status, data = client.uid('search', None, 'UNSEEN')
            if status != 'OK':
                raise ValueError('Não consegui consultar a caixa de entrada.')
            for uid in (data[0] or b'').split()[-count:][::-1]:
                raw = self.fetch(client, uid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                if not raw:
                    continue
                item = parse_message(raw)
                items.append({'sender': item['sender'], 'title': item['title']})
        return items

    def execute(self, request):
        try:
            return True, self.list_recent(request[1]) if request[0] == 'list' else self.read(request[1])
        except ValueError as exc:
            return False, str(exc)
        except imaplib.IMAP4.error:
            return False, 'O Gmail recusou a conexão. Confira a senha de app e o acesso IMAP da conta em Controles → Gmail.'
        except Exception:
            return False, 'Não consegui acessar o Gmail agora. Verifique a conexão e tente novamente.'
