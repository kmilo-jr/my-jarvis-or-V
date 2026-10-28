@echo off
setlocal
cd /d "%~dp0"
title V 1.9.8
if not exist .venv\Scripts\pythonw.exe (
  echo Execute configurar_prototype.bat primeiro.
  pause
  exit /b 1
)
start "V 1.9.8" .venv\Scripts\pythonw.exe main.py
endlocal
