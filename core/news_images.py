"""Resolve images from the supplied article or a matching publisher result."""
import re
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup


def article_image(item):
    if item.get('image_url'):
        return item['image_url']
    url = str(item.get('url', ''))
    if urlparse(url).scheme not in ('http', 'https'):
        return ''
    try:
        if urlparse(url).hostname == 'news.google.com':
            from web_research import web_search
            words = set(re.findall(r'\w+', item.get('title', '').casefold()))
            if not words: return ''
            matches = web_search('"' + item['title'] + '" ' + item.get('source', ''), limit=3)
            url = ''
            for match in matches:
                overlap = words & set(re.findall(r'\w+', match.title.casefold()))
                if len(overlap) / len(words) >= .8 and urlparse(match.url).hostname != 'news.google.com':
                    url = match.url; break
            if not url: return ''
        with requests.get(url, timeout=(3, 5), stream=True, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            response.raise_for_status()
            if 'text/html' not in response.headers.get('Content-Type', '').lower(): return ''
            data = bytearray()
            for chunk in response.iter_content(16384):
                data.extend(chunk)
                if len(data) >= 700000: break
            soup = BeautifulSoup(bytes(data), 'html.parser')
            tag = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name':'twitter:image'})
            image = urljoin(response.url, str(tag.get('content', ''))) if tag else ''
            return image if urlparse(image).scheme in ('http', 'https') else ''
    except Exception:
        return ''


def with_images(items):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix='V-ArticleImage') as pool:
        images = list(pool.map(article_image, items))
    return [dict(item, image_url=image) for item, image in zip(items, images)]
