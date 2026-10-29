"""Deterministic local lists and schedules, shared by voice, text and planner."""
from app_paths import ROOT
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import threading
import unicodedata
from uuid import uuid4


def fold(text):
    return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode().lower()


def canonical_schedule(text):
    text = str(text).strip()
    text = re.sub(r'^(?:(?:pode|poderia)\s+)?(?:me\s+(?:avisar|avise|avisa|lembrar)|avise(?:-me)?|avisa(?:-me)?)\b', 'me lembre', text, flags=re.I)
    text = re.sub(r'^(?:pode|poderia)\s+(me lembre|lembre-me)\b', r'\1', text, flags=re.I)
    return re.sub(r'[, ]*por favor[.!?]*$', '', text, flags=re.I).strip()


def merge_time_reply(request, reply):
    """Replace an incomplete/invalid time instead of accumulating conflicting times."""
    base = request
    # Remove clock-like fragments, including ASR/typing errors such as 14:#.
    base = re.sub(r'\b(?:(?:às?|as?)\s+)?\d{1,2}(?:[:h][^\s,;]*|\s+horas?)(?:\s+horas?)?', ' ', base, flags=re.I)
    base = re.sub(r'\b(?:às|as)\s+\d{1,2}\b', ' ', base, flags=re.I)
    base = re.sub(r'\b(?:daqui(?:\s+a)?|em)\s+(?:\d+|[a-zçãê]+(?: e [a-zçãê]+)?)\s+(?:segundos?|minutos?|horas?)\b', ' ', base, flags=re.I)
    if re.search(r'\b(?:hoje|amanha|depois de amanha|daqui|em)\b|\d{1,2}/\d{1,2}', fold(reply)):
        base = re.sub(r'\b(?:depois de amanh[ãa]|amanh[ãa]|hoje|(?:dia\s+)?\d{1,2}/\d{1,2}(?:/\d{4})?)\b', ' ', base, flags=re.I)
    answer = reply.strip()
    if re.fullmatch(r'\d{1,2}', answer):
        answer = 'às ' + answer + 'h'
    elif re.fullmatch(r'\d+\s+(?:segundos?|minutos?|horas?)', answer, flags=re.I):
        answer = 'em ' + answer
    return re.sub(r'\s+', ' ', base + ' ' + answer).strip()


def is_local_request(text):
    c = fold(canonical_schedule(text)).strip(' .!?')
    if re.search(r'\b(?:iphone|v mobile|celular)\b', c):
        return False
    if re.match(r'^(?:agende|agendar)\s+', c) or c.startswith('minha agenda') or re.fullmatch(r'o que tenho (?:para )?(?:hoje|amanha)', c):
        return True
    return bool(re.match(r'^(?:(?:crie|criar|cria|agende|agendar|marque|programe|coloque|cancele|cancelar|remova)\b.*\b(?:alarme|lembrete|compromisso|lista)\b|(?:me lembre|me lembra|lembre-me)\b|(?:agenda|alarme|lembrete|compromisso|lista|minhas listas|meus alarmes|meus lembretes|meus compromissos)\b|(?:mostre|mostrar|leia|ver|listar|liste|qual|quais|o que tenho)\b.*\b(?:agenda|compromissos|alarmes|lembretes|listas?)\b|(?:adicione|adicionar|inclua|conclua|marque como feito|retire)\b.*\blista\b)', c))


def parse_when(text, now):
    """Return (timestamp, title with time removed); never infer a missing hour."""
    c = fold(text)
    if re.search(r'\b(?:segunda|terca|quarta|quinta|sexta|sabado|domingo|proxima semana|semana que vem)\b', c):
        raise ValueError('Para esse dia, informe a data e o horário, por exemplo “02/10 às 15h”.')
    numbers = {'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'tres': 3, 'quatro': 4,
               'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10,
               'onze': 11, 'doze': 12, 'treze': 13, 'catorze': 14, 'quatorze': 14,
               'quinze': 15, 'dezesseis': 16, 'dezessete': 17, 'dezoito': 18, 'dezenove': 19,
               'vinte': 20, 'trinta': 30, 'quarenta': 40, 'cinquenta': 50, 'sessenta': 60}
    units = 'um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove'
    number_pattern = r'(?:(?:vinte|trinta|quarenta|cinquenta) e (?:' + units + r')|' + '|'.join(numbers) + r')'
    def number(value):
        return int(value) if value.isdigit() else numbers[value] if value in numbers else sum(numbers[x] for x in value.split(' e '))
    rel = re.search(r'\b(?:daqui(?: a)?|em)\s+(\d+|' + number_pattern + r')\s+(segundos?|minutos?|horas?)\b', c)
    if rel:
        token = rel.group(1)
        amount = number(token)
        if not 1 <= amount <= 10000:
            raise ValueError('Use um intervalo entre 1 e 10000 unidades.')
        unit = rel.group(2)
        seconds = amount * (3600 if unit.startswith('hora') else 60 if unit.startswith('minuto') else 1)
        end = rel.end()
        extra = re.match(r'\s+e\s+(\d+|' + number_pattern + r')\s+(minutos?|segundos?)\b', c[end:])
        if extra:
            extra_unit = extra.group(2)
            if not unit.startswith('hora') and not (unit.startswith('minuto') and extra_unit.startswith('segundo')):
                raise ValueError('Use um intervalo único, por exemplo “em 50 minutos”.')
            seconds += number(extra.group(1)) * (60 if extra_unit.startswith('minuto') else 1)
            end += extra.end()
        elif unit.startswith('hora'):
            half_extra = re.match(r'\s+e meia\b', c[end:])
            if half_extra:
                seconds += 1800
                end += half_extra.end()
        remaining = (text[:rel.start()] + ' ' + text[end:]).strip()
        if re.search(r'\b(?:amanha|depois de amanha)\b|\d{1,2}/\d{1,2}', fold(remaining)):
            raise ValueError('Você indicou uma data e um intervalo a partir de agora. Use só “daqui 30 minutos” ou uma data com horário.')
        remaining = re.sub(r'\bhoje\b', '', remaining, flags=re.I)
        return now + seconds, remaining.strip()
    half = re.search(r'\b(?:daqui(?: a)?|em)\s+meia hora\b', c)
    if half:
        return parse_when(text[:half.start()] + 'em 30 minutos' + text[half.end():], now)
    # Numeric hours transcribed with a space, and spoken hours such as "às duas e meia".
    spaced = re.search(r'(?<![\d:])\b(\d{1,2})\s+horas?\b', c)
    if spaced:
        return parse_when(text[:spaced.start()] + spaced.group(1) + 'h' + text[spaced.end():], now)
    words = re.search(r'\bas\s+(' + number_pattern + r')(?:\s+e\s+(meia|' + number_pattern + r'))?\b', c)
    if words:
        hour = number(words.group(1))
        minute = 30 if words.group(2) == 'meia' else number(words.group(2)) if words.group(2) else 0
        return parse_when(text[:words.start()] + f'às {hour:02d}:{minute:02d}' + text[words.end():], now)
    clock = re.search(r'\b(?:as?\s+)(\d{1,2})(?:[:h](\d{0,2}))?(?:\s*horas?)?\b(?![:h\d])|\b(\d{1,2})[:h](\d{0,2})\b(?![:h\d])', c)
    if not clock:
        raise ValueError('Qual horário? Use, por exemplo, “amanhã às 15h” ou “em 10 minutos”.')
    hour = int(clock.group(1) or clock.group(3))
    minute = int(clock.group(2) or clock.group(4) or 0)
    period = re.search(r'^\s+(?:da|a|de)\s+(manha|tarde|noite)\b', c[clock.end():])
    if period:
        if not 1 <= hour <= 12:
            raise ValueError('Com manhã, tarde ou noite, use uma hora entre 1 e 12.')
        hour = hour % 12 if period.group(1) == 'manha' else hour % 12 + 12
    if hour > 23 or minute > 59:
        raise ValueError('Use um horário válido, entre 00:00 e 23:59.')
    current = datetime.fromtimestamp(now)
    day = current.date()
    explicit = False
    spans = [(clock.start(), clock.end() + (period.end() if period else 0))]
    dated = re.search(r'\b(?:dia\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', c)
    relative_day = re.search(r'\b(depois de amanha|amanha|hoje)\b', c)
    if dated:
        try:
            day = datetime(int(dated.group(3) or current.year), int(dated.group(2)), int(dated.group(1))).date()
        except ValueError:
            raise ValueError('Essa data não existe. Use dia/mês/ano.') from None
        spans.append(dated.span()); explicit = True
    elif relative_day:
        offset = {'hoje': 0, 'amanha': 1, 'depois de amanha': 2}[relative_day.group(1)]
        day += timedelta(days=offset)
        spans.append(relative_day.span()); explicit = True
    due = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute).timestamp()
    if due <= now and not explicit:
        due = (datetime.fromtimestamp(due) + timedelta(days=1)).timestamp()
    if due <= now:
        raise ValueError('Esse horário já passou. Informe uma data e um horário futuros.')
    title = text
    for start, end in sorted(spans, reverse=True):
        title = title[:start] + ' ' + title[end:]
    return due, re.sub(r'\s+', ' ', title).strip()


class ListStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else ROOT / 'data/lists.json'
        self.lock = threading.RLock()

    def load(self):
        if not self.path.exists():
            return {'lists': {}}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('lists'), dict):
            raise ValueError('Arquivo de listas inválido; os dados foram preservados.')
        for value in data['lists'].values():
            if not isinstance(value, dict) or not isinstance(value.get('items'), list) or not isinstance(value.get('name'), str):
                raise ValueError('Arquivo de listas inválido; os dados foram preservados.')
            for item in value['items']:
                if not isinstance(item, dict) or not isinstance(item.get('text'), str) or type(item.get('done')) is not bool or not isinstance(item.get('id'), str):
                    raise ValueError('Arquivo de listas inválido; os dados foram preservados.')
        return data

    def save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.path)

    def execute(self, action, name='', item=''):
        name, item = name.strip(' .!?'), item.strip(' .!?')
        if len(name) > 80 or len(item) > 240:
            raise ValueError('Use até 80 caracteres no nome da lista e 240 no item.')
        key = fold(name)
        with self.lock:
            data = self.load()
            lists = data['lists']
            if action == 'all':
                return 'Suas listas: ' + ', '.join(x['name'] for x in lists.values()) if lists else 'Você ainda não tem listas.'
            if not name:
                raise ValueError('Informe o nome da lista.')
            if action in ('create', 'add'):
                lists.setdefault(key, {'name': name, 'items': []})
            if key not in lists:
                raise ValueError(f'A lista “{name}” não existe.')
            target = lists[key]
            if action == 'show':
                rows = [f"{'✓' if x['done'] else '○'} {x['text']}" for x in target['items']]
                return f"Lista {target['name']}:\n" + ('\n'.join(rows) or 'Nenhum item.')
            if action == 'create':
                message = f'Lista “{name}” pronta.'
            elif action == 'add':
                if not item:
                    raise ValueError('Informe o item que deseja adicionar.')
                if any(fold(x['text']) == fold(item) and not x['done'] for x in target['items']):
                    return f'“{item}” já está pendente na lista {name}.'
                target['items'].append({'id': uuid4().hex, 'text': item, 'done': False})
                message = f'Adicionei “{item}” à lista {name}.'
            else:
                found = [x for x in target['items'] if fold(x['text']) == fold(item) and not x['done']]
                if len(found) != 1:
                    raise ValueError('Não encontrei um único item pendente com esse nome. Consulte a lista e use o texto completo.')
                if action == 'done':
                    found[0]['done'] = True
                    message = f'Concluí “{item}” na lista {name}.'
                else:
                    target['items'].remove(found[0])
                    message = f'Removi “{item}” da lista {name}.'
            self.save(data)
            return message


class PersonalAssistant:
    def __init__(self, initiative, lists=None, clock=None):
        import time
        self.initiative = initiative
        self.lists = lists or ListStore()
        self.clock = clock or time.time

    def execute(self, text):
        raw = canonical_schedule(text).strip(' .!?')
        c = fold(raw)
        now = self.clock()
        m = re.fullmatch(r'(?:crie|criar|cria) (?:uma |a )?lista (.+)', c)
        if m:
            return self.lists.execute('create', raw[m.start(1):m.end(1)])
        m = re.fullmatch(r'(adicione|adicionar|inclua|coloque|conclua|marque como feito|remova|retire) (.+?) (?:na|a|da) lista (.+)', c)
        if m:
            action = 'done' if m.group(1) in ('conclua', 'marque como feito') else 'remove' if m.group(1) in ('remova', 'retire') else 'add'
            return self.lists.execute(action, raw[m.start(3):m.end(3)], raw[m.start(2):m.end(2)])
        if re.fullmatch(r'(?:minhas listas|(?:mostre|listar|liste) (?:as )?(?:minhas )?listas)', c):
            return self.lists.execute('all')
        m = re.fullmatch(r'(?:(?:mostre|mostrar|leia|ver) (?:a |minha )?)?lista (.+)', c)
        if m:
            return self.lists.execute('show', raw[m.start(1):m.end(1)])
        m = re.fullmatch(r'(?:cancele|cancelar|remova) (?:o )?(alarme|lembrete|compromisso) (.+)', c)
        if m:
            kind = {'alarme': 'alarms', 'lembrete': 'reminders', 'compromisso': 'appointments'}[m.group(1)]
            query = m.group(2)
            matches = [e for e in self.initiative.snapshot()['events'] if e['kind'] == kind and (e['state'] == 'pending' or kind == 'appointments' and e['state'] == 'delivered' and e['due'] > now)
                       and (fold(e['title']) == query or (len(query) >= 6 and e['id'].startswith(query)))]
            if len(matches) != 1:
                raise ValueError('Não encontrei um único aviso. Consulte a agenda e use o código mostrado.')
            self.initiative.change_event(matches[0]['id'])
            return f"Cancelei: {matches[0]['title']}."
        is_query = (not re.match(r'^(?:crie|criar|agende|agendar|marque|programe|coloque|me lembre|me lembra|lembre-me)', c)
                    and (bool(re.search(r'\b(?:agenda|compromissos|alarmes|lembretes)\b', c)) or bool(re.fullmatch(r'o que tenho (?:para )?(?:hoje|amanha)', c))))
        if is_query:
            date = datetime.fromtimestamp(now).date()
            target = date + timedelta(days=1) if 'amanha' in c else date if 'hoje' in c else None
            kinds = {'alarms'} if 'alarmes' in c else {'reminders'} if 'lembretes' in c else {'alarms', 'reminders', 'appointments'}
            events = [e for e in self.initiative.snapshot()['events'] if e['kind'] in kinds and (e['state'] == 'pending' or e['kind'] == 'appointments' and e['state'] == 'delivered' and (target is not None or e['due'] > now))
                      and (target is None or datetime.fromtimestamp(e['due']).date() == target)]
            rows = []
            for e in sorted(events, key=lambda x: x['due']):
                when = datetime.fromtimestamp(e['due']).strftime('%d/%m/%Y às %H:%M')
                kind = {'alarms': 'Alarme', 'reminders': 'Lembrete', 'appointments': 'Compromisso'}[e['kind']]
                rows.append(f"{when} · {kind}: {e['title']} [{e['id'][:8]}]" + (' · vencido' if e['due'] <= now else ''))
            return 'Sua agenda local:\n' + '\n'.join(rows) if rows else 'Nenhum aviso pendente nesse período na agenda local.'
        if re.search(r'\b(?:alarme|lembrete|compromisso|me lembre|me lembra|lembre-me)\b', c) or re.match(r'^(?:agende|agendar)\s+', c):
            if re.search(r'\b(?:todo dia|todos os dias|diariamente|semanalmente|toda semana|repita|toda segunda|toda terca|toda quarta|toda quinta|toda sexta)\b', c):
                raise ValueError('A agenda local ainda usa avisos únicos. Informe uma data e um horário para este aviso.')
            kind = 'alarms' if re.search(r'\balarme\b', c) else 'appointments' if 'compromisso' in c or re.match(r'^(?:agende|agendar)\s+(?!(?:um |o )?lembrete\b)', c) else 'reminders'
            due, title = parse_when(raw, now)
            title = re.sub(r'^(?:(?:crie|criar|agende|agendar|marque|programe|coloque)\s+(?:um |o )?(?:alarme|lembrete|compromisso)|me lembre|me lembra|lembre-me|alarme|lembrete|compromisso)\s*', '', title, flags=re.I)
            title = re.sub(r'^(?:agende|agendar)\s+', '', title, flags=re.I)
            title = re.sub(r'\bquando\s+(?:for|der|chegar(?: a hora)?)\b|\bhoras?\s*$', '', title, flags=re.I)
            title = re.sub(r'^(?:(?:para|de|que|sobre)\s+)+|\s+(?:para|de)$', '', title, flags=re.I).strip(' ,.;:')
            if not title:
                if kind in ('alarms', 'reminders'):
                    title = 'Alarme' if kind == 'alarms' else 'Aviso de horário'
                else:
                    raise ValueError('Qual é o assunto do aviso? Exemplo: “me lembre de revisar o projeto amanhã às 15h”.')
            event = self.initiative.add(title, due, kind=kind, now=now)
            label = {'alarms': 'Alarme', 'reminders': 'Lembrete', 'appointments': 'Compromisso'}[kind]
            when = datetime.fromtimestamp(due).strftime('%d/%m/%Y às %H:%M')
            return f"{label} salvo no PC para {when}: {title}. Código {event['id'][:8]}. O V precisa estar aberto." + (' Vou avisar 10 minutos antes, respeitando os limites de iniciativa.' if kind == 'appointments' else '')
        raise ValueError('Use: “adicione leite à lista compras”, “agenda de hoje” ou “me lembre de revisar o projeto em 10 minutos”.')
