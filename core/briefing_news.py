"""Fresh publisher feeds, persistent rotation and preloaded article photos."""
import base64
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

FEEDS = [('g1', 'https://g1.globo.com/rss/g1/'),
         ('Agência Brasil', 'https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml')]
HISTORY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'briefing_news_seen.json'
_lock = threading.Lock()


def parse_feed(content, source):
    items = []
    for node in ET.fromstring(content).findall('./channel/item')[:40]:
        title, url = node.findtext('title', '').strip(), node.findtext('link', '').strip()
        if not title or not url.startswith(('https://', 'http://')): continue
        description = BeautifulSoup(node.findtext('description', ''), 'html.parser')
        image = node.findtext('imagem-destaque', '').strip()
        for child in node.iter():
            if not image and child.tag.rsplit('}', 1)[-1] in ('content', 'thumbnail', 'enclosure'):
                if child.attrib.get('medium') == 'image' or 'image' in child.attrib.get('type', '') or child.tag.endswith('thumbnail'):
                    image = child.attrib.get('url', '')
        if not image:
            tag = description.find('img')
            image = str(tag.get('src', '')) if tag else ''
        subtitle = next((child.text for child in node if child.tag.endswith('}subtitle')), '')
        snippet = subtitle or description.get_text(' ', strip=True)
        items.append(dict(title=title, url=url, source=source, snippet=snippet[:420],
                          published=node.findtext('pubDate', ''), image_url=image))
    return items


def fetch_feed(spec):
    source, url = spec
    try:
        response = requests.get(url, timeout=(3, 8), headers={'User-Agent':'V-Assistant/1.0', 'Cache-Control':'no-cache'})
        response.raise_for_status()
        return parse_feed(response.content, source)
    except Exception:
        return []


def identity(item):
    url = urlsplit(item['url'])
    key = urlunsplit((url.scheme, url.netloc, url.path.rstrip('/'), '', ''))
    return hashlib.sha256(key.encode()).hexdigest()


def published(item):
    try: return parsedate_to_datetime(item.get('published', '')).timestamp()
    except (ValueError, TypeError, OverflowError): return 0


def select_news(items, path=HISTORY_PATH, count=5):
    """Prefer unseen articles, then least recently selected when feeds run out."""
    path = Path(path)
    with _lock:
        try:
            state = json.loads(path.read_text(encoding='utf-8'))
            seen = state['seen']; sequence = int(state['sequence']) + 1
            if not isinstance(seen, dict): raise ValueError
            seen = {key: value for key, value in seen.items() if isinstance(value, int) and value >= 0}
        except (OSError, ValueError, KeyError, TypeError):
            seen, sequence = {}, 1
        unique = {}; titles = set()
        for item in sorted(items, key=published, reverse=True):
            title = item['title'].casefold().strip()
            if title in titles: continue
            titles.add(title); unique.setdefault(identity(item), item)
        ranked = sorted(unique.items(), key=lambda pair: (seen.get(pair[0], 0), not bool(pair[1].get('image_url')), -published(pair[1])))
        chosen = ranked[:count]
        for key, _ in chosen: seen[key] = sequence
        seen = dict(sorted(seen.items(), key=lambda pair: pair[1], reverse=True)[:500])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.tmp'); temp.write_text(json.dumps({'sequence':sequence, 'seen':seen}), encoding='utf-8')
            temp.replace(path)
        except OSError:
            pass
        return [dict(item) for _, item in chosen]


def preload_image(item):
    result = dict(item)
    url = str(item.get('image_url', ''))
    if not url.startswith(('https://', 'http://')): return result
    try:
        from PIL import Image
        with requests.get(url, timeout=(3, 6), stream=True,
                          headers={'User-Agent':'Mozilla/5.0', 'Referer':item['url']}) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(32768):
                data.extend(chunk)
                if len(data) > 3_000_000: return result
        with Image.open(BytesIO(data)) as picture:
            if picture.width * picture.height > 20_000_000: return result
            picture.thumbnail((1000, 600))
            output = BytesIO(); picture.convert('RGB').save(output, format='JPEG', quality=85)
            result['image_data'] = base64.b64encode(output.getvalue()).decode('ascii')
    except Exception:
        pass
    return result


def current_news(path=HISTORY_PATH, count=5, sources=None, topics=''):
    count = max(0, min(15, int(count)))
    if count == 0: return []
    feeds = FEEDS if sources is None else [spec for spec in FEEDS if spec[0] in sources]
    with ThreadPoolExecutor(max_workers=2) as pool:
        items = [item for group in pool.map(fetch_feed, feeds) for item in group]
    if not items and sources is None:
        from web_research import fetch_news
        items = [item.as_dict() for item in fetch_news(None, 24)]
    if topics.strip():
        import unicodedata
        def norm(value):
            return ''.join(c for c in unicodedata.normalize('NFD', value.casefold()) if not unicodedata.combining(c))
        terms = [norm(x.strip()) for x in topics.split(',') if x.strip()]
        items = [item for item in items if any(term in norm(item['title'] + ' ' + item.get('snippet', '')) for term in terms)]
    selected = select_news(items, path, count=count)
    from .news_images import with_images
    selected = with_images(selected)
    with ThreadPoolExecutor(max_workers=3) as pool:
        return list(pool.map(preload_image, selected))
