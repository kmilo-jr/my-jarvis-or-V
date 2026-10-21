@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe configurar_spotify_api.py
) else (
  py -3.12 configurar_spotify_api.py
)
pause
