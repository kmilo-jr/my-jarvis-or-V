@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" usar_piper_como_voz.py
) else (
  py -3.12 usar_piper_como_voz.py
)
pause
