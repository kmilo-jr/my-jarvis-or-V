@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Execute configurar_prototype.bat primeiro.
  pause
  exit /b 1
)
.venv\Scripts\python.exe testar_voz_edge.py
echo.
pause
