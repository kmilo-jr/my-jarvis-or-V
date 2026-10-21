import unittest
from unittest.mock import Mock, patch
from core.learning import philosophy, learning_request
from brain.service import BrainService
from brain.web_fallback import search
from web_research import WebItem
from core.functional_engine import FunctionalEngine, FunctionalResult


class LearningResearchTests(unittest.TestCase):
    def engine(self):
        e = FunctionalEngine.__new__(FunctionalEngine)
        e.projects = Mock()
        e.projects.command.return_value = None
        e.history = []
        e._append_history = Mock()
        e.brain = Mock()
        return e

    def test_philosophy_is_local_attributed_as_paraphrase_and_does_not_repeat(self):
        first = philosophy('qual a filosofia de hoje')
        second = philosophy('outra filosofia', first[0])
        self.assertNotEqual(first[0], second[0])
        self.assertIn('palavras próprias', second[1])
        e = self.engine()
        self.assertEqual(e.handle('V, qual a filosofia de hoje')[0].skill, 'FILOSOFIA')
        e.brain.chat.assert_not_called()

    def test_learning_modes_activate_without_ai_and_can_be_ended(self):
        e = self.engine()
        self.assertEqual(e.handle('me ajude a aprender inglês')[0].skill, 'ESTUDOS')
        self.assertEqual(e.brain.tutor_mode, 'english')
        e.handle('preciso de ajuda com um trabalho da faculdade')
        self.assertEqual(e.brain.tutor_mode, 'study')
        e.handle('encerrar estudo')
        self.assertEqual(e.brain.tutor_mode, '')

    def test_election_question_requests_scope_before_network(self):
        e = self.engine()
        result = e.handle('quem está à frente nas pesquisas das eleições')[0]
        self.assertIn('cargo e local', result.message)
        self.assertTrue(e._pending_election_query)
        e.brain.chat.assert_not_called()

    def test_tutor_instructions_reach_model_prompt(self):
        with patch('brain.service.load_key', return_value=''), patch('brain.groq_client.load_key', return_value=''):
            b = BrainService({})
        b.tutor_mode = 'english'
        self.assertIn('MODO INGLÊS', b._identity_prompt())
        b.tutor_mode = 'study'
        self.assertIn('Nunca invente bibliografia', b._identity_prompt())

    def test_election_scope_reply_reaches_search_and_never_planner(self):
        e = self.engine()
        e.handle('quem está à frente nas pesquisas das eleições')
        e.tool_router = Mock()
        e.tool_router.route.return_value.mode = 'chat'
        e._memory_command = Mock(return_value=None)
        e._pre_route_known_intent = Mock(return_value=None)
        e._brain_wants_live_search = Mock(return_value=True)
        e._chat_with_brain = Mock(return_value=FunctionalResult(True, True, 'Fontes', 'PESQUISA'))
        self.assertEqual(e.handle('presidente do Brasil')[0].message, 'Fontes')
        query = e._chat_with_brain.call_args.args[0]
        self.assertIn('pesquisas das eleições', query)
        self.assertIn('presidente do Brasil', query)
        e.brain.plan.assert_not_called()

    def test_search_returns_sources_without_any_model(self):
        b = Mock()
        b._groq_allowed.return_value = False
        item = WebItem('Pesquisa no estado X', 'https://example.org/pesquisa', 'Instituto X', 'Coleta em setembro', '2026-10-01')
        with patch('web_research.fetch_news', return_value=[item]):
            answer = search(b, 'pesquisa governador de X')
        self.assertIn('https://example.org/pesquisa', answer)
        self.assertIn('Não consegui sintetizar', answer)
        self.assertEqual(b.last_live_search['items'][0]['published'], '2026-10-01')
        b._groq_generate.assert_not_called()

    def test_search_failure_does_not_claim_it_has_sources(self):
        b = Mock()
        with patch('web_research.fetch_news', side_effect=RuntimeError), patch('web_research.web_search', return_value=[]):
            self.assertIsNone(search(b, 'consulta'))

    def test_groq_primary_search_does_not_require_gemini(self):
        with patch('brain.service.load_key', return_value=''), patch('brain.groq_client.load_key', return_value=''):
            b = BrainService({'primary_provider': 'groq', 'web_search_fallback_enabled': True})
        with patch('brain.web_fallback.search', return_value='Fontes encontradas') as web:
            self.assertEqual(b.chat('pesquisa eleitoral hoje', []), 'Fontes encontradas')
            web.assert_called_once()
