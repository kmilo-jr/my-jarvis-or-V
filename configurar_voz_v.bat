@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" configurar_voz_v.py
) else (
  python configurar_voz_v.py
)
