@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" testar_som_processamento.py
) else (
  python testar_som_processamento.py
)
pause
