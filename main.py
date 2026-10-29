from __future__ import annotations
from app_paths import ROOT
import json
import sys
from pathlib import Path

from versao import BANNER
from vlog import setup_logging

BASE = ROOT


def load_config():
    config_path = BASE / "config" / "default.json"
    if not config_path.exists():
        example_path = BASE / "config" / "default.example.json"
        config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_app():
    from core.functional_engine import FunctionalEngine, CompatRegistry
    from brain.service import BrainService
    from brain.memory_store import PersistentMemoryStore
    from voice.engine import VoiceEngine

    cfg = load_config()
    memory_store = PersistentMemoryStore(BASE / "data" / "memory.json", max_items=int(cfg.get("memory", {}).get("max_items", 200)))
    brain = BrainService(cfg.get("brain", {}), memory_store=memory_store, personality=cfg.get("personality", {}))
    engine = FunctionalEngine(brain, memory_store=memory_store)
    registry = CompatRegistry()
    voice = VoiceEngine(cfg.get("voice", {}))
    # Carrega o modelo local em paralelo para que a primeira resposta por voz
    # não precise começar também o carregamento pesado do XTTS-v2.
    voice.warmup_tts()
    return engine, registry, voice


def main():
    setup_logging()
    from core.crash_diagnostics import enable
    enable()
    print(f"=== {BANNER} ===")
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app = QApplication(sys.argv)
    try:
        from spotify_bridge import start_bridge_background
        start_bridge_background()
    except Exception as exc:
        print(f"Spotify Bridge startup: {type(exc).__name__}: {exc}")
    app.setApplicationName("V Prototype")
    engine, registry, voice = build_app()
    window = MainWindow(engine, registry, voice)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
