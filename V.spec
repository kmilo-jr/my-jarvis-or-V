# -*- mode: python ; coding: utf-8 -*-
"""Empacotamento do V com PyInstaller (modo pasta: dist/V/V.exe).

Gerado por tools/build_exe.ps1. Limites conhecidos do pacote minimo:
- NAO inclui torch/TTS (clone XTTS), modelos Whisper baixados, runtime do Qwen
  nem `vendor/`. Esses recursos continuam disponiveis rodando do codigo-fonte
  com o ambiente completo (requirements.lock.txt).
- Edge-TTS, Piper, ElevenLabs, SAPI, Spotify Bridge, brain (Gemini/Groq/Ollama),
  visão e briefing entram normalmente.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve()

hiddenimports = []
for pacote in ("core", "brain", "voice", "ui", "personality", "integrations"):
    hiddenimports += collect_submodules(pacote)

# Imports feitos por nome dentro de funcoes (o analisador estatico nao os ve).
hiddenimports += [
    "app_paths", "versao", "vlog", "secure_store",
    "legacy_tools", "legacy_config", "web_research", "market_data",
    "mobile_bridge", "pc_remote", "remote_server",
    "windows_media_session", "windows_notification_reader",
    "spotify_api", "spotify_bridge", "wake_on_lan",
    "winrt.windows.media.control", "pycaw", "comtypes", "sounddevice",
    "faster_whisper", "onnxruntime", "piper",
]

excludes = [
    # Pesados e opcionais: ficam de fora do pacote minimo.
    "torch", "torchaudio", "torchvision", "TTS", "sklearn", "matplotlib",
    "librosa", "numba", "tensorboard", "IPython", "pandas", "sympy",
    "networkx", "tkinter", "pytest",
    # Modulos Qt que o V nao usa (reduz tamanho de forma segura).
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtOpenGL",
]

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "config" / "default.example.json"), "config"),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "VERSAO.txt"), "."),
]

a = Analysis(
    [str(ROOT / "main_dual_ui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="V",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # mantem diagnostico visivel; troque para False se preferir janela limpa
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="V",
)
