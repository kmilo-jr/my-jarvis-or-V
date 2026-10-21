@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" usar_edge_como_voz.py
) else (
  py -3.12 usar_edge_como_voz.py
)
pause
