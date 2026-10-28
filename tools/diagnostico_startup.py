from __future__ import annotations
# --- movido para tools/: a raiz do projeto e um nivel acima ---
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import importlib, json, platform, sys
from pathlib import Path

ROOT = _ROOT
REQUIRED = [
    ("PySide6", "PySide6"), ("psutil", "psutil"), ("pyautogui", "pyautogui"),
    ("pywinauto", "pywinauto"), ("sounddevice", "sounddevice"), ("numpy", "numpy"),
    ("faster_whisper", "faster-whisper"), ("requests", "requests"), ("bs4", "beautifulsoup4"),
    ("winrt.windows.media.control", "winrt-Windows.Media.Control"),
]

def main():
    print("="*62); print("V PROTOTYPE 1.0 - BRAIN CORE ALPHA - DIAGNOSTICO"); print("="*62)
    print(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    print(f"Executavel: {sys.executable}\nProjeto: {ROOT}")
    failed=[]
    try:
        json.loads((ROOT/'config'/'default.json').read_text(encoding='utf-8'))
        print('[OK] CONFIG JSON valido.')
    except Exception as exc:
        failed.append(('config',exc)); print(f'[FALHA] CONFIG: {type(exc).__name__}: {exc}')
    for module, package in REQUIRED:
        try:
            obj=importlib.import_module(module); print(f"[OK] {package}: {getattr(obj,'__version__','ok')}")
        except Exception as exc:
            failed.append((package,exc)); print(f"[FALHA] {package}: {type(exc).__name__}: {exc}")
    try:
        import legacy_tools
        from core.functional_engine import FunctionalEngine
        print('[OK] Action Core legado + Functional Engine carregados.')
    except Exception as exc:
        failed.append(('action core',exc)); print(f'[FALHA] Action Core: {type(exc).__name__}: {exc}')
    if not failed:
        try:
            from PySide6.QtWidgets import QApplication
            from main import build_app
            from ui.main_window import MainWindow
            app=QApplication.instance() or QApplication([])
            engine, registry, voice=build_app(); w=MainWindow(engine,registry,voice); w.close(); app.processEvents()
            print('[OK] Interface principal construida.')
        except Exception as exc:
            failed.append(('ui',exc)); print(f'[FALHA] UI: {type(exc).__name__}: {exc}')
    print('-'*62)
    if failed:
        print('DIAGNOSTICO: ha falhas. Envie logs\\startup.log.'); return 1
    print('DIAGNOSTICO: inicializacao pronta.'); return 0

if __name__=='__main__': raise SystemExit(main())
