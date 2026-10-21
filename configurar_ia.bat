@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe configurar_ia.py
) else (
  py -3.12 configurar_ia.py
)
