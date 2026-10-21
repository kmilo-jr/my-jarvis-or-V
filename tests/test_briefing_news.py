import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from core.briefing_news import parse_feed, select_news, current_news


class BriefingNewsTests(unittest.TestCase):
    def test_publisher_photo_wins_over_logo_in_description(self):
        xml = b'<rss><channel><item><title>News</title><link>https://example.org/story</link><imagem-destaque>https://example.org/photo.jpg</imagem-destaque><description>&lt;img src="logo.svg"/&gt;Article</description></item></channel></rss>'
        self.assertEqual(parse_feed(xml, 'Publisher')[0]['image_url'], 'https://example.org/photo.jpg')

    def test_rotation_persists_between_calls_and_recycles_oldest(self):
        items = [dict(title=f'Item {i}', url=f'https://example.org/{i}', image_url='photo') for i in range(15)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'seen.json'
            first = select_news(items, path)
            second = select_news(items, path)
            third = select_news(items, path)
            self.assertEqual(len({i['url'] for i in first+second+third}), 15)
            self.assertEqual(select_news(items, path), first)

    def test_duplicate_urls_and_titles_do_not_fill_multiple_slots(self):
        items = [dict(title='One', url='https://example.org/1'), dict(title='One', url='https://example.org/2'), dict(title='Updated', url='https://example.org/1?utm_source=x')]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(len(select_news(items, Path(directory)/'seen.json')), 1)

    def test_each_request_fetches_again(self):
        items = [dict(title=f'Item {i}', url=f'https://example.org/{i}', image_url='photo') for i in range(10)]
        with tempfile.TemporaryDirectory() as directory, patch('core.briefing_news.fetch_feed', return_value=items) as fetch, patch('core.news_images.with_images', side_effect=lambda x:x), patch('core.briefing_news.preload_image', side_effect=lambda x:x):
            path = Path(directory)/'seen.json'
            first, second = current_news(path), current_news(path)
            self.assertEqual(len(first), 5)
            self.assertEqual(len(second), 5)
            self.assertEqual(fetch.call_count, 4)
            self.assertFalse({x['url'] for x in first} & {x['url'] for x in second})
