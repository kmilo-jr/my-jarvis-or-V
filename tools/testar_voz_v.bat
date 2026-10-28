@echo off
cd /d "%~dp0"
if exist "%~dp0..\.venv\Scripts\python.exe" (
  "%~dp0..\.venv\Scripts\python.exe" testar_voz_v.py
) else (
  python testar_voz_v.py
)
