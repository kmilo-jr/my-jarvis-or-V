@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" diagnosticar_spotify_bridge.py
) else (
  python diagnosticar_spotify_bridge.py
)
pause
