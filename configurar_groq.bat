@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" configurar_groq.py
if errorlevel 1 pause
endlocal
