@echo off
chcp 65001 >nul
cd /d "%~dp0"
title V 1.5 // Configurar Spotify Bridge
where spicetify >nul 2>&1
if not %errorlevel%==0 (
  echo Spicetify nao encontrado. Rode instalar_spicetify.bat primeiro.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" configurar_spotify_bridge.py
) else (
  python configurar_spotify_bridge.py
)
pause
