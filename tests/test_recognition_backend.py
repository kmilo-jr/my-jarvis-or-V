from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
import numpy as np
from voice.recognition_backend import load_model
from voice.engine import VoiceEngine


class RecognitionBackendTests(unittest.TestCase):
    def test_auto_selects_gpu_and_registers_libraries(self):
        with patch('ctranslate2.get_cuda_device_count', return_value=1), patch(
                'faster_whisper.WhisperModel') as factory, patch(
                'voice.recognition_backend.prepare_cuda_libraries') as prepare:
            _, info = load_model({'device': 'auto'})
        self.assertEqual(info['device'], 'cuda')
        self.assertEqual(factory.call_args.kwargs['compute_type'], 'int8_float16')
        prepare.assert_called_once()

    def test_auto_without_gpu_uses_int8_cpu(self):
        with patch('ctranslate2.get_cuda_device_count', return_value=0), patch(
                'faster_whisper.WhisperModel') as factory:
            _, info = load_model({'device': 'auto'})
        self.assertEqual(info['device'], 'cpu')
        self.assertEqual(factory.call_args.kwargs['compute_type'], 'int8')

    def test_gpu_load_failure_falls_back_once(self):
        with patch('faster_whisper.WhisperModel', side_effect=[RuntimeError('CUDA OOM'), Mock()]) as factory, patch(
                'voice.recognition_backend.prepare_cuda_libraries'):
            _, info = load_model({'device': 'cuda'})
        self.assertEqual(info['device'], 'cpu')
        self.assertEqual(factory.call_count, 2)

    def test_inference_gpu_failure_retries_same_audio_on_cpu(self):
        engine = VoiceEngine({'device': 'auto'})
        engine._recognition_backend = {'device': 'cuda'}
        engine._model = Mock()
        engine._model.transcribe.side_effect = RuntimeError('CUDA out of memory')
        cpu = Mock()
        cpu.transcribe.return_value = (iter([SimpleNamespace(text='V, bom dia', avg_logprob=-.2)]),
                                       SimpleNamespace(language='pt', language_probability=1))
        audio = np.ones(16000)
        with patch('voice.recognition_backend.load_model', return_value=(cpu, {'device': 'cpu'})) as load:
            text, meta = engine.transcribe(audio)
        self.assertEqual(text, 'V, bom dia')
        self.assertIs(cpu.transcribe.call_args.args[0], audio)
        self.assertTrue(load.call_args.kwargs['force_cpu'])
        self.assertEqual(meta['recognition_backend']['device'], 'cpu')


if __name__ == '__main__':
    unittest.main()
