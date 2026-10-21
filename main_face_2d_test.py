from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from main import build_app

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("V Face Lab — 2D")
    try:
        from spotify_bridge import start_bridge_background
        start_bridge_background()
    except Exception as exc:
        print(f"Spotify Bridge startup: {type(exc).__name__}: {exc}")
    engine, registry, voice = build_app()
    from ui.amber_window_2d import Amber2DTestWindow
    window = Amber2DTestWindow(engine, registry, voice, startup_greeting=False)
    window.show()
    app._v_face_test_window = window
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
