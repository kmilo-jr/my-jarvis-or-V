"""Synthetic live Qt video plus real detector; no webcam capture or uploads."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtWidgets import QApplication
from ui.camera_panel import CameraPanel


def main():
    app = QApplication([])
    with patch('ui.camera_panel.QMediaDevices.videoInputs', return_value=[]):
        panel = CameraPanel()
    panel.camera = Mock()
    panel.frame_at = time.monotonic()
    panel.show()
    panel.preview_stack.setCurrentWidget(panel.video)
    image = QImage(640, 480, QImage.Format.Format_RGB32)
    image.fill(0xff335577)
    gaps, frames, analyses = [], [0], [0]
    last = [time.perf_counter()]
    original = panel.processor.run
    def analyze(*args):
        result = original(*args)
        analyses[0] += 1
        return result
    panel.processor.run = analyze
    def beat():
        now = time.perf_counter()
        gaps.append(now - last[0])
        last[0] = now
    def feed():
        frames[0] += 1
        # Distinct frame buffer each time: identical QVideoFrames are ignored
        # by QVideoSink and would incorrectly simulate a disconnected camera.
        frame = QVideoFrame(image.copy())
        frame.setStartTime(frames[0] * 33333)
        panel.sink.setVideoFrame(frame)
    heartbeat = QTimer()
    heartbeat.timeout.connect(beat)
    heartbeat.start(10)
    source = QTimer()
    source.timeout.connect(feed)
    source.start(33)
    final_state = {}
    def finish():
        # QApplication.quit closes dialogs, intentionally releasing the camera.
        # Inspect the stream before that normal shutdown happens.
        final_state['connected'] = panel.camera is not None
        final_state['fresh'] = time.monotonic() - panel.frame_at < .5
        app.quit()
    QTimer.singleShot(12000, finish)
    started = time.perf_counter()
    app.exec()
    elapsed = time.perf_counter() - started
    connected = final_state.get('connected', False)
    fresh = final_state.get('fresh', False)
    source.stop()
    heartbeat.stop()
    panel.shutdown()
    panel.close()
    result = {'duration_seconds': round(elapsed, 2), 'injected_frames': frames[0],
              'local_analyses': analyses[0], 'heartbeat_ticks': len(gaps),
              'max_ui_gap_ms': round(max(gaps) * 1000, 1),
              'p95_ui_gap_ms': round(sorted(gaps)[int(len(gaps) * .95)] * 1000, 1),
              'camera_stayed_active': connected, 'latest_frame_fresh': fresh,
              'source': 'synthetic frames; no webcam capture'}
    target = Path(__file__).resolve().parents[1] / 'logs/vision/fluency_check.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    assert connected and fresh and analyses[0] >= 3, result


if __name__ == '__main__':
    main()
