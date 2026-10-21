"""Compare preserved source with current renderers, without starting V services.

Requires logs/animation_20261002/*.py.before, captured before this change.
Reports paint time, not monitor FPS or whole-application latency.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import statistics
import time
import types
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QFontDatabase
from ui.briefing_scene import BriefingBackdrop
from ui.futuristic_face import FuturisticFaceWidget
from ui.neural_core import NeuralCoreWidget


def main():
    print('Initializing offscreen renderer...', flush=True)
    app = QApplication.instance() or QApplication([])
    for name in ('segoeui.ttf', 'segoeuib.ttf'):
        path = Path('C:/Windows/Fonts') / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    root = Path(__file__).resolve().parents[1]
    output = root / 'logs/animation_20261002'
    results = {}
    cases = [('orbital', 'briefing_scene.py', BriefingBackdrop, (1180, 720)),
             ('face', 'futuristic_face.py', FuturisticFaceWidget, (690, 620)),
             ('neural', 'neural_core.py', NeuralCoreWidget, (500, 500))]
    for name, filename, current, size in cases:
        module = types.ModuleType('ui._before_' + name)
        module.__package__ = 'ui'
        source = output / (filename + '.before')
        module.__file__ = str(root / 'ui' / filename)
        exec(compile(source.read_text(encoding='utf-8'), str(source), 'exec'), module.__dict__)
        old = getattr(module, current.__name__)(None)
        new = current(None)
        widgets = (old, new)
        for w in widgets:
            w.resize(*size)
            w.show()
        app.processEvents()
        for w in widgets:
            w.timer.stop()
        images = [QImage(w.size(), QImage.Format.Format_ARGB32_Premultiplied) for w in widgets]
        comparisons = {}
        timings = [[], []]
        for state in ('READY', 'LISTENING', 'PROCESSING', 'SPEAKING', 'ERROR'):
            for w in widgets:
                w.set_state(state)
                w.phase = 1.25
                if hasattr(w, 'speech_level'):
                    w.speech_level = .4
            for i, w in enumerate(widgets):
                w.render(images[i])
            arrays = [np.frombuffer(image.constBits(), dtype=np.uint8).astype(np.int16) for image in images]
            diff = np.abs(arrays[0] - arrays[1])
            comparisons[state] = {'mean_channel_difference': float(diff.mean()),
                                   'changed_channel_fraction': float(np.count_nonzero(diff)/diff.size)}
            assert diff.mean() < .1, (name, state, comparisons[state])
            if state == 'SPEAKING':
                for i, label in enumerate(('before', 'after')):
                    images[i].save(str(output / f'{name}_{label}.png'))
                for frame in range(65):
                    for i, w in enumerate(widgets):
                        w.phase = 1.25 + frame*.01
                        start = time.perf_counter()
                        w.render(images[i])
                        if frame >= 5:
                            timings[i].append((time.perf_counter()-start)*1000)
        results[name] = {'before_median_ms': statistics.median(timings[0]),
                         'after_median_ms': statistics.median(timings[1]),
                         'visual_comparison': comparisons}
        for w in widgets:
            w.close()
            w.deleteLater()
        app.processEvents()
        print(name, json.dumps(results[name]), flush=True)
    (output/'comparison.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('Rendering and visual comparisons passed.', flush=True)


if __name__ == '__main__':
    main()
