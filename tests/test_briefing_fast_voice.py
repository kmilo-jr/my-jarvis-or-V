import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch
from core.daily_briefing import card, concise_speech
from voice.briefing_cache import GREETINGS, cache_path, store_audio, valid_audio
from voice.engine import VoiceEngine


class FastBriefingTests(unittest.TestCase):
    def test_narrator_override_is_per_item_and_conversation_returns_to_qwen(self):
        import threading
        engine = VoiceEngine({'tts_profile': 'qwen_local'})
        calls = []
        receipts = [{'state': 'queued', 'profile': 'qwen_local'},
                    {'state': 'queued', 'profile': 'piper'}, {'state': 'queued'}]
        for text, receipt in zip(('abertura', 'resumo', 'conversa'), receipts):
            engine._tts_queue.put((text, threading.Event(), receipt))
        engine._tts_queue.put(None)
        with patch.object(engine, '_speak_qwen', side_effect=lambda t: calls.append(('qwen', t)) or True), patch.object(
                engine, '_speak_piper', side_effect=lambda t: calls.append(('piper', t)) or True), patch.object(
                engine, '_save_tts_diagnostic'), patch.object(engine, '_begin_visual_speech'), patch.object(engine, '_end_visual_speech'):
            engine._tts_loop()
        self.assertEqual(calls, [('qwen', 'abertura'), ('piper', 'resumo'), ('qwen', 'conversa')])
        self.assertTrue(all(r['state'] == 'done' for r in receipts))
        self.assertEqual(engine.config['tts_profile'], 'qwen_local')

    def test_short_speech_preserves_display_and_unavailable_warning(self):
        body = '10:00 · Reunião\n14:00 · Estudo\n16:00 · Mercado'
        item = card('agenda', 'Agenda', body, metric='3')
        spoken = concise_speech(item)
        self.assertIn('10:00', spoken)
        self.assertNotIn('14:00', spoken)
        self.assertEqual(item['body'], body)
        failed = card('clima', 'Indisponível', 'Não consegui consultar.', ok=False)
        self.assertEqual(concise_speech(failed), failed['speech'])
        message = card('mensagens', 'Mensagens', 'Captura indisponível', metric='2')
        self.assertIn('incompleta', concise_speech(message))

    def test_cache_is_fixed_only_invalidates_reference_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); ref = root/'ref.wav'; ref.write_bytes(b'reference')
            self.assertIsNone(cache_path('Meu e-mail privado', ref, {}, root))
            key = cache_path(GREETINGS[0], ref, {}, root)
            ref.write_bytes(b'changed')
            self.assertNotEqual(key, cache_path(GREETINGS[0], ref, {}, root))
            key.write_bytes(b'broken')
            self.assertFalse(valid_audio(key))

    def test_cached_greeting_bypasses_synthesis_and_survives_engine_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); ref = root/'ref.wav'; ref.write_bytes(b'reference')
            source = root/'sample.wav'
            with wave.open(str(source), 'wb') as audio:
                audio.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                audio.writeframes(b'\x00\x10' * 2400)
            key = cache_path(GREETINGS[0], ref, {}, root)
            store_audio(source, key)
            for _ in range(2):
                engine = VoiceEngine({})
                backend = Mock()
                with patch.object(engine, '_get_qwen', return_value=backend), patch.object(
                        engine, '_resolve_qwen_reference', return_value=ref), patch(
                        'voice.briefing_cache.cache_path', return_value=key), patch.object(
                        engine, '_play_xtts_audio', side_effect=lambda chunks, *a, **kw: bool(list(chunks))):
                    self.assertTrue(engine._speak_qwen(GREETINGS[0]))
                backend.synthesize.assert_not_called()
                self.assertTrue(valid_audio(key))
                self.assertTrue(engine.last_tts_metrics['persistent_greeting_hit'])
