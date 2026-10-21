"""Isolated native Qt office benchmark, without accounts, voice or AI services."""
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import psutil
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QWidget
from PySide6.QtTest import QTest
from PySide6.QtCore import QEventLoop, QTimer
from ui.pixel_office import PixelOffice


class MeasuredOffice(PixelOffice):
    painted_pixels = 0
    paints = 0

    def paintEvent(self, event):
        self.paints += 1
        self.painted_pixels += sum(rect.width()*rect.height() for rect in event.region())
        super().paintEvent(event)


def main():
    app = QApplication([])
    proc = psutil.Process()
    w = QMainWindow()
    w.neural = SimpleNamespace(state='PROCESSING')
    w._active_request = 'filosofia'
    stack = QStackedWidget(); w.setCentralWidget(stack)
    office = MeasuredOffice(w); stack.addWidget(office); stack.addWidget(QWidget())
    w.resize(1000,660); w.show(); app.processEvents()
    QTest.qWait(300)
    results = {}
    for scenario in ('stationary','walking','hidden'):
        if scenario == 'walking':
            w._active_request='música';office.sync_activity()
        elif scenario == 'hidden':
            stack.setCurrentIndex(1);app.processEvents()
        frames, paints, pixels = office.frame_count, office.paints, office.painted_pixels
        cpu=proc.cpu_times(); t=time.perf_counter()
        # Native event loop: QTest.qWait polling can undercount a 16 ms timer.
        loop=QEventLoop();QTimer.singleShot(4000,loop.quit);loop.exec()
        duration=time.perf_counter()-t; after=proc.cpu_times()
        results[scenario]={'seconds':round(duration,3),
            'cpu_percent_one_core':round(100*(after.user+after.system-cpu.user-cpu.system)/duration,2),
            'rss_mib':round(proc.memory_info().rss/1024**2,2),
            'animation_updates':office.frame_count-frames,'paint_events':office.paints-paints,
            'painted_megapixels':round((office.painted_pixels-pixels)/1e6,2),
            'timer_active':office.timer.isActive()}
    w.close()
    out=Path('logs/office_preview') / ('benchmark_'+sys.argv[1]+'.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps(results))


if __name__=='__main__':main()
