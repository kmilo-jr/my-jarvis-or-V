@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo O ambiente do V ainda nao foi configurado.
  echo Execute configurar_prototype.bat primeiro.
  pause
  exit /b 1
)
.venv\Scripts\python.exe configurar_voz_edge.py
