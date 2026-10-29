"""Validated, independent preferences for the morning briefing."""
from app_paths import ROOT
import json
import math
from pathlib import Path

PATH = ROOT / 'config' / 'briefing_preferences.json'
ORDER = ['música', 'clima', 'agenda', 'pendências', 'mensagens', 'gmail', 'notícias']
SOURCES = ['g1', 'Agência Brasil']


def defaults():
    return dict(city=None, news_count=5, email_count=3, topics='', sources=SOURCES[:],
                order=ORDER[:], music_enabled=True, music_volume=15)


def validate(data):
    value = defaults(); value.update(data)
    for key, maximum in [('news_count', 15), ('email_count', 10), ('music_volume', 100)]:
        if type(value[key]) is not int or not 0 <= value[key] <= maximum:
            raise ValueError(f'Valor inválido para {key}: use de 0 a {maximum}.')
    if type(value['music_enabled']) is not bool:
        raise ValueError('Opção de música inválida.')
    if not isinstance(value['order'], list) or sorted(value['order']) != sorted(ORDER):
        raise ValueError('A ordem deve conter cada cartão uma única vez.')
    if not isinstance(value['sources'], list) or not value['sources'] or any(x not in SOURCES for x in value['sources']):
        raise ValueError('Escolha pelo menos uma fonte disponível.')
    if not isinstance(value['topics'], str) or len(value['topics']) > 250:
        raise ValueError('Use até 250 caracteres nos assuntos.')
    city = value['city']
    if city is not None:
        if not isinstance(city, dict) or not isinstance(city.get('label'), str) or not city['label'].strip():
            raise ValueError('Pesquise e selecione uma cidade.')
        for key, maximum in [('latitude', 90), ('longitude', 180)]:
            number = city.get(key)
            if type(number) not in (float, int) or not math.isfinite(number) or abs(number) > maximum:
                raise ValueError('Coordenadas da cidade inválidas.')
        value['city'] = {key: city[key] for key in ('label', 'latitude', 'longitude')}
    return {key: value[key] for key in defaults()}


def load(path=PATH):
    path = Path(path)
    if not path.exists(): return defaults()
    return validate(json.loads(path.read_text(encoding='utf-8')))


def save(data, path=PATH):
    value = validate(data); path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8'); temp.replace(path)
    return value


def find_cities(query):
    import requests
    query = query.strip()
    if len(query) < 2: raise ValueError('Digite pelo menos duas letras da cidade.')
    response = requests.get('https://geocoding-api.open-meteo.com/v1/search',
                            params={'name': query, 'count': 10, 'language': 'pt', 'format': 'json'}, timeout=(3, 8))
    response.raise_for_status()
    return [dict(label=', '.join(str(x[k]) for k in ('name', 'admin1', 'country') if x.get(k)),
                 latitude=x['latitude'], longitude=x['longitude']) for x in response.json().get('results', [])]
