import unittest
from unittest.mock import Mock, patch
from core.news_images import article_image


class NewsImageTests(unittest.TestCase):
    def test_feed_image_is_preserved_without_fetch(self):
        with patch('core.news_images.requests.get') as get:
            self.assertEqual(article_image({'image_url':'https://example.org/photo.jpg'}), 'https://example.org/photo.jpg')
            get.assert_not_called()

    def test_publisher_metadata_and_relative_url(self):
        response = Mock(); response.headers = {'Content-Type':'text/html'}; response.url = 'https://example.org/story'
        response.iter_content.return_value = [b'<meta property="og:image" content="/image.jpg">']
        request = Mock(); request.__enter__ = Mock(return_value=response); request.__exit__ = Mock(return_value=False)
        with patch('core.news_images.requests.get', return_value=request):
            self.assertEqual(article_image({'url':response.url}), 'https://example.org/image.jpg')

    def test_unrelated_result_not_used_as_article_image(self):
        with patch('web_research.web_search', return_value=[Mock(title='Outra coisa', url='https://example.org')]), patch('core.news_images.requests.get') as get:
            self.assertEqual(article_image({'title':'Nova pesquisa sobre astronomia', 'url':'https://news.google.com/rss/123'}), '')
            get.assert_not_called()
