from __future__ import annotations
import sys
from main import build_app


def main():
    print("=== V 1.6 INSTAGRAM UI EXPERIMENT ===")
    from PySide6.QtWidgets import QApplication
    from ui.instagram_window import InstagramExperimentWindow
    app = QApplication(sys.argv)
    app.setApplicationName("V Instagram UI Experiment")
    try:
        from spotify_bridge import start_bridge_background
        start_bridge_background()
    except Exception as exc:
        print(f"Spotify Bridge startup: {type(exc).__name__}: {exc}")
    engine, registry, voice = build_app()
    window = InstagramExperimentWindow(engine, registry, voice)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
