from __future__ import annotations

import json
import threading
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


def _norm(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(s.split()).strip(" .,!?:;-—–")


@dataclass
class MemoryItem:
    id: int
    text: str
    created_at: str
    source: str = "explicit"
    category: str = "geral"
    updated_at: str = ""


class PersistentMemoryStore:
    """Memória local explícita do V.

    Só grava fatos quando o usuário usa comandos como "lembre que...". O arquivo
    fica dentro da própria pasta do V e pode ser inspecionado pelo usuário.
    """
    def __init__(self, path: str | Path, max_items: int = 200):
        self.path = Path(path)
        self.max_items = max(10, int(max_items))
        self._lock = threading.RLock()
        self._items: list[MemoryItem] = []
        self._next_id = 1
        self._load()

    def _load(self):
        with self._lock:
            self._load_error = False
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"memories": []}
                if not isinstance(raw, dict) or not isinstance(raw.get('memories', []), list):
                    raise ValueError('invalid_memory_file')
                int(raw.get('next_id', 1))
            except Exception:
                self._load_error = True
                raw = {"memories": []}
            items=[]
            for obj in raw.get("memories", []):
                try:
                    items.append(MemoryItem(int(obj.get("id", 0)), str(obj.get("text", "")).strip(), str(obj.get("created_at", "")), str(obj.get("source", "explicit")), obj.get('category', 'geral'), obj.get('updated_at', '')))
                except Exception:
                    self._load_error = True
            self._items=[x for x in items if x.text]
            self._next_id = max(max((x.id for x in self._items), default=0) + 1, int(raw.get('next_id', 1)))

    def _save(self):
        if self._load_error:
            raise ValueError('Arquivo de memória ilegível. A gravação foi bloqueada para preservar os dados; repare ou restaure o arquivo antes de reiniciar o V.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload={"version": 2, "next_id": self._next_id, "memories": [asdict(x) for x in self._items]}
        tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.path)

    def remember(self, text: str, source: str = "explicit", category: str = "geral") -> MemoryItem | None:
        value=" ".join(str(text or "").split()).strip(" .")
        if not value:
            return None
        self._validate(value, category)
        n=_norm(value)
        with self._lock:
            for item in self._items:
                if _norm(item.text)==n:
                    return item
            if len(self._items) >= self.max_items:
                raise ValueError('Limite de memórias atingido. Corrija ou esqueça uma memória antes de adicionar outra; nada foi apagado.')
            next_id=self._next_id
            self._next_id += 1
            item=MemoryItem(next_id, value, datetime.now(timezone.utc).isoformat(), source, category)
            previous = self._items[:]
            self._items.append(item)
            self._items=self._items[-self.max_items:]
            try:
                self._save()
            except Exception:
                self._items = previous
                raise
            return item

    @staticmethod
    def _validate(text, category):
        if not text.strip() or len(text) > 1000:
            raise ValueError('Use entre 1 e 1000 caracteres por memória.')
        if category not in ('geral', 'preferencias', 'equipamentos', 'projetos', 'rotinas'):
            raise ValueError('Categoria de memória inválida.')

    def update(self, item_id, text, category=None):
        value = ' '.join(str(text).split()).strip()
        with self._lock:
            item = next((x for x in self._items if x.id == int(item_id)), None)
            if item is None:
                raise ValueError('Memória não encontrada; atualize a lista.')
            category = item.category if category is None else category
            self._validate(value, category)
            old = (item.text, item.category, item.updated_at)
            item.text, item.category = value, category
            item.updated_at = datetime.now(timezone.utc).isoformat()
            try:
                self._save()
            except Exception:
                item.text, item.category, item.updated_at = old
                raise
            return item

    def forget_id(self, item_id):
        with self._lock:
            for index, item in enumerate(self._items):
                if item.id == int(item_id):
                    self._items.pop(index)
                    try:
                        self._save()
                    except Exception:
                        self._items.insert(index, item)
                        raise
                    return item
            raise ValueError('Memória não encontrada; atualize a lista.')

    def relevant(self, query='', limit=24, max_chars=6000):
        """Bounded local retrieval: facts are data, never executable instructions."""
        ignored = {'que', 'para', 'com', 'uma', 'meu', 'minha', 'voce', 'como', 'quero'}
        words = {w for w in _norm(query).split() if len(w) > 2} - ignored
        with self._lock:
            ranked = sorted(enumerate(self._items), key=lambda pair: (
                len(words & set(_norm(pair[1].text + ' ' + pair[1].category).split())), pair[0]), reverse=True)
            result = []
            remaining = max_chars
            for _, item in ranked[:limit]:
                value = f'[{item.category} #{item.id}] {item.text}'
                if len(value) <= remaining:
                    result.append(value)
                    remaining -= len(value)
            return result

    def forget(self, query: str) -> MemoryItem | None:
        q=_norm(query)
        if not q:
            return None
        with self._lock:
            # exact first; then substring for natural phrases.
            idx=None
            for i,item in enumerate(self._items):
                if _norm(item.text)==q:
                    idx=i; break
            if idx is None:
                matches=[(i,item) for i,item in enumerate(self._items) if q in _norm(item.text) or _norm(item.text) in q]
                if len(matches)==1:
                    idx=matches[0][0]
            if idx is None:
                return None
            item=self._items.pop(idx)
            try:
                self._save()
            except Exception:
                self._items.insert(idx, item)
                raise
            return item

    def get_memories(self) -> list[str]:
        with self._lock:
            return [x.text for x in self._items]

    def items(self) -> list[dict]:
        with self._lock:
            return [asdict(x) for x in self._items]

    def count(self) -> int:
        with self._lock:
            return len(self._items)
