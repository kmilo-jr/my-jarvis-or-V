"""Capture native failures and uncaught callbacks without recording user input."""
import faulthandler
import sys
import traceback
from datetime import datetime
from pathlib import Path

_stream = None


def enable():
    global _stream
    if _stream is not None:
        return
    try:
        folder = Path(__file__).resolve().parents[1] / 'logs'
        folder.mkdir(exist_ok=True)
        _stream = (folder / 'app_crash.log').open('a', encoding='utf-8', buffering=1)
        _stream.write(f'\nSession {datetime.now().isoformat()}\n')
        faulthandler.enable(_stream, all_threads=True)
        original = sys.excepthook

        def record(kind, value, trace):
            # Record locations/types only: exception strings may contain account data.
            _stream.write(f'Unhandled {kind.__name__}\n')
            traceback.print_tb(trace, file=_stream)
            _stream.flush()
            original(kind, value, trace)

        sys.excepthook = record
    except OSError:
        pass
