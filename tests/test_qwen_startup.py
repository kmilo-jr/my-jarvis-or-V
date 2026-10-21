import unittest
from unittest.mock import patch
from voice.engine import VoiceEngine


class QwenStartupTests(unittest.TestCase):
    def test_shortens_only_opening_clause_without_losing_words(self):
        voice = VoiceEngine({})
        text = ('Primeiro, vou separar os compromissos importantes, conferir as tarefas '
                'que ficaram pendentes e apresentar um resumo claro, sem repetir informações desnecessárias. Depois, continuamos.')
        chunks = voice._split_qwen_response(text)
        self.assertTrue(chunks[0].endswith('um resumo claro,'))
        self.assertGreaterEqual(len(chunks[0]), len(chunks[1]) * 1.5)
        self.assertEqual(' '.join(chunks), text)
        self.assertEqual(chunks[-1], 'Depois, continuamos.')

    def test_keeps_short_sentences_numbers_and_no_boundary_intact(self):
        voice = VoiceEngine({})
        for text in ('Bom dia. Vamos trabalhar.', 'O resultado foi 12,5 por cento. ',
                     'Palavra ' * 25 + '.',
                     'Sim, ' + 'palavra ' * 22 + '.'):
            self.assertEqual(voice._split_qwen_response(text), voice._split_xtts_response(text))

    def test_does_not_trade_startup_for_a_long_gap_after_tiny_opener(self):
        voice = VoiceEngine({})
        text = ('Primeiro vou separar os compromissos importantes, conferir as tarefas '
                'que ficaram pendentes e apresentar um resumo claro sem repetir informações desnecessárias.')
        self.assertEqual(voice._split_qwen_response(text), voice._split_xtts_response(text))
