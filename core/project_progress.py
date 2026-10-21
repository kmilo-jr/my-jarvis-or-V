"""Explicit project checkpoints with atomic storage and editable fields."""
import json
import re
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if unicodedata.category(c) != 'Mn').strip()


class ProjectStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / 'data' / 'project_progress.json'
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            if not self.path.exists():
                return {'active': None, 'projects': {}}
            try:
                data = json.loads(self.path.read_text(encoding='utf-8'))
                assert isinstance(data, dict) and isinstance(data['projects'], dict)
                assert data['active'] is None or data['active'] in data['projects']
                for key, item in data['projects'].items():
                    assert isinstance(item, dict)
                    assert all(isinstance(item[field], str) for field in ('name', 'done', 'pending', 'next', 'updated'))
                    assert key == normalized(item['name']) and item['name'].strip()
                return data
            except (ValueError, KeyError, TypeError, AssertionError):
                raise ValueError('Registro de projetos inválido. O arquivo foi preservado.') from None

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.path)

    def save(self, name, done='', pending='', next_step=''):
        values = [str(x).strip() for x in (name, done, pending, next_step)]
        if not values[0] or len(values[0]) > 100 or any(len(x) > 3000 for x in values[1:]):
            raise ValueError('Informe um nome de até 100 caracteres e campos de até 3000 caracteres.')
        with self.lock:
            data = self.read()
            key = normalized(values[0])
            if key not in data['projects'] and len(data['projects']) >= 100:
                raise ValueError('Limite de 100 projetos. Esqueça um projeto para adicionar outro.')
            data['projects'][key] = dict(zip(('name', 'done', 'pending', 'next'), values),
                                         updated=datetime.now().astimezone().isoformat(timespec='seconds'))
            data['active'] = key
            self._save(data)
            return data['projects'][key]

    def select(self, name):
        with self.lock:
            data = self.read()
            key = normalized(name)
            if key not in data['projects']:
                raise ValueError('Projeto não encontrado. Abra Projetos para criar ou escolher um.')
            data['active'] = key
            self._save(data)
            return data['projects'][key]

    def forget(self, name):
        with self.lock:
            data = self.read()
            key = normalized(name)
            if key not in data['projects']:
                raise ValueError('Projeto não encontrado.')
            del data['projects'][key]
            if data['active'] == key:
                data['active'] = None
            self._save(data)

    def active(self):
        data = self.read()
        return data['projects'].get(data['active'])

    @staticmethod
    def summary(item):
        if not item:
            return 'Nenhum projeto ativo. Abra Projetos ou diga: criar projeto seguido do nome.'
        return (f"Projeto {item['name']}.\nConcluído: {item['done'] or 'não registrado'}.\n"
                f"Pendente: {item['pending'] or 'não registrado'}.\n"
                f"Próximo passo: {item['next'] or 'não registrado'}.")

    def command(self, text):
        text = text.strip().rstrip('.!?')
        n = normalized(text)
        if n in ('continua de onde paramos', 'continue de onde paramos', 'onde paramos', 'status do projeto'):
            return self.summary(self.active())
        if n in ('listar projetos', 'meus projetos'):
            return 'Projetos: ' + (', '.join(p['name'] for p in self.read()['projects'].values()) or 'nenhum salvo')
        match = re.match(r'^(criar projeto|retomar projeto|esquecer projeto)\s+(.+)$', text, re.I)
        if match:
            action, name = match.groups()
            if action.lower() == 'esquecer projeto':
                self.forget(name)
                return 'Projeto esquecido.'
            if action.lower() == 'retomar projeto':
                return self.summary(self.select(name))
            if normalized(name) in self.read()['projects']:
                return self.summary(self.select(name))
            return self.summary(self.save(name))
        match = re.match(r'^(?:no projeto,?\s+)?(concluído|concluido|pendente|próximo passo|proximo passo)(?:\s*:\s*|\s+)(.+)$', text, re.I)
        if match:
            item = self.active()
            if not item:
                return self.summary(None)
            field = {'concluido': 'done', 'pendente': 'pending', 'proximo passo': 'next'}[normalized(match[1])]
            item[field] = match[2]
            self.save(item['name'], item['done'], item['pending'], item['next'])
            return 'Registro atualizado. ' + self.summary(item)
        return None
