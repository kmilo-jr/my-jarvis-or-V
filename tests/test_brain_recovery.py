import json
import unittest
from unittest.mock import Mock, patch
import requests
from brain.service import BrainService


class BrainRecoveryTests(unittest.TestCase):
    def test_gemini_25_uses_supported_thinking_budget(self):
        with patch('brain.service.load_key', return_value='test'):
            brain = BrainService({'gemini_model': 'gemini-2.5-flash'})
        config = brain._gemini_payload('', [], 'Olá')['generationConfig']
        self.assertEqual(config['thinkingConfig'], {'thinkingBudget': 0})

    def test_gemini_3_retains_thinking_level(self):
        with patch('brain.service.load_key', return_value='test'):
            brain = BrainService({'gemini_model': 'gemini-3.7-flash'})
        config = brain._gemini_payload('', [], 'Olá')['generationConfig']
        self.assertEqual(config['thinkingConfig'], {'thinkingLevel': 'low'})

    def brain(self, provider='hybrid'):
        with patch('brain.service.load_key', return_value='test'):
            # These tests isolate Gemini -> Ollama; never call a configured real Groq account.
            brain = BrainService({'provider': provider, 'gemini_chat_model': 'test', 'gemini_fallback_model': 'test', 'groq_enabled': False})
        brain._gemini_session = Mock()
        brain._gemini_session.post.return_value = Mock(status_code=503, text='Temporarily unavailable')
        return brain

    def local_response(self, text):
        response = Mock()
        response.read.return_value = json.dumps({'message': {'content': text}}).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    def test_503_falls_back_once_and_clears_stale_streaming_metadata(self):
        brain = self.brain()
        brain.last_latency = {'provider': 'gemini:test', 'streaming': True}
        with patch('brain.service.urllib.request.urlopen', return_value=self.local_response('Estou aqui.')):
            result = brain.chat_stream('Olá', [])
        self.assertEqual(result, 'Estou aqui.')
        self.assertEqual(brain._gemini_session.post.call_count, 1)
        self.assertEqual(brain.last_provider, 'ollama')
        self.assertFalse(brain.last_latency['streaming'])
        self.assertIn('503', brain.last_latency['fallback_reason'])
        self.assertEqual(brain.last_error, '')

    def test_timeout_falls_back_without_retrying_online(self):
        brain = self.brain()
        brain._gemini_session.post.side_effect = requests.ReadTimeout('test timeout')
        with patch('brain.service.urllib.request.urlopen', return_value=self.local_response('Resposta local.')):
            self.assertEqual(brain.chat_stream('Olá', []), 'Resposta local.')
        self.assertEqual(brain._gemini_session.post.call_count, 1)

    def test_followup_uses_local_until_online_retry_window(self):
        brain = self.brain()
        with patch('brain.service.time.monotonic', return_value=100), patch('brain.service.urllib.request.urlopen', return_value=self.local_response('Estou aqui.')):
            brain.chat_stream('Olá', [])
            brain.chat_stream('Explique melhor', [])
            brain.chat('Mais um exemplo', [])
        self.assertEqual(brain._gemini_session.post.call_count, 1)
        with patch('brain.service.time.monotonic', return_value=131), patch('brain.service.urllib.request.urlopen', return_value=self.local_response('Estou aqui.')):
            brain.chat_stream('Olá', [])
        self.assertEqual(brain._gemini_session.post.call_count, 2)

    def test_both_failures_remain_in_diagnostics(self):
        brain = self.brain()
        with patch('brain.service.urllib.request.urlopen', side_effect=ConnectionRefusedError('local offline')):
            self.assertIsNone(brain.chat_stream('Olá', []))
        self.assertIn('503', brain.last_error)
        self.assertIn('local offline', brain.last_error)
        self.assertFalse(brain.last_latency['streaming'])

    def test_gemini_only_does_not_use_local_provider(self):
        brain = self.brain('gemini')
        with patch.object(brain, '_ollama_chat') as local:
            self.assertIsNone(brain.chat_stream('Olá', []))
        local.assert_not_called()
        self.assertEqual(brain._gemini_session.post.call_count, 1)

    def test_current_information_never_falls_back_to_local_guess(self):
        brain = self.brain()
        with patch.object(brain, '_ollama_chat') as local:
            result = brain.chat_stream('Quais as notícias de hoje?', [])
        self.assertIn('Não consegui verificar', result)
        local.assert_not_called()

    def test_non_stream_chat_preserves_both_failures(self):
        brain = self.brain()
        with patch('brain.service.urllib.request.urlopen', side_effect=ConnectionRefusedError('local offline')):
            self.assertIsNone(brain.chat('Olá', []))
        self.assertIn('503', brain.last_error)
        self.assertIn('local offline', brain.last_error)


if __name__ == '__main__':
    unittest.main()
