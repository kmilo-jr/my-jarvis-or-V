import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QSize
from PySide6.QtMultimedia import QVideoFrame

from core.vision import decode, vision_command, summarize, Detection, ObjectDetector
from integrations.vision_gemini import describe_image
from ui.camera_panel import CameraPanel, to_pil, select_camera_format, VisionProcessor


class DetectionTests(unittest.TestCase):
    def test_prefers_modest_stream_and_avoids_slow_format(self):
        def fmt(w, h, fps):
            return SimpleNamespace(resolution=lambda: QSize(w, h), maxFrameRate=lambda: fps)
        hd = fmt(1280, 720, 30)
        small = fmt(640, 480, 30)
        slow = fmt(640, 480, 5)
        huge = fmt(3840, 2160, 60)
        self.assertIs(select_camera_format([hd, small, huge]), small)
        self.assertIs(select_camera_format([hd, slow, huge]), hd)
        self.assertIsNone(select_camera_format([]))

    def test_processor_converts_video_frame(self):
        image = QImage(640, 480, QImage.Format.Format_RGB32)
        image.fill(QColor('red'))
        processor = VisionProcessor(None)
        processor.detector = Mock()
        processor.detector.detect.return_value = []
        _, _, converted = processor.run(QVideoFrame(image), None)
        self.assertFalse(converted.isNull())
        pil = processor.detector.detect.call_args.args[0]
        self.assertEqual(pil.getpixel((0, 0)), (255, 0, 0))

    def test_commands_and_negations(self):
        self.assertEqual(vision_command('ligue a câmera!'), 'open')
        self.assertEqual(vision_command('Você está me vendo?'), 'detect')
        self.assertEqual(vision_command('desligue a câmera'), 'close')
        for text in ('não ligue a câmera', 'comprar uma câmera', 'camera de segurança', 'bom dia'):
            self.assertIsNone(vision_command(text))

    def test_decode_coordinates_nms_and_classes(self):
        raw = np.zeros((1, 3549, 85), dtype=np.float32)
        # Two adjacent cells predict the same person; a third predicts a dog.
        for i, cx, cls in ((0, 10, 0), (1, 9, 0), (2, 8, 16)):
            raw[0, i, :4] = [cx, 10, np.log(10), np.log(10)]
            raw[0, i, 4] = .9
            raw[0, i, 5 + cls] = .9
        found = decode(raw, 416, .5, 832, 832)
        self.assertEqual({d.label for d in found}, {'pessoa', 'cachorro'})
        self.assertEqual(len(found), 2)
        np.testing.assert_allclose(found[0].box, (80, 80, 240, 240), atol=.001)
        self.assertTrue((raw[0, :3, 2] < 3).all())  # No mutation of runtime output.

    def test_empty_nonfinite_and_missing_model(self):
        raw = np.zeros((1, 3549, 85), dtype=np.float32)
        raw[0, 0, 4] = float('nan')
        self.assertEqual(decode(raw, 416, 1, 416, 416), [])
        self.assertIn('Não identifiquei', summarize([]))
        with self.assertRaisesRegex(RuntimeError, 'ausente'):
            ObjectDetector('missing-camera-model.onnx')

    def test_rgb_stride_conversion(self):
        image = QImage(7, 4, QImage.Format.Format_RGB888)
        image.fill(QColor('red'))
        converted = to_pil(image)
        self.assertEqual(converted.size, (7, 4))
        self.assertEqual(converted.getpixel((6, 3)), (255, 0, 0))


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.brain = SimpleNamespace(_gemini_allowed=lambda: True, gemini_key='test-key',
                                     gemini_chat_model='test-model', gemini_base_url='https://example.invalid/v1beta')

    @patch('integrations.vision_gemini.requests.post')
    def test_cloud_disabled_never_sends(self, post):
        self.brain._gemini_allowed = lambda: False
        with self.assertRaises(RuntimeError):
            describe_image(self.brain, b'image', 'descreva')
        post.assert_not_called()

    @patch('integrations.vision_gemini.requests.post')
    def test_single_image_no_tools_and_visible_answer_only(self, post):
        post.return_value.ok = True
        post.return_value.json.return_value = {'candidates': [{'content': {'parts': [
            {'text': 'hidden', 'thought': True}, {'text': 'Um copo.'}]}}]}
        self.assertEqual(describe_image(self.brain, b'image', 'descreva'), 'Um copo.')
        payload = post.call_args.kwargs['json']
        self.assertNotIn('tools', payload)
        self.assertEqual(len(payload['contents'][0]['parts']), 2)
        self.assertEqual(post.call_args.kwargs['timeout'], (5, 35))

    @patch('integrations.vision_gemini.requests.post')
    def test_http_failure_does_not_leak_body(self, post):
        post.return_value.ok = False
        post.return_value.status_code = 429
        post.return_value.text = 'secret API data'
        with self.assertRaisesRegex(RuntimeError, 'HTTP 429') as error:
            describe_image(self.brain, b'image', 'descreva')
        self.assertNotIn('secret', str(error.exception))


class CameraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch('ui.camera_panel.QMediaDevices.videoInputs', return_value=[]):
            self.panel = CameraPanel()
        self.messages = []
        self.panel.answer.connect(self.messages.append)

    def tearDown(self):
        self.panel.shutdown()
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def test_default_off_no_devices_no_online_upload(self):
        self.assertIsNone(self.panel.camera)
        self.assertFalse(self.panel.start_button.isEnabled())
        self.assertFalse(self.panel.online_toggle.isChecked())
        with patch.object(self.panel.executor, 'submit') as submit:
            self.panel.describe('descreva')
            self.panel.detect_once()
            submit.assert_not_called()
        self.assertEqual(len(self.messages), 2)

    def test_preview_is_native_and_latest_frame_advances_during_slow_analysis(self):
        self.panel.camera = Mock()
        self.panel.future = Future()  # Deliberately never finishes during capture.
        self.panel.future_generation = self.panel.generation
        self.panel.has_detection = True
        self.assertIs(self.panel.sink, self.panel.video.videoSink())
        with patch.object(self.panel.executor, 'submit') as submit, patch.object(self.panel, '_show_image') as repaint:
            for color in ('red', 'green', 'blue'):
                image = QImage(32, 24, QImage.Format.Format_RGB32)
                image.fill(QColor(color))
                self.panel._frame(QVideoFrame(image))
                self.panel._tick()
            submit.assert_not_called()
            repaint.assert_not_called()  # QLabel snapshots must not replace native video.
        self.assertEqual(self.panel.latest.toImage().pixelColor(0, 0), QColor('blue'))
        self.panel.future.set_result(('Done', [], None))

    def test_completed_detection_never_replaces_live_preview(self):
        self.panel.camera = Mock()
        self.panel.frame_at = time.monotonic()
        self.panel.future = Future()
        self.panel.future_generation = self.panel.generation
        self.panel.future_started = time.monotonic() - 2
        self.panel.future.set_result(('Uma pessoa', [], QImage(20, 20, QImage.Format.Format_RGB32)))
        with patch.object(self.panel, '_show_image') as repaint:
            self.panel._tick()
            repaint.assert_not_called()
        self.assertEqual(self.panel.result.text(), 'Uma pessoa')
        self.assertGreater(self.panel.next_detection - time.monotonic(), 2.5)

    def test_stale_frame_never_submitted(self):
        self.panel.camera = Mock()
        self.panel.latest = QImage(4, 4, QImage.Format.Format_RGB888)
        self.panel.frame_at = time.monotonic() - 3
        with patch.object(self.panel.executor, 'submit') as submit:
            self.panel.detect_once()
            submit.assert_not_called()

    def test_game_mode_spaces_detection_and_normal_mode_restores_interval(self):
        from types import SimpleNamespace
        parent = SimpleNamespace(game_mode=SimpleNamespace(enabled=True))
        self.panel.camera = Mock()
        self.panel.frame_at = time.monotonic()
        with patch.object(self.panel, 'parent', return_value=parent):
            for enabled, minimum, maximum in [(True, 2.8, 3.1), (False, .5, .9)]:
                parent.game_mode.enabled = enabled
                self.panel.future = Future()
                self.panel.future_generation = self.panel.generation
                self.panel.future_started = time.monotonic()
                self.panel.future.set_result(('Objects', [], QImage(20, 20, QImage.Format.Format_RGB32)))
                self.panel._tick()
                remaining = self.panel.next_detection - time.monotonic()
                self.assertGreater(remaining, minimum)
                self.assertLess(remaining, maximum)

    def test_stop_discards_inflight_result_and_clears_image(self):
        self.assertFalse(self.panel.timer.isActive())
        self.panel.timer.start()
        camera = self.panel.camera = Mock()
        self.panel.latest = QImage(4, 4, QImage.Format.Format_RGB888)
        self.panel.future = Future()
        self.panel.future_generation = self.panel.generation
        self.panel.future_spoken = True
        self.panel.stop()
        self.assertTrue(self.panel.timer.isActive())
        self.panel.future.set_result(('Old scene', [], None))
        self.panel._tick()
        self.assertFalse(self.panel.timer.isActive())
        camera.stop.assert_called_once()
        self.assertIsNone(self.panel.latest)
        self.assertEqual(self.messages, [])

    def test_busy_local_request_reuses_one_job(self):
        self.panel.future = Future()
        self.panel.future_generation = self.panel.generation
        with patch.object(self.panel.executor, 'submit') as submit:
            self.panel.detect_once()
            submit.assert_not_called()
        self.assertTrue(self.panel.future_spoken)
        self.panel.future.set_result(('Objects', [], None))

    def test_failure_stops_retry_loop(self):
        self.panel.camera = Mock()
        self.panel.frame_at = time.monotonic()
        self.panel.future = Future()
        self.panel.future_generation = self.panel.generation
        self.panel.future.set_exception(RuntimeError('Modelo ausente'))
        with patch.object(self.panel.executor, 'submit') as submit:
            self.panel._tick()
            self.panel._tick()
            submit.assert_not_called()
        self.assertTrue(self.panel.detect_failed)
        self.assertIn('Modelo ausente', self.panel.status.text())

    def test_disconnection_and_frame_timeout(self):
        self.panel.camera = Mock()
        self.panel.frame_at = time.monotonic() - 10
        self.panel._tick()
        self.assertIsNone(self.panel.camera)
        self.assertIn('não está enviando', self.panel.status.text())
        self.panel.camera = Mock()
        self.panel.camera.cameraDevice.return_value.id.return_value = b'disconnected'
        with patch('ui.camera_panel.QMediaDevices.videoInputs', return_value=[]):
            self.panel.refresh_devices()
        self.assertIsNone(self.panel.camera)
        self.assertIn('Nenhuma câmera', self.panel.status.text())

    def test_escape_closes_camera_and_resets_upload(self):
        camera = self.panel.camera = Mock()
        self.panel.online_toggle.setChecked(True)
        self.panel.reject()
        camera.stop.assert_called_once()
        self.assertIsNone(self.panel.camera)
        self.assertFalse(self.panel.online_toggle.isChecked())


if __name__ == '__main__':
    unittest.main()
