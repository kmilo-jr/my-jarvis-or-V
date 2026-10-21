@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Execute configurar_prototype.bat primeiro.
  pause
  exit /b 1
)
start "V Prototype" .venv\Scripts\pythonw.exe main.py
