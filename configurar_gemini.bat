@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" configurar_gemini.py
) else (
  python configurar_gemini.py
)
