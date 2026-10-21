@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" testar_gemini.py
) else (
  python testar_gemini.py
)
echo.
pause
