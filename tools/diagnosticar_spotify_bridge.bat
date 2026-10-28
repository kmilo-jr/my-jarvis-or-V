@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0..\.venv\Scripts\python.exe" (
  "%~dp0..\.venv\Scripts\python.exe" diagnosticar_spotify_bridge.py
) else (
  python diagnosticar_spotify_bridge.py
)
pause
