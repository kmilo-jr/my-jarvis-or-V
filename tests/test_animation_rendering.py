import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from ui.animation_clock import AnimationClock
from ui.briefing_scene import BriefingBackdrop
from ui.neural_core import NeuralCoreWidget
from ui.futuristic_face import FuturisticFaceWidget


class ClockTests(unittest.TestCase):
    def test_elapsed_time_and_resume_clamp(self):
        with patch('ui.animation_clock.time.monotonic', side_effect=[10, 10.033, 90, 90.016]):
            clock = AnimationClock()
            self.assertAlmostEqual(clock.step(), .033)
            self.assertEqual(clock.step(), .1)
            self.assertAlmostEqual(clock.step(), .016)

    def test_reset_does_not_catch_up_hidden_time(self):
        with patch('ui.animation_clock.time.monotonic', side_effect=[0, 100, 100.033]):
            clock = AnimationClock()
            clock.reset()
            self.assertAlmostEqual(clock.step(), .033)


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widgets = []

    def tearDown(self):
        for w in self.widgets:
            w.close()
            w.deleteLater()
        self.app.processEvents()

    def make(self, cls):
        widget = cls(None)
        self.widgets.append(widget)
        widget.resize(800, 600)
        return widget

    def test_background_cache_reuses_pixels_and_invalidates_size(self):
        w = self.make(BriefingBackdrop)
        first = w._static_background()
        w.phase = 2.5
        w.set_state('SPEAKING')
        self.assertIs(w._static_background(), first)
        w.resize(900, 700)
        resized = w._static_background()
        self.assertIsNot(resized, first)
        self.assertEqual(w._background_key[:2], (900, 700))

    def test_same_motion_with_different_frame_intervals(self):
        w = self.make(BriefingBackdrop)
        with patch.object(w._clock, 'step', return_value=.025):
            for _ in range(40):
                w.tick()
        self.assertAlmostEqual(w.phase, .3)
        w.phase = 0
        with patch.object(w._clock, 'step', return_value=.1):
            for _ in range(10):
                w.tick()
        self.assertAlmostEqual(w.phase, .3)

    def test_animation_timers_follow_visibility(self):
        for cls in (BriefingBackdrop, NeuralCoreWidget, FuturisticFaceWidget):
            w = self.make(cls)
            w.show()
            self.app.processEvents()
            self.assertTrue(w.timer.isActive())
            self.assertEqual(w.timer.timerType(), Qt.PreciseTimer)
            w.hide()
            self.assertFalse(w.timer.isActive())

    def test_face_geometry_cache_bounded_across_states_and_frames(self):
        w = self.make(FuturisticFaceWidget)
        w.show()
        self.app.processEvents()
        w.timer.stop()
        for state in ('READY', 'SPEAKING', 'ERROR', 'PROCESSING', 'LISTENING'):
            w.set_state(state)
            for phase in (0, 1, 2):
                w.phase = phase
                image = w.grab()
                self.assertFalse(image.isNull())
        self.assertLessEqual(len(w._polygons), 24)
        self.assertEqual(sum(map(len, w._graduations.values())), 96)

    def test_neural_network_rebuilds_only_for_size_change(self):
        w = self.make(NeuralCoreWidget)
        points, edges = w._network(800, 600)
        w.phase = 2
        same_points, same_edges = w._network(800, 600)
        self.assertIs(points, same_points)
        self.assertIs(edges, same_edges)
        resized_points, resized_edges = w._network(900, 700)
        self.assertIsNot(points, resized_points)
        self.assertEqual([(i,j) for i,j,d in edges], [(i,j) for i,j,d in resized_edges])


if __name__ == '__main__':
    unittest.main()
