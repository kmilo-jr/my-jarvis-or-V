import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from brain.groq_client import GroqClient, load_key, save_key
from brain.service import BrainService


class GroqTests(unittest.TestCase):
    def client(self, status=200, content='Resposta.', finish='stop'):
        with patch('brain.groq_client.load_key', return_value='secret-test'):
            client = GroqClient({})
        response = Mock(status_code=status, headers={'retry-after':'15'})
        response.json.return_value = {'choices': [{'finish_reason': finish, 'message': {'content': content, 'reasoning': 'not spoken'}}]}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        client.session = Mock()
        client.session.post.return_value = response
        return client

    def brain(self):
        with patch('brain.service.load_key', return_value='gemini-test'), patch('brain.groq_client.load_key', return_value='groq-test'):
            b = BrainService({'provider': 'hybrid'})
        b.groq = self.client()
        b._gemini_chat = Mock(return_value=None)
        b._gemini_plan = Mock(return_value=None)
        b._ollama_chat = Mock(return_value='local')
        b._ollama_plan = Mock(return_value='local plan')
        return b

    def test_request_carries_history_and_json_contract(self):
        c = self.client(content='{"mode":"chat","reply":"Olá","actions":[]}')
        c.generate('Return JSON.', [{'role':'user','content':'Antes'}], 'Depois', json_mode=True)
        args = c.session.post.call_args
        self.assertEqual(args.args[0], 'https://api.groq.com/openai/v1/chat/completions')
        payload = args.kwargs['json']
        self.assertEqual(payload['model'], 'openai/gpt-oss-120b')
        self.assertEqual(payload['response_format'], {'type':'json_object'})
        self.assertEqual(payload['messages'][1]['content'], 'Antes')
        self.assertEqual(payload['reasoning_effort'], 'low')
        self.assertFalse(c.last_latency['streaming'])

    def test_http_errors_do_not_expose_credentials_or_body(self):
        c = self.client(status=401)
        self.assertIsNone(c.generate('', [], 'Olá'))
        self.assertIn('chave inválida', c.last_error)
        self.assertNotIn(c.key, c.last_error)

    def test_rate_limit_honors_retry_after_without_sleeping(self):
        c = self.client(status=429)
        with patch('brain.groq_client.time.monotonic', return_value=100):
            c.generate('', [], 'Olá')
            c.generate('', [], 'Olá')
        self.assertEqual(c.retry_at, 115)
        self.assertEqual(c.session.post.call_count, 1)
        with patch('brain.groq_client.time.monotonic', return_value=116):
            c.generate('', [], 'Olá')
        self.assertEqual(c.session.post.call_count, 2)

    def test_invalid_results_are_rejected(self):
        for content, finish in [('Partial', 'length'), ('', 'stop'), ('Tool', 'tool_calls')]:
            self.assertIsNone(self.client(content=content, finish=finish).generate('', [], 'Olá'))

    def test_gemini_success_skips_groq(self):
        b = self.brain()
        b._gemini_chat.return_value = 'Gemini'
        self.assertEqual(b.chat('Olá', []), 'Gemini')
        b.groq.session.post.assert_not_called()

    def test_groq_primary_chat_and_stream_skip_gemini(self):
        for method in ('chat', 'chat_stream'):
            b = self.brain()
            b.config['primary_provider'] = 'groq'
            b._gemini_session = Mock()
            self.assertEqual(getattr(b, method)('Oi', []), 'Resposta.')
            b._gemini_chat.assert_not_called()
            b._gemini_session.post.assert_not_called()
            b._ollama_chat.assert_not_called()

    def test_groq_primary_failure_tries_gemini_once_without_repeating_groq(self):
        b = self.brain()
        b.config['primary_provider'] = 'groq'
        b.groq = self.client(status=503)
        self.assertEqual(b.chat('Oi', []), 'local')
        self.assertEqual(b.groq.session.post.call_count, 1)
        b._gemini_chat.assert_called_once()

    def test_primary_groq_error_is_retained_when_all_services_fail(self):
        b = self.brain()
        b.config['primary_provider'] = 'groq'
        b.groq = self.client(status=403)
        def fail_gemini(*args):
            b.last_error = 'Gemini HTTP 401'
        def fail_local(*args):
            b.last_error = 'Ollama indisponivel'
        b._gemini_chat.side_effect = fail_gemini
        b._ollama_chat.side_effect = fail_local
        self.assertIsNone(b.chat('Oi', []))
        for name in ('Groq', 'Gemini', 'Ollama'):
            self.assertIn(name, b.last_error)

    def test_groq_primary_plan_and_summary_skip_gemini(self):
        b = self.brain()
        b.config['primary_provider'] = 'groq'
        b.groq = self.client(content='{"mode":"chat","reply":"Oi","actions":[]}')
        self.assertEqual(b.plan('Oi', []).provider, 'groq')
        b._gemini_plan.assert_not_called()
        b._gemini_generate = Mock()
        b.groq = self.client()
        self.assertEqual(b.respond_after_tools('Pedido', [], []), 'Resposta.')
        b._gemini_generate.assert_not_called()

    def test_groq_precedes_local_and_preserves_memories_and_context(self):
        b = self.brain()
        b.memory_store = Mock()
        b.memory_store.get_memories.return_value = ['Prefere respostas curtas']
        b.last_error = 'Gemini: HTTP 503'
        self.assertEqual(b.chat('Olá', [], {'project':'V'}), 'Resposta.')
        self.assertEqual(b.last_provider, 'groq:openai/gpt-oss-120b')
        self.assertFalse(b.last_latency['streaming'])
        b._ollama_chat.assert_not_called()
        system = b.groq.session.post.call_args.kwargs['json']['messages'][0]['content']
        self.assertIn('project', system)
        self.assertIn('Prefere respostas curtas', system)

    def test_failure_and_missing_key_use_local(self):
        b = self.brain()
        b.groq = self.client(status=503)
        self.assertEqual(b.chat('Olá', []), 'local')
        b.groq.key = ''
        b.groq.session.post.reset_mock()
        self.assertEqual(b.chat('Olá', []), 'local')
        b.groq.session.post.assert_not_called()

    def test_failed_stream_uses_groq_and_does_not_suppress_voice(self):
        b = self.brain()
        b._gemini_session = Mock()
        b._gemini_session.post.return_value = Mock(status_code=503, text='Unavailable')
        self.assertEqual(b.chat_stream('Olá', []), 'Resposta.')
        self.assertFalse(b.last_latency['streaming'])
        b._ollama_chat.assert_not_called()

    def test_plan_keeps_only_registered_tools(self):
        b = self.brain()
        b.groq = self.client(content=json.dumps({'mode':'tools','actions':[{'tool':'app.open','args':{'app':'calculadora'}},{'tool':'shell.execute','args':{}}]}))
        plan = b.plan('Abra a calculadora', [], tool_manifest=[{'name':'app.open'}])
        self.assertEqual(plan.provider, 'groq')
        self.assertEqual([a['tool'] for a in plan.actions], ['app.open'])
        b._ollama_plan.assert_not_called()

    def test_malformed_plan_falls_back_to_local(self):
        b = self.brain()
        b.groq = self.client(content='{"mode":"tools","actions":42}')
        self.assertEqual(b.plan('Abra algo', []), 'local plan')

    def test_post_tool_summary_uses_groq(self):
        b = self.brain()
        b._gemini_generate = Mock(return_value=None)
        self.assertEqual(b.respond_after_tools('Pedido', [], [{'ok':True,'message':'Concluído'}]), 'Resposta.')

    def test_live_search_does_not_invent_sources_with_groq(self):
        b = self.brain()
        b.live_search = Mock(return_value=None)
        for method in [b.chat, b.chat_stream]:
            self.assertIn('Não consegui verificar', method('Notícias de hoje', []))
        b.groq.session.post.assert_not_called()

    def test_credentials_roundtrip_with_dpapi(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', {'GROQ_API_KEY':''}):
            path = Path(folder) / 'key.dat'
            save_key('secret-test', path)
            self.assertNotIn('secret-test', path.read_text())
            self.assertEqual(load_key(path), 'secret-test')


if __name__ == '__main__':
    unittest.main()
