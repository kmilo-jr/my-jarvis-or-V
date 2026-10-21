@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" testar_voz_v.py
) else (
  python testar_voz_v.py
)
